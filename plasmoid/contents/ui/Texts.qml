/*
 * Textos que dependen de datos del backend: confirmaciones, códigos de error y valores
 * de sysfs. El backend no envía frases; aquí se traducen con i18n() al idioma del sistema.
 * Los nombres de perfil (Quiet, Balanced, Performance) y de modo de ventilación son
 * nombres propios y no se traducen.
 */
import QtQuick

QtObject {
    function success(setting, value) {
        switch (setting) {
        case "profile":
            return i18n("Profile %1 active.", value);
        case "fan":
            return i18n("Fan mode %1 active.", value);
        case "brightness":
            return i18n("Lighting: %1.", brightness(value));
        case "charge-limit":
            return i18n("Charge limit: %1 %.", value);
        case "lightbar":
            return value === "on" ? i18n("Lightbar on.") : i18n("Lightbar off.");
        }
        return "";
    }

    function error(details) {
        switch (details.code) {
        case "fanRequiresBalanced":
            return i18n("Fan modes can only be changed in Balanced. The profile was not changed.");
        case "fanModeFailed":
            return details.restored
                ? i18n("Could not apply %1. Automatic fan control was restored.", details.mode)
                : i18n("Could not apply %1, and automatic fan control could not be restored.", details.mode);
        case "fanChangeInProgress":
            return i18n("Another fan change is in progress.");
        case "lightbarUnsupported":
            return i18n("asusd does not support the lightbar on this device.");
        case "notConfirmed":
            return i18n("Could not confirm the new %1.", settingName(details.setting));
        case "hardwareAccess":
            return i18n("Could not access the hardware: %1", details.detail);
        }
        return i18n("Unexpected error: %1", details.detail || details.code);
    }

    function backendFailure() {
        return i18n("Could not communicate with the ASUS Control backend.");
    }

    function settingName(setting) {
        switch (setting) {
        case "profile":
            return i18nc("setting name inside a sentence", "profile");
        case "fan":
            return i18nc("setting name inside a sentence", "fan mode");
        case "brightness":
            return i18nc("setting name inside a sentence", "lighting level");
        case "charge-limit":
            return i18nc("setting name inside a sentence", "charge limit");
        case "lightbar":
            return i18nc("setting name inside a sentence", "lightbar state");
        }
        return setting;
    }

    function brightness(level) {
        switch (level) {
        case "off":
            return i18nc("lighting level", "Off");
        case "low":
            return i18nc("lighting level", "Low");
        case "medium":
            return i18nc("lighting level", "Medium");
        case "high":
            return i18nc("lighting level", "High");
        }
        return level;
    }

    function chargingStatus(status) {
        switch (status) {
        case "Charging":
            return i18nc("battery status", "Charging");
        case "Discharging":
            return i18nc("battery status", "Discharging");
        case "Not charging":
            return i18nc("battery status", "Not charging");
        case "Full":
            return i18nc("battery status", "Full");
        }
        return status;
    }

    function powerSource(acOnline) {
        return acOnline ? i18n("Plugged in") : i18n("On battery");
    }
}
