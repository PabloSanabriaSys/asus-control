#!/usr/bin/env bash
# Corrección persistente de la cinta LED del G615JH en asusd.
#
#   sudo scripts/lightbar-fix.sh status   # diagnóstico (no requiere sudo)
#   sudo scripts/lightbar-fix.sh apply    # respalda, instala la definición y reinicia asusd
#   sudo scripts/lightbar-fix.sh revert   # elimina la definición y reinicia asusd
#
# Se ejecuta una sola vez; ASUS Control nunca modifica /etc.
set -euo pipefail

readonly SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/system/asusd_user_ledmodes.ron"
readonly TARGET=/etc/asusd/asusd_user_ledmodes.ron
readonly AURA_CONFIG=/etc/asusd/aura_19b6.ron
readonly EXPECTED_BOARD=G615JH
readonly LIGHTBAR_ZONE=2
readonly STAMP="$(date +%Y%m%d-%H%M%S)"

die() { echo "Error: $*" >&2; exit 1; }

require_root() {
    [[ $EUID -eq 0 ]] || die "ejecuta con sudo: sudo $0 $1"
}

aura_path() {
    busctl --system --list tree xyz.ljones.Asusd 2>/dev/null | grep -m1 '^/xyz/ljones/aura/' || true
}

supported_zones() {
    local path
    path="$(aura_path)"
    [[ -n $path ]] || { echo "asusd no responde"; return; }
    busctl --system get-property xyz.ljones.Asusd "$path" xyz.ljones.Aura SupportedPowerZones
}

lightbar_supported() {
    # Salida de busctl: "au N z1 z2 ..."
    supported_zones | awk -v zone="$LIGHTBAR_ZONE" '{ for (i = 3; i <= NF; i++) if ($i == zone) found = 1 } END { exit !found }'
}

wait_for_asusd() {
    for _ in $(seq 20); do
        [[ -n "$(aura_path)" ]] && return 0
        sleep 0.5
    done
    die "asusd no volvió a publicar el dispositivo Aura."
}

backup() {
    [[ -f $1 ]] && cp -a -- "$1" "$1.bak-$STAMP" && echo "Respaldo: $1.bak-$STAMP"
    return 0
}

status() {
    echo "Placa: $(cat /sys/class/dmi/id/board_name)"
    echo "Definición local: $([[ -f $TARGET ]] && echo "instalada ($TARGET)" || echo "no instalada")"
    echo "Zonas de energía admitidas: $(supported_zones)"
    if lightbar_supported; then echo "Cinta LED: admitida"; else echo "Cinta LED: no admitida"; fi
}

apply() {
    require_root apply
    [[ "$(cat /sys/class/dmi/id/board_name)" == "$EXPECTED_BOARD" ]] \
        || die "este equipo no es un $EXPECTED_BOARD."
    [[ -f $SOURCE ]] || die "no se encontró $SOURCE."
    if [[ -f $TARGET ]] && cmp -s "$SOURCE" "$TARGET"; then
        echo "La definición ya estaba instalada."
    else
        backup "$TARGET"
        backup "$AURA_CONFIG"
        install -m 0644 -o root -g root -- "$SOURCE" "$TARGET"
        echo "Instalado: $TARGET"
    fi
    systemctl restart asusd.service
    wait_for_asusd
    lightbar_supported || die "asusd sigue sin admitir la cinta LED. Revisa: journalctl -u asusd -b"
    asusctl aura power lightbar --boot --awake
    echo "Cinta LED admitida y encendida."
}

revert() {
    require_root revert
    if [[ ! -f $TARGET ]]; then
        echo "No hay definición local instalada."
        return
    fi
    backup "$TARGET"
    rm -f -- "$TARGET"
    systemctl restart asusd.service
    wait_for_asusd
    echo "Definición eliminada; asusd vuelve a la configuración genérica."
}

case "${1:-status}" in
    status) status ;;
    apply) apply ;;
    revert) revert ;;
    *) die "uso: $0 [status|apply|revert]" ;;
esac
