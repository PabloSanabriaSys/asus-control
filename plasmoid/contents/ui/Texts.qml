/*
 * Textos que dependen de datos del backend: códigos de error y valores
 * de sysfs. El backend no envía frases; aquí se traducen con i18n() al idioma del sistema.
 * Los nombres de perfil (Quiet, Balanced, Performance) y de modo de ventilación son
 * nombres propios y no se traducen.
 */
import QtQuick

QtObject {
    function savingSettings(state) {
        const labels = {
            "desktop.policy": i18n("Screen off after 2 min; suspend after 10 min when supported"),
            "platform.autoAc": i18n("Automatic profile switching paused"),
            "fans.balanced": i18n("Automatic fans"),
            "lighting.lightbar": i18n("Lightbar off"),
            "display.refresh": i18n("Internal display at 60 Hz or lower"),
            "panel.overdrive": i18n("Panel overdrive off"),
            "lighting.keyboard": i18n("Keyboard lighting off"),
            "platform.profile": i18n("Quiet profile"),
            "battery.chargeLimit": i18n("Charge limit locked at 100 %"),
            "gpu.configuration": i18n("Integrated graphics active")
        };
        const parts = [];
        const checks = state.checks || [];
        for (const check of checks) {
            const key = check.key;
            if (state.restoring)
                continue;
            if (!(key in labels) || !check.confirmed || (state.pending || []).includes(key))
                continue;
            if (key === "fans.balanced" && !checks.some(c => c.key === "fans.quiet" && c.confirmed && !(state.pending || []).includes(c.key)))
                continue;
            if (key === "platform.autoAc" && !checks.some(c => c.key === "platform.autoBattery" && c.confirmed && !(state.pending || []).includes(c.key)))
                continue;
            parts.push(labels[key]);
        }
        const deferred = checks.filter(check => check.restartRequired);
        if (deferred.length > 0)
            parts.push(state.restoring ? i18n("Previous GPU mode queued for the next restart.")
                                      : i18n("Integrated graphics queued for the next restart."));
        if (checks.some(check => !check.confirmed && !check.restartRequired))
            parts.push(i18n("Some settings are not applied. Retry to apply battery saving."));
        if ((state.unavailable || []).includes("gpu.configuration"))
            parts.push(i18n("GPU switching unavailable or another GPU change is already queued."));
        const skipped = (state.unavailable || []).filter(key => !key.startsWith("gpu."));
        if (skipped.length > 0)
            parts.push(i18n("Unavailable settings: %1", skipped.join(", ")));
        return parts.join(" · ");
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
