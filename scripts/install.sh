#!/usr/bin/env bash
# Instala ASUS Control para el usuario actual (sin sudo, sin pip).
# Usa el Python y el PySide6 del sistema. Opción: --no-start para no lanzarla al terminar.
set -euo pipefail

readonly APP_ID=asus-control
readonly PYTHON=/usr/bin/python3
readonly REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
readonly LIB_DIR="$DATA_HOME/$APP_ID"
readonly LAUNCHER="$HOME/.local/bin/$APP_ID"
readonly DESKTOP_FILE="$DATA_HOME/applications/$APP_ID.desktop"
readonly ICON_FILE="$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg"

die() { echo "Error: $*" >&2; exit 1; }

check_requirements() {
    [[ $EUID -ne 0 ]] || die "instala como usuario normal, sin sudo."
    "$PYTHON" -c 'import PySide6' 2>/dev/null || die "$PYTHON no puede importar PySide6."
    command -v asusctl >/dev/null || echo "Aviso: asusctl no está instalado; los controles aparecerán como no disponibles."
}

stop_running_instance() {
    pkill -u "$(id -u)" -f "^$PYTHON -m asus_control" 2>/dev/null || true
}

install_package() {
    rm -rf -- "$LIB_DIR"
    mkdir -p -- "$LIB_DIR"
    cp -r -- "$REPO/src/asus_control" "$LIB_DIR/"
    find "$LIB_DIR" -name __pycache__ -type d -prune -exec rm -rf {} +
}

install_launcher() {
    mkdir -p -- "$(dirname "$LAUNCHER")"
    cat > "$LAUNCHER" <<LAUNCHER
#!/bin/sh
export PYTHONPATH="$LIB_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec $PYTHON -m asus_control "\$@"
LAUNCHER
    chmod 0755 -- "$LAUNCHER"
}

install_desktop_entry() {
    install -D -m 0644 -- "$REPO/src/asus_control/resources/$APP_ID.svg" "$ICON_FILE"
    mkdir -p -- "$(dirname "$DESKTOP_FILE")"
    cat > "$DESKTOP_FILE" <<DESKTOP
[Desktop Entry]
Type=Application
Name=ASUS Control
GenericName=Control de hardware ASUS
Comment=Perfiles, ventilación, iluminación y batería del ROG Strix G16
Exec=$LAUNCHER
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
    stop_running_instance
    install_package
    install_launcher
    install_desktop_entry
    echo "Instalado en $LIB_DIR"
    echo "Lanzador: $LAUNCHER"
    if [[ "${1:-}" != "--no-start" ]]; then
        # El primer arranque activa el inicio automático (configurable desde el menú).
        setsid -f "$LAUNCHER" >/dev/null 2>&1
        echo "ASUS Control iniciado en la bandeja."
    fi
}

main "$@"
