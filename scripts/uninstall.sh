#!/usr/bin/env bash
# Desinstala ASUS Control del usuario actual. No toca alternar-ventilacion ni /etc/asusd.
# Opción: --no-restart para no reiniciar plasmashell al terminar.
set -euo pipefail

readonly APP_ID=asus-control
readonly APPLET_ID=com.pablosanabria.asuscontrol
readonly DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
readonly CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
readonly STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

# Restore first. Refuse to remove the only recovery tool if any setting is still pending.
readonly SAVING_UNIT="$APP_ID-power-saving.service"
systemctl --user stop "$SAVING_UNIT" 2>/dev/null || true

abort_uninstall() {
    echo "No se pudo restaurar la configuración. Se conservan ASUS Control y su respaldo." >&2
    systemctl --user start "$SAVING_UNIT" 2>/dev/null || true
    exit 1
}

needs_restore=no
if [[ -e "$STATE_HOME/$APP_ID/power-saving.json" ]]; then
    needs_restore="$(/usr/bin/python3 -c '
import json, sys
with open(sys.argv[1]) as handle:
    state = json.load(handle)
if state["version"] != 1:
    sys.exit(1)
print("yes" if state["session"] is not None else "no")
' "$STATE_HOME/$APP_ID/power-saving.json")" || abort_uninstall
fi
if [[ "$needs_restore" == yes ]]; then
    [[ -x "$HOME/.local/bin/$APP_ID" ]] || abort_uninstall
    if ! "$HOME/.local/bin/$APP_ID" power-saving off | /usr/bin/python3 -c \
        'import json,sys; r=json.load(sys.stdin); sys.exit(0 if r["ok"] and not r["state"]["powerSaving"]["restoring"] and not r["state"]["powerSaving"]["enabled"] else 1)'; then
        abort_uninstall
    fi
fi
systemctl --user disable "$SAVING_UNIT" 2>/dev/null || true
rm -f -- "$CONFIG_HOME/systemd/user/$SAVING_UNIT"
systemctl --user daemon-reload

if kpackagetool6 -t Plasma/Applet --show "$APPLET_ID" >/dev/null 2>&1; then
    kpackagetool6 -t Plasma/Applet --remove "$APPLET_ID" >/dev/null
fi

rm -rf -- "$DATA_HOME/$APP_ID" "$CONFIG_HOME/$APP_ID"
rm -f -- \
    "$HOME/.local/bin/$APP_ID" \
    "$DATA_HOME/applications/$APP_ID.desktop" \
    "$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID"*.svg \
    "$CONFIG_HOME/autostart/$APP_ID.desktop"

command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
if [[ "${1:-}" != "--no-restart" ]]; then
    systemctl --user restart plasma-plasmashell.service
fi
echo "ASUS Control desinstalado."
