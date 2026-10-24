/* Contenido del popup: resumen, sensores y controles. */
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
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
    readonly property bool controlsEnabled: applet.available && applet.savingAvailable
                                           && !applet.savingControlsLocked && !applet.savingTransition
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
        return "battery-" + level + (battery.status === "Charging" ? "-charging" : "");
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
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

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

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        level: 5
                        text: i18n("Maximum battery saving")
                        opacity: 0.75
                    }
                    PlasmaComponents.Switch {
                        enabled: full.applet.savingAvailable && !full.applet.busy
                        checked: full.applet.savingChecked
                        onToggled: {
                            const wanted = checked;
                            checked = Qt.binding(() => full.applet.savingChecked);
                            full.applet.apply("power-saving", wanted ? "on" : "off");
                        }
                    }
                }

                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    wrapMode: Text.WordWrap
                    font: Kirigami.Theme.smallFont
                    opacity: 0.7
                    text: full.applet.savingTransition ? i18n("Applying changes…")
                          : full.applet.savingRestartRequired ? (full.applet.saving.restoring
                              ? i18n("Restart to restore your previous GPU mode.")
                              : i18n("Restart to finish switching to integrated graphics."))
                          : full.applet.saving && full.applet.saving.restoring ? i18n("Restoration incomplete. Retry to finish restoring your settings.")
                          : full.applet.savingActive ? i18n("Turn off to restore your previous settings, even after restarting.")
                          : i18n("Saves your current settings before reducing power consumption.")
                }

                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    visible: full.applet.savingActive
                    text: full.applet.saving ? full.texts.savingSettings(full.applet.saving) : ""
                    wrapMode: Text.WordWrap
                    font: Kirigami.Theme.smallFont
                    opacity: 0.8
                }

                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    visible: full.applet.saving && full.applet.saving.errors.length > 0
                    text: full.applet.saving ? full.applet.saving.errors.join("\n") : ""
                    wrapMode: Text.WrapAnywhere
                    color: Kirigami.Theme.negativeTextColor
                }

                PlasmaComponents.Button {
                    visible: full.applet.savingActive && full.applet.saving
                             && full.applet.savingRetryNeeded
                    enabled: !full.applet.busy
                    text: full.applet.saving && full.applet.saving.restoring
                          ? i18n("Retry restoration") : i18n("Retry battery saving")
                    onClicked: full.applet.apply("power-saving", full.applet.saving.restoring ? "off" : "on")
                }
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

                // Teclado: asusd expone un único brillo, compartido con la cinta LED.
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing

                    Kirigami.Icon {
                        // Iconos propios (plasmoid/icons): mismo estilo con cualquier tema de iconos.
                        source: "asus-control-keyboard-symbolic"
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: Kirigami.Units.iconSizes.smallMedium
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        RowLayout {
                            Layout.fillWidth: true

                            PlasmaComponents.Label {
                                Layout.fillWidth: true
                                text: i18n("Keyboard")
                            }

                            PlasmaComponents.Label {
                                text: full.live.brightness
                                      ? full.texts.brightness(full.applet.shown("brightness"))
                                      : full.unavailable
                                opacity: 0.7
                            }
                        }

                        BrightnessSlider {
                            Layout.fillWidth: true
                            enabled: full.controlsEnabled && full.live.brightness !== null
                            current: full.applet.shown("brightness")
                            onActivated: level => full.applet.apply("brightness", level)
                        }
                    }
                }

                // Cinta LED: solo si asusd confirma que admite la zona Lightbar. No tiene brillo
                // propio: sigue al del teclado.
                RowLayout {
                    Layout.fillWidth: true
                    visible: full.live.lightbar !== null
                    spacing: Kirigami.Units.largeSpacing

                    // Atenuado cuando la cinta está apagada.
                    Kirigami.Icon {
                        source: "asus-control-lightbar-symbolic"
                        opacity: full.applet.shown("lightbar") === "on" ? 1 : 0.5
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: Kirigami.Units.iconSizes.smallMedium
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        PlasmaComponents.Label {
                            Layout.fillWidth: true
                            text: i18n("Lightbar")
                        }

                        PlasmaComponents.Label {
                            Layout.fillWidth: true
                            text: i18n("Same brightness as the keyboard")
                            font: Kirigami.Theme.smallFont
                            opacity: 0.7
                            elide: Text.ElideRight
                        }
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
                note: full.live.chargeLimit !== null ? i18n("Charging stops at %1 %", full.applet.shown("charge-limit")) : ""

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
