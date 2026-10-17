/* Contenido del popup: resumen, controles y sensores. */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras

PlasmaExtras.Representation {
    id: full

    required property var applet
    required property Texts texts

    readonly property var hw: applet.hw
    readonly property bool controlsEnabled: applet.available && !applet.busy
    readonly property string unavailable: i18n("Not available")

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
            parts.push(texts.powerSource(battery.acOnline));
        if (battery.status)
            parts.push(texts.chargingStatus(battery.status));
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
                        text: i18n("Performance profile")
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
                              ? i18n("%1 %", full.hw.battery.percent) : "—"
                    }

                    PlasmaComponents.Label {
                        Layout.alignment: Qt.AlignRight
                        text: full.hw && full.hw.battery && full.hw.battery.acOnline
                              ? i18nc("power source, short", "Plugged in")
                              : i18nc("power source, short", "Battery")
                        opacity: 0.7
                    }
                }
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                type: Kirigami.MessageType.Warning
                text: i18n("asusd is not responding. Controls are disabled.")
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
                        text: i18n("Close")
                        displayHint: Kirigami.DisplayHint.IconOnly
                        onTriggered: full.applet.clearMessage()
                    }
                ]
            }

            // --- Controles ----------------------------------------------------------
            Section {
                title: i18nc("section title", "Performance")
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
                    onActivated: value => full.applet.apply("profile", value)
                }
            }

            // Ventilación solo existe en Balanced; nunca se cambia el perfil para mostrarla.
            Section {
                visible: full.hw !== null && full.hw.profile === "Balanced"
                title: i18n("Fans")
                note: !full.hw || !full.hw.fans ? full.unavailable
                      : full.hw.fans.mode === null ? i18n("Custom curves") : ""

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
                    onActivated: value => full.applet.apply("fan", value)
                }
            }

            Section {
                title: i18n("Lighting")
                note: full.hw && full.hw.brightness ? "" : full.unavailable

                SegmentedRow {
                    Layout.fillWidth: true
                    enabled: full.controlsEnabled && full.hw.brightness !== null
                    current: full.hw ? full.hw.brightness : null
                    options: [
                        { value: "off", label: full.texts.brightness("off") },
                        { value: "low", label: full.texts.brightness("low") },
                        { value: "medium", label: full.texts.brightness("medium") },
                        { value: "high", label: full.texts.brightness("high") }
                    ]
                    onActivated: value => full.applet.apply("brightness", value)
                }

                // Solo si asusd confirma que admite la zona Lightbar.
                RowLayout {
                    Layout.fillWidth: true
                    visible: full.hw !== null && full.hw.lightbar !== null

                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        text: i18n("Lightbar")
                    }

                    PlasmaComponents.Switch {
                        enabled: full.controlsEnabled
                        checked: full.hw && full.hw.lightbar ? full.hw.lightbar.on : false
                        onToggled: {
                            const wanted = checked;
                            checked = Qt.binding(() => full.hw && full.hw.lightbar ? full.hw.lightbar.on : false);
                            full.applet.apply("lightbar", wanted ? "on" : "off");
                        }
                    }
                }
            }

            Section {
                title: i18n("Battery")

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
                        text: i18n("Charge limit")
                    }

                    SegmentedRow {
                        Layout.fillWidth: true
                        enabled: full.controlsEnabled && full.hw.chargeLimit !== null
                        current: full.hw ? full.hw.chargeLimit : null
                        options: [
                            { value: 60, label: i18n("%1 %", 60) },
                            { value: 80, label: i18n("%1 %", 80) },
                            { value: 100, label: i18n("%1 %", 100) }
                        ]
                        onActivated: value => full.applet.apply("charge-limit", value)
                    }
                }
            }

            Section {
                title: i18n("Sensors")

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    // «—» indica un sensor no disponible.
                    SensorTile {
                        label: i18nc("sensor tile caption", "°C CPU")
                        value: full.sensorValue(full.hw && full.hw.sensors.cpuTemp !== null
                                                ? Math.round(full.hw.sensors.cpuTemp) : null)
                    }
                    SensorTile {
                        label: i18nc("sensor tile caption", "RPM CPU")
                        value: full.sensorValue(full.hw ? full.hw.sensors.cpuFan : null)
                    }
                    SensorTile {
                        label: i18nc("sensor tile caption", "RPM GPU")
                        value: full.sensorValue(full.hw ? full.hw.sensors.gpuFan : null)
                    }
                    SensorTile {
                        label: i18nc("sensor tile caption, middle fan", "RPM mid")
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
