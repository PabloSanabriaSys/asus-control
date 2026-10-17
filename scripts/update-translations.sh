#!/usr/bin/env bash
# Traducciones del applet (gettext, dominio plasma_applet_<id>).
#
#   scripts/update-translations.sh          extrae las cadenas i18n() a translate/template.pot
#                                           y actualiza cada .po (después, traduce lo nuevo)
#   scripts/update-translations.sh --check  falla si la plantilla está desactualizada o si
#                                           algún .po tiene entradas sin traducir o difusas
set -euo pipefail

readonly APPLET_ID=com.pablosanabria.asuscontrol
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly TRANSLATE_DIR="$ROOT/plasmoid/translate"
readonly TEMPLATE="$TRANSLATE_DIR/template.pot"

extract() {
    (
        cd "$ROOT/plasmoid"
        xgettext \
            --from-code=UTF-8 \
            --language=JavaScript \
            --keyword= \
            --keyword=i18n:1 \
            --keyword=i18nc:1c,2 \
            --keyword=i18np:1,2 \
            --keyword=i18ncp:1c,2,3 \
            --package-name="plasma_applet_$APPLET_ID" \
            --add-comments=TRANSLATORS: \
            --sort-by-file \
            --output="$1" \
            contents/ui/*.qml
    )
}

# Identificadores (contexto + mensaje) de un catálogo, sin cabecera ni referencias.
message_ids() {
    msgcat --no-location --no-wrap --sort-output "$1" | grep -E '^(msgctxt|msgid) ' | grep -v '^msgid ""$'
}

check() {
    local status=0
    FRESH="$(mktemp)"
    trap 'rm -f -- "$FRESH"' EXIT
    extract "$FRESH"
    if ! diff -q <(message_ids "$FRESH") <(message_ids "$TEMPLATE") >/dev/null; then
        echo "template.pot está desactualizado: ejecuta scripts/update-translations.sh" >&2
        status=1
    fi
    local po stats
    for po in "$TRANSLATE_DIR"/*.po; do
        if ! diff -q <(message_ids "$TEMPLATE") <(message_ids "$po") >/dev/null; then
            echo "${po##*/} no coincide con la plantilla" >&2
            status=1
        fi
        stats="$(msgfmt --check --statistics -o /dev/null "$po" 2>&1)"
        if [[ $stats == *untranslated* || $stats == *fuzzy* ]]; then
            echo "${po##*/}: $stats" >&2
            status=1
        fi
    done
    return "$status"
}

update() {
    extract "$TEMPLATE"
    local po
    for po in "$TRANSLATE_DIR"/*.po; do
        [[ -e $po ]] || continue
        msgmerge --quiet --update --backup=none --no-fuzzy-matching "$po" "$TEMPLATE"
        echo "Actualizado: ${po#"$ROOT"/} ($(msgfmt --statistics -o /dev/null "$po" 2>&1))"
    done
}

case "${1:-}" in
    --check) check ;;
    "") update ;;
    *) echo "uso: $0 [--check]" >&2; exit 2 ;;
esac
