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
readonly ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"

die() { echo "Error: $*" >&2; exit 1; }

check_requirements() {
    [[ $EUID -ne 0 ]] || die "instala como usuario normal, sin sudo."
    "$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' || die "se necesita Python 3.11 o superior."
    command -v kpackagetool6 >/dev/null || die "falta kpackagetool6 (Plasma 6)."
    command -v msgfmt >/dev/null || die "falta msgfmt (paquete gettext) para compilar las traducciones."
    # El applet habla con el servicio asusd (paquete asusctl) por D-Bus.
    busctl --system status xyz.ljones.Asusd >/dev/null 2>&1 \
        || echo "Aviso: asusd no está en ejecución; los controles aparecerán como no disponibles."
}

remove_legacy_tray_app() {
    # Versión anterior: app Qt con icono propio y entrada de autostart.
    pkill -u "$(id -u)" -f "^$PYTHON -m asus_control$" 2>/dev/null || true
    rm -f -- "$CONFIG_HOME/autostart/$APP_ID.desktop"
    # Preserve user preferences and durable restoration snapshots during upgrades.
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

# Copia el paquete a un directorio temporal y compila las traducciones dentro de él
# (contents/locale/<idioma>/LC_MESSAGES/plasma_applet_<id>.mo); el repositorio solo guarda los .po.
build_applet() {
    local staging=$1
    cp -r -- "$REPO/plasmoid/." "$staging/"
    rm -rf -- "$staging/translate" "$staging/icons"
    local po lang
    for po in "$REPO"/plasmoid/translate/*.po; do
        lang="$(basename "$po" .po)"
        mkdir -p -- "$staging/contents/locale/$lang/LC_MESSAGES"
        msgfmt --check -o "$staging/contents/locale/$lang/LC_MESSAGES/plasma_applet_$APPLET_ID.mo" "$po"
    done
}

install_applet() {
    # asus-control: lanzador y explorador de widgets; asus-control-symbolic: bandeja (monocromo,
    # Plasma lo colorea según el tema mediante la clase ColorScheme-Text).
    install -D -m 0644 -t "$ICON_DIR" -- "$REPO"/plasmoid/icons/*.svg
    STAGING="$(mktemp -d)"
    trap 'rm -rf -- "$STAGING"' EXIT
    build_applet "$STAGING"
    if kpackagetool6 -t Plasma/Applet --show "$APPLET_ID" >/dev/null 2>&1; then
        kpackagetool6 -t Plasma/Applet --upgrade "$STAGING" >/dev/null
    else
        kpackagetool6 -t Plasma/Applet --install "$STAGING" >/dev/null
    fi
}

install_launcher_entry() {
    # Abre el mismo applet en una ventana desde el lanzador de aplicaciones.
    mkdir -p -- "$(dirname "$DESKTOP_FILE")"
    cat > "$DESKTOP_FILE" <<DESKTOP
[Desktop Entry]
Type=Application
Name=ASUS Control
GenericName=ASUS hardware control
GenericName[es]=Control de hardware ASUS
Comment=Profiles, fans, lighting and battery for the ROG Strix G16
Comment[es]=Perfiles, ventilación, iluminación y batería del ROG Strix G16
Exec=plasmawindowed $APPLET_ID
Icon=$APP_ID
Terminal=false
Categories=System;Settings;HardwareSettings;
Keywords=asus;rog;fan;battery;keyboard;
Keywords[es]=asus;rog;ventilador;batería;teclado;
StartupNotify=false
DESKTOP
    command -v update-desktop-database >/dev/null && update-desktop-database -q "$(dirname "$DESKTOP_FILE")" || true
    command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
}

install_power_saving_service() {
    local unit_dir="$CONFIG_HOME/systemd/user"
    mkdir -p -- "$unit_dir"
    cat > "$unit_dir/$APP_ID-power-saving.service" <<UNIT
[Unit]
Description=ASUS Control battery saving restoration and session recovery
PartOf=graphical-session.target
After=plasma-powerdevil.service

[Service]
Type=simple
ExecStart="$LAUNCHER" power-saving watch
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical-session.target
UNIT
    systemctl --user daemon-reload
    systemctl --user enable "$APP_ID-power-saving.service"
    if systemctl --user is-active --quiet graphical-session.target; then
        systemctl --user restart "$APP_ID-power-saving.service"
    fi
}

main() {
    check_requirements
    remove_legacy_tray_app
    install_backend
    install_applet
    install_launcher_entry
    install_power_saving_service
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
