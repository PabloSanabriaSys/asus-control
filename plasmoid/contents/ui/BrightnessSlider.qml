/*
 * Slider de los 4 niveles de brillo (Apagado, Bajo, Medio, Alto).
 * La posición sigue a `current` (valor mostrado: pendiente o leído). Al soltar, o con
 * teclado o rueda, solo se emite `activated` y el slider vuelve a enlazarse con `current`.
 */
import QtQuick
import org.kde.plasma.components as PlasmaComponents

PlasmaComponents.Slider {
    id: slider

    property var current: null

    signal activated(string level)

    readonly property var levels: ["off", "low", "medium", "high"]
    readonly property int currentIndex: Math.max(0, levels.indexOf(current))

    from: 0
    to: levels.length - 1
    stepSize: 1
    snapMode: PlasmaComponents.Slider.SnapAlways
    value: currentIndex

    // El ratón confirma al soltar; teclado y rueda, en cada paso.
    onMoved: if (!pressed) commit()
    onPressedChanged: if (!pressed) commit()

    function commit() {
        const level = levels[Math.round(value)];
        value = Qt.binding(() => currentIndex);
        if (level !== current)
            activated(level);
    }
}
