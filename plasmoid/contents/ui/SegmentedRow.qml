/*
 * Grupo de botones exclusivos. El botón marcado sigue siempre a `current`
 * (el estado leído); al pulsar solo se emite `activated`.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents

RowLayout {
    id: row

    /** Lista de {value, label}. */
    property var options: []
    property var current: null

    signal activated(var value)

    spacing: Kirigami.Units.smallSpacing

    Repeater {
        model: row.options

        delegate: PlasmaComponents.Button {
            required property var modelData

            Layout.fillWidth: true
            // Igual ancho preferido para que todos los botones midan lo mismo.
            Layout.preferredWidth: Kirigami.Units.gridUnit
            text: modelData.label
            checkable: true
            checked: row.current === modelData.value
            onClicked: {
                // El clic invierte `checked`; se vuelve a enlazar con el estado real.
                checked = Qt.binding(() => row.current === modelData.value);
                if (row.current !== modelData.value)
                    row.activated(modelData.value);
            }
        }
    }
}
