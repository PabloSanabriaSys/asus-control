/*
 * Slider de los 4 niveles de brillo (Apagado, Bajo, Medio, Alto).
 * Igual que los botones, la posición sigue al nivel leído: al soltar (o con teclado
 * o rueda) solo se emite `activated` y el slider vuelve a enlazarse con `current`.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents

RowLayout {
    id: row

    required property Texts texts
    property var current: null

    signal activated(string level)

    readonly property var levels: ["off", "low", "medium", "high"]
    readonly property int currentIndex: Math.max(0, levels.indexOf(current))

    spacing: Kirigami.Units.smallSpacing

    Kirigami.Icon {
        source: "input-keyboard-brightness"
        fallback: "input-keyboard"
        implicitWidth: Kirigami.Units.iconSizes.small
        implicitHeight: Kirigami.Units.iconSizes.small
    }

    PlasmaComponents.Slider {
        id: slider

        Layout.fillWidth: true
        from: 0
        to: row.levels.length - 1
        stepSize: 1
        snapMode: PlasmaComponents.Slider.SnapAlways
        value: row.currentIndex

        // El ratón confirma al soltar; teclado y rueda, en cada paso.
        onMoved: if (!pressed) commit()
        onPressedChanged: if (!pressed) commit()

        function commit() {
            const level = row.levels[Math.round(value)];
            value = Qt.binding(() => row.currentIndex);
            if (level !== row.current)
                row.activated(level);
        }
    }

    PlasmaComponents.Label {
        // Ancho fijo para que el slider no cambie de tamaño con cada nivel.
        Layout.preferredWidth: Kirigami.Units.gridUnit * 3.5
        horizontalAlignment: Text.AlignRight
        text: row.current ? row.texts.brightness(row.current) : "—"
        opacity: 0.8
    }
}
