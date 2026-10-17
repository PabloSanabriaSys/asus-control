/* Sección con título discreto y aviso opcional («No disponible», etc.). */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents

ColumnLayout {
    id: section

    property string title
    property string note: ""
    default property alias content: body.data

    Layout.fillWidth: true
    spacing: Kirigami.Units.smallSpacing

    RowLayout {
        Layout.fillWidth: true

        Kirigami.Heading {
            level: 5
            text: section.title
            opacity: 0.75
            Layout.fillWidth: true
        }

        PlasmaComponents.Label {
            visible: section.note !== ""
            text: section.note
            font: Kirigami.Theme.smallFont
            opacity: 0.7
        }
    }

    ColumnLayout {
        id: body

        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
    }
}
