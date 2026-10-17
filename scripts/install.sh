#!/usr/bin/env bash
# Instala ASUS Control para el usuario actual (sin sudo, sin pip):
#   - backend Python en ~/.local/share/asus-control y lanzador ~/.local/bin/asus-control
#   - applet de bandeja de Plasma (com.pablosanabria.asuscontrol)
# Opción: --no-restart para no reiniciar plasmashell al terminar.
set -euo pipefail

readonly APP_ID=asus-control
readonly APPLET_ID=com.pablosanabria.asuscontrol
readonly PYTHON=/usr/bin/python3
readonly REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
readonly CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
readonly LIB_DIR="$DATA_HOME/$APP_ID"
readonly LAUNCHER="$HOME/.local/bin/$APP_ID"
readonly DESKTOP_FILE="$DATA_HOME/applications/$APP_ID.desktop"
readonly ICON_FILE="$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg"

die() { echo "Error: $*" >&2; exit 1; }

check_requirements() {
    [[ $EUID -ne 0 ]] || die "instala como usuario normal, sin sudo."
    "$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' || die "se necesita Python 3.11 o superior."
    command -v kpackagetool6 >/dev/null || die "falta kpackagetool6 (Plasma 6)."
    command -v asusctl >/dev/null || echo "Aviso: asusctl no está instalado; los controles aparecerán como no disponibles."
}

remove_legacy_tray_app() {
    # Versión anterior: app Qt con icono propio y entrada de autostart.
    pkill -u "$(id -u)" -f "^$PYTHON -m asus_control$" 2>/dev/null || true
    rm -f -- "$CONFIG_HOME/autostart/$APP_ID.desktop"
    rm -rf -- "$CONFIG_HOME/$APP_ID"
}

install_backend() {
    rm -rf -- "$LIB_DIR"
    mkdir -p -- "$LIB_DIR"
    cp -r -- "$REPO/src/asus_control" "$LIB_DIR/"
    find "$LIB_DIR" -name __pycache__ -type d -prune -exec rm -rf {} +
    mkdir -p -- "$(dirname "$LAUNCHER")"
    cat > "$LAUNCHER" <<LAUNCHER
#!/bin/sh
export PYTHONPATH="$LIB_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec $PYTHON -m asus_control "\$@"
LAUNCHER
    chmod 0755 -- "$LAUNCHER"
    "$LAUNCHER" profile >/dev/null || echo "Aviso: el backend no pudo leer el perfil (¿asusd activo?)."
}

install_applet() {
    install -D -m 0644 -- "$REPO/plasmoid/$APP_ID.svg" "$ICON_FILE"
    if kpackagetool6 -t Plasma/Applet --show "$APPLET_ID" >/dev/null 2>&1; then
        kpackagetool6 -t Plasma/Applet --upgrade "$REPO/plasmoid" >/dev/null
    else
        kpackagetool6 -t Plasma/Applet --install "$REPO/plasmoid" >/dev/null
    fi
}

install_launcher_entry() {
    # Abre el mismo applet en una ventana desde el lanzador de aplicaciones.
    mkdir -p -- "$(dirname "$DESKTOP_FILE")"
    cat > "$DESKTOP_FILE" <<DESKTOP
[Desktop Entry]
Type=Application
Name=ASUS Control
GenericName=Control de hardware ASUS
Comment=Perfiles, ventilación, iluminación y batería del ROG Strix G16
Exec=plasmawindowed $APPLET_ID
Icon=$APP_ID
Terminal=false
Categories=System;Settings;HardwareSettings;
Keywords=asus;rog;ventilador;batería;teclado;
StartupNotify=false
DESKTOP
    command -v update-desktop-database >/dev/null && update-desktop-database -q "$(dirname "$DESKTOP_FILE")" || true
    command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
}

main() {
    check_requirements
    remove_legacy_tray_app
    install_backend
    install_applet
    install_launcher_entry
    echo "Backend: $LAUNCHER"
    echo "Applet: $APPLET_ID"
    if [[ "${1:-}" == "--no-restart" ]]; then
        echo "Reinicia Plasma para ver los cambios: systemctl --user restart plasma-plasmashell"
    else
        systemctl --user restart plasma-plasmashell.service
        echo "Plasma reiniciado; ASUS Control aparece en la bandeja del sistema."
    fi
}

main "$@"
