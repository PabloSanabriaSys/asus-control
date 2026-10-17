#!/usr/bin/env bash
# Desinstala ASUS Control del usuario actual. No toca alternar-ventilacion ni /etc/asusd.
# Opción: --no-restart para no reiniciar plasmashell al terminar.
set -euo pipefail

readonly APP_ID=asus-control
readonly APPLET_ID=com.pablosanabria.asuscontrol
readonly DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
readonly CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

if kpackagetool6 -t Plasma/Applet --show "$APPLET_ID" >/dev/null 2>&1; then
    kpackagetool6 -t Plasma/Applet --remove "$APPLET_ID" >/dev/null
fi

rm -rf -- "$DATA_HOME/$APP_ID" "$CONFIG_HOME/$APP_ID"
rm -f -- \
    "$HOME/.local/bin/$APP_ID" \
    "$DATA_HOME/applications/$APP_ID.desktop" \
    "$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg" \
    "$CONFIG_HOME/autostart/$APP_ID.desktop"

command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
if [[ "${1:-}" != "--no-restart" ]]; then
    systemctl --user restart plasma-plasmashell.service
fi
echo "ASUS Control desinstalado."
