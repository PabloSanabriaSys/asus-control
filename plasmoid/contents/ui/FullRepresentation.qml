/* Contenido del popup: resumen, sensores y controles. */
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
    readonly property var battery: hw ? hw.battery : null
    readonly property var live: applet.live
    // Los controles no se bloquean mientras se aplica un cambio: muestran el valor pendiente.
    readonly property bool controlsEnabled: applet.available
    readonly property var profile: applet.shown("profile")
    readonly property string unavailable: i18n("Not available")

    Layout.minimumWidth: Kirigami.Units.gridUnit * 18
    Layout.preferredWidth: Kirigami.Units.gridUnit * 20
    Layout.preferredHeight: Kirigami.Units.gridUnit * 24

    function sensorValue(value) {
        return value === null || value === undefined ? "—" : String(value);
    }

    /** Icono de Breeze por decenas: battery-060, battery-060-charging… */
    function batteryIcon() {
        if (!battery || battery.percent === null)
            return "battery-missing";
        const level = String(Math.round(battery.percent / 10) * 10).padStart(3, "0");
        return "battery-" + level + (battery.acOnline ? "-charging" : "");
    }

    function batteryStatusText() {
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

            // --- Resumen: perfil y batería ------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing

                Kirigami.Icon {
                    source: "asus-control-symbolic"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }

                ColumnLayout {
                    spacing: 0

                    Kirigami.Heading {
                        level: 2
                        text: full.profile || full.unavailable
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

                    RowLayout {
                        Layout.alignment: Qt.AlignRight
                        spacing: Kirigami.Units.smallSpacing

                        Kirigami.Icon {
                            source: full.batteryIcon()
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        }

                        Kirigami.Heading {
                            level: 2
                            text: full.battery && full.battery.percent !== null
                                  ? i18n("%1 %", full.battery.percent) : "—"
                        }
                    }

                    PlasmaComponents.Label {
                        Layout.alignment: Qt.AlignRight
                        text: full.batteryStatusText()
                        font: Kirigami.Theme.smallFont
                        opacity: 0.7
                    }
                }
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                type: Kirigami.MessageType.Warning
                text: i18n("asusd is not responding. Controls are disabled.")
                visible: !full.live.available
            }

            // Solo errores: el resultado de un cambio correcto ya se ve en los controles.
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                type: Kirigami.MessageType.Error
                text: full.applet.errorMessage
                visible: full.applet.errorMessage !== ""
                actions: [
                    Kirigami.Action {
                        icon.name: "dialog-close"
                        text: i18n("Close")
                        displayHint: Kirigami.DisplayHint.IconOnly
                        onTriggered: full.applet.clearError()
                    }
                ]
            }

            // --- Sensores -----------------------------------------------------------
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

            // --- Controles ----------------------------------------------------------
            Section {
                title: i18nc("section title", "Performance")
                note: full.applet.available ? "" : full.unavailable

                SegmentedRow {
                    Layout.fillWidth: true
                    enabled: full.controlsEnabled
                    current: full.profile
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
                visible: full.profile === "Balanced"
                title: i18n("Fans")
                note: !full.hw || !full.hw.fans ? full.unavailable
                      : full.hw.fans.mode === null ? i18n("Custom curves") : ""

                SegmentedRow {
                    Layout.fillWidth: true
                    enabled: full.controlsEnabled && full.hw !== null && full.hw.fans !== null
                    current: full.applet.shown("fan")
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
                note: full.live.brightness ? "" : full.unavailable

                // asusctl expone un único brillo compartido por el teclado y la iluminación.
                BrightnessSlider {
                    Layout.fillWidth: true
                    enabled: full.controlsEnabled && full.live.brightness !== null
                    texts: full.texts
                    current: full.applet.shown("brightness")
                    onActivated: level => full.applet.apply("brightness", level)
                }

                // Solo si asusd confirma que admite la zona Lightbar; la cinta no tiene brillo propio.
                RowLayout {
                    Layout.fillWidth: true
                    visible: full.live.lightbar !== null

                    Kirigami.Icon {
                        source: full.applet.shown("lightbar") === "on"
                                ? "flashlight-on" : "flashlight-off"
                        implicitWidth: Kirigami.Units.iconSizes.small
                        implicitHeight: Kirigami.Units.iconSizes.small
                    }

                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        text: i18n("Lightbar")
                    }

                    PlasmaComponents.Switch {
                        enabled: full.controlsEnabled
                        checked: full.applet.shown("lightbar") === "on"
                        onToggled: {
                            const wanted = checked;
                            checked = Qt.binding(() => full.applet.shown("lightbar") === "on");
                            full.applet.apply("lightbar", wanted ? "on" : "off");
                        }
                    }
                }
            }

            Section {
                title: i18n("Charge limit")

                SegmentedRow {
                    Layout.fillWidth: true
                    enabled: full.controlsEnabled && full.live.chargeLimit !== null
                    current: full.applet.shown("charge-limit")
                    options: [
                        { value: 60, label: i18n("%1 %", 60) },
                        { value: 80, label: i18n("%1 %", 80) },
                        { value: 100, label: i18n("%1 %", 100) }
                    ]
                    onActivated: value => full.applet.apply("charge-limit", value)
                }
            }
        }
    }
}
