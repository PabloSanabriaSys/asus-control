#!/usr/bin/env bash
# Desinstala ASUS Control del usuario actual. No toca alternar-ventilacion ni /etc/asusd.
# Opción: --purge para borrar también la configuración (~/.config/asus-control).
set -euo pipefail

readonly APP_ID=asus-control
readonly DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
readonly CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

pkill -u "$(id -u)" -f '^/usr/bin/python3 -m asus_control' 2>/dev/null || true

rm -rf -- "$DATA_HOME/$APP_ID"
rm -f -- \
    "$HOME/.local/bin/$APP_ID" \
    "$DATA_HOME/applications/$APP_ID.desktop" \
    "$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg" \
    "$CONFIG_HOME/autostart/$APP_ID.desktop"

if [[ "${1:-}" == "--purge" ]]; then
    rm -rf -- "$CONFIG_HOME/$APP_ID"
fi

command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
echo "ASUS Control desinstalado."
