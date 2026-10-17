/* Contenido del popup: resumen, controles y sensores. */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras

PlasmaExtras.Representation {
    id: full

    required property var applet

    readonly property var hw: applet.hw
    readonly property bool controlsEnabled: applet.available && !applet.busy
    readonly property string unavailable: "No disponible"

    Layout.minimumWidth: Kirigami.Units.gridUnit * 18
    Layout.preferredWidth: Kirigami.Units.gridUnit * 20
    Layout.preferredHeight: Kirigami.Units.gridUnit * 27
    collapseMarginsHint: true

    function sensorValue(value) {
        return value === null || value === undefined ? "—" : String(value);
    }

    function batteryText() {
        const battery = hw ? hw.battery : null;
        if (!battery)
            return unavailable;
        const parts = [];
        if (battery.acOnline !== null)
            parts.push(battery.acOnline ? "Conectado a corriente" : "Con batería");
        if (battery.status)
            parts.push(battery.status);
        return parts.join(" · ") || unavailable;
    }

    PlasmaComponents.ScrollView {
        id: scroll

        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            // Ancho fijado al área visible: sin desplazamiento horizontal.
            width: scroll.availableWidth
            spacing: Kirigami.Units.largeSpacing

            // --- Resumen ------------------------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.largeSpacing

                Kirigami.Icon {
                    source: "asus-control"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }

                ColumnLayout {
                    spacing: 0

                    Kirigami.Heading {
                        level: 2
                        text: full.hw && full.hw.profile ? full.hw.profile : full.unavailable
                    }

                    PlasmaComponents.Label {
                        text: "Perfil de rendimiento"
                        opacity: 0.7
                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                PlasmaComponents.BusyIndicator {
                    visible: full.applet.busy || full.hw === null
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: Kirigami.Units.iconSizes.medium
                }

                ColumnLayout {
                    spacing: 0

                    Kirigami.Heading {
                        Layout.alignment: Qt.AlignRight
                        level: 2
                        text: full.hw && full.hw.battery && full.hw.battery.percent !== null
                              ? full.hw.battery.percent + " %" : "—"
                    }

                    PlasmaComponents.Label {
                        Layout.alignment: Qt.AlignRight
                        text: full.hw && full.hw.battery && full.hw.battery.acOnline
                              ? "Conectado" : "Batería"
                        opacity: 0.7
                    }
                }
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                type: Kirigami.MessageType.Warning
                text: "asusd no responde. Los controles están deshabilitados."
                visible: full.hw !== null && !full.hw.asusdAvailable
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                type: Kirigami.MessageType.Error
                text: full.applet.message
                visible: full.applet.messageIsError && full.applet.message !== ""
                actions: [
                    Kirigami.Action {
                        icon.name: "dialog-close"
                        text: "Cerrar"
                        displayHint: Kirigami.DisplayHint.IconOnly
                        onTriggered: full.applet.clearMessage()
                    }
                ]
            }

            // --- Controles ----------------------------------------------------------
            Section {
                title: "Rendimiento"
                note: full.applet.available ? "" : full.unavailable

                SegmentedRow {
                    Layout.fillWidth: true
                    enabled: full.controlsEnabled
                    current: full.hw ? full.hw.profile : null
                    options: [
                        { value: "Quiet", label: "Quiet" },
                        { value: "Balanced", label: "Balanced" },
                        { value: "Performance", label: "Performance" }
                    ]
                    onActivated: value => full.applet.apply(["profile", value])
                }
            }

            // Ventilación solo existe en Balanced; nunca se cambia el perfil para mostrarla.
            Section {
                visible: full.hw !== null && full.hw.profile === "Balanced"
                title: "Ventilación"
                note: !full.hw || !full.hw.fans ? full.unavailable
                      : full.hw.fans.mode === null ? "Curvas personalizadas" : ""

                SegmentedRow {
                    Layout.fillWidth: true
                    enabled: full.controlsEnabled && full.hw.fans !== null
                    current: full.hw && full.hw.fans ? full.hw.fans.mode : null
                    options: [
                        { value: "Normal", label: "Normal" },
                        { value: "Extra", label: "Extra" },
                        { value: "Ultra", label: "Ultra" },
                        { value: "Ultra Mega", label: "Ultra Mega" }
                    ]
                    onActivated: value => full.applet.apply(["fan", value])
                }
            }

            Section {
                title: "Iluminación"
                note: full.hw && full.hw.brightness ? "" : full.unavailable

                SegmentedRow {
                    Layout.fillWidth: true
                    enabled: full.controlsEnabled && full.hw.brightness !== null
                    current: full.hw ? full.hw.brightness : null
                    options: [
                        { value: "off", label: "Apagado" },
                        { value: "low", label: "Bajo" },
                        { value: "medium", label: "Medio" },
                        { value: "high", label: "Alto" }
                    ]
                    onActivated: value => full.applet.apply(["brightness", value])
                }

                // Solo si asusd confirma que admite la zona Lightbar.
                RowLayout {
                    Layout.fillWidth: true
                    visible: full.hw !== null && full.hw.lightbar !== null

                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        text: "Cinta LED"
                    }

                    PlasmaComponents.Switch {
                        enabled: full.controlsEnabled
                        checked: full.hw && full.hw.lightbar ? full.hw.lightbar.on : false
                        onToggled: {
                            const wanted = checked;
                            checked = Qt.binding(() => full.hw && full.hw.lightbar ? full.hw.lightbar.on : false);
                            full.applet.apply(["lightbar", wanted ? "on" : "off"]);
                        }
                    }
                }
            }

            Section {
                title: "Batería"

                PlasmaComponents.ProgressBar {
                    Layout.fillWidth: true
                    from: 0
                    to: 100
                    value: full.hw && full.hw.battery && full.hw.battery.percent !== null
                           ? full.hw.battery.percent : 0
                }

                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    text: full.batteryText()
                    opacity: 0.8
                    elide: Text.ElideRight
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing

                    PlasmaComponents.Label {
                        text: "Límite de carga"
                    }

                    SegmentedRow {
                        Layout.fillWidth: true
                        enabled: full.controlsEnabled && full.hw.chargeLimit !== null
                        current: full.hw ? full.hw.chargeLimit : null
                        options: [
                            { value: 60, label: "60 %" },
                            { value: 80, label: "80 %" },
                            { value: 100, label: "100 %" }
                        ]
                        onActivated: value => full.applet.apply(["charge-limit", value])
                    }
                }
            }

            Section {
                title: "Sensores"

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    // «—» indica un sensor no disponible.
                    SensorTile {
                        label: "°C CPU"
                        value: full.sensorValue(full.hw && full.hw.sensors.cpuTemp !== null
                                                ? Math.round(full.hw.sensors.cpuTemp) : null)
                    }
                    SensorTile {
                        label: "RPM CPU"
                        value: full.sensorValue(full.hw ? full.hw.sensors.cpuFan : null)
                    }
                    SensorTile {
                        label: "RPM GPU"
                        value: full.sensorValue(full.hw ? full.hw.sensors.gpuFan : null)
                    }
                    SensorTile {
                        label: "RPM central"
                        value: full.sensorValue(full.hw ? full.hw.sensors.midFan : null)
                    }
                }
            }

            PlasmaComponents.Label {
                Layout.fillWidth: true
                visible: !full.applet.messageIsError && full.applet.message !== ""
                text: "✓ " + full.applet.message
                opacity: 0.8
                wrapMode: Text.WordWrap
            }
        }
    }
}
