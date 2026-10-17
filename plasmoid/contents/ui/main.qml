/*
 * Applet de bandeja de ASUS Control.
 *
 * Dos fuentes de datos:
 *  - AsusdLive: asusd por D-Bus desde QML (perfil, brillo, límite de carga, cinta LED),
 *    en vivo y con escrituras directas.
 *  - Backend Python (`asus-control`): ventilación, que necesita el bloqueo compartido con
 *    alternar-ventilacion y la recuperación ante fallos, y sensores/batería (sysfs).
 *
 * Un cambio se muestra al instante como «pendiente» y se confirma con la lectura posterior:
 * el aviso de cambio de asusd o la respuesta verificada del backend. Si no llega a tiempo,
 * el control vuelve al valor real y se muestra el error. Textos en Texts.qml (i18n).
 */
import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.plasmoid

PlasmoidItem {
    id: root

    readonly property string backend: "\"$HOME/.local/bin/asus-control\""
    readonly property int panelRefreshMs: 2000
    readonly property int confirmTimeoutMs: 3000
    /** Ajustes que se escriben directamente en asusd; el resto pasa por el backend. */
    readonly property var liveSettings: ["profile", "brightness", "charge-limit", "lightbar"]

    /** Respuesta del backend Python: ventilación, sensores y batería. */
    property var hw: null
    /** Cambios sin confirmar: {ajuste: {value, deadline}}. Se muestran en lugar del valor leído. */
    property var pending: ({})
    readonly property bool busy: Object.keys(pending).length > 0
    /** Último error de una acción; vacío si no hay. Los cambios correctos no se anuncian. */
    property string errorMessage: ""

    property var queue: []
    property var running: null

    readonly property AsusdLive live: AsusdLive {}
    readonly property bool available: live.available

    Plasmoid.icon: "asus-control-symbolic"
    Plasmoid.status: PlasmaCore.Types.ActiveStatus
    toolTipMainText: i18n("ASUS Control")
    toolTipSubText: tooltipText()
    switchWidth: Kirigami.Units.gridUnit * 16
    switchHeight: Kirigami.Units.gridUnit * 20

    fullRepresentation: FullRepresentation {
        applet: root
        texts: root.texts
    }

    readonly property Texts texts: Texts {}

    function tooltipText() {
        if (!live.available)
            return i18n("asusd is not available");
        const parts = [i18n("Profile %1", live.profile)];
        const battery = hw ? hw.battery : null;
        if (battery && battery.percent !== null)
            parts.push(i18n("%1 %", battery.percent));
        if (battery && battery.acOnline !== null)
            parts.push(texts.powerSource(battery.acOnline));
        return parts.join(" · ");
    }

    /** Valor leído de cada ajuste, en el formato que usan los controles. */
    function actual(setting) {
        switch (setting) {
        case "profile":
            return live.profile;
        case "brightness":
            return live.brightness;
        case "charge-limit":
            return live.chargeLimit;
        case "lightbar":
            return live.lightbar ? (live.lightbar.awake ? "on" : "off") : null;
        case "fan":
            return hw && hw.fans ? hw.fans.mode : null;
        }
        return null;
    }

    /** Valor que debe mostrar un control: el pendiente si lo hay; si no, el leído. */
    function shown(setting) {
        return setting in pending ? pending[setting].value : actual(setting);
    }

    function apply(setting, value) {
        pending = Object.assign({}, pending, { [setting]: { value: value, deadline: Date.now() + confirmTimeoutMs } });
        if (liveSettings.indexOf(setting) !== -1)
            writeLive(setting, value);
        else
            enqueueAction(setting, value);
    }

    function writeLive(setting, value) {
        switch (setting) {
        case "profile":
            live.setProfile(value);
            break;
        case "brightness":
            live.setBrightness(value);
            break;
        case "charge-limit":
            live.setChargeLimit(value);
            break;
        case "lightbar":
            live.setLightbarAwake(value === "on");
            break;
        }
    }

    /** Confirma los cambios directos cuando asusd ya refleja el valor; caduca los vencidos. */
    function checkPending() {
        const now = Date.now();
        let changed = false;
        const rest = Object.assign({}, pending);
        for (const setting of liveSettings) {
            if (!(setting in rest))
                continue;
            if (actual(setting) === rest[setting].value) {
                delete rest[setting];
                changed = true;
            } else if (now > rest[setting].deadline) {
                delete rest[setting];
                changed = true;
                errorMessage = texts.error({ code: "notConfirmed", setting: setting });
            }
        }
        if (changed)
            pending = rest;
    }

    function dropPending(setting) {
        const rest = Object.assign({}, pending);
        delete rest[setting];
        pending = rest;
    }

    function clearError() {
        errorMessage = "";
    }

    Connections {
        target: root.live

        function onProfileChanged() {
            root.checkPending();
            // La sección de ventilación depende del perfil: se relee el estado del backend.
            root.refresh();
        }
        function onBrightnessChanged() {
            root.checkPending();
        }
        function onChargeLimitChanged() {
            root.checkPending();
        }
        function onLightbarChanged() {
            root.checkPending();
        }
        function onWriteFailed(setting, detail) {
            root.dropPending(setting);
            root.errorMessage = root.texts.error({ code: "hardwareAccess", detail: detail });
        }
    }

    Timer {
        // Caducidad de los cambios directos que asusd no confirma.
        interval: 250
        running: root.busy
        repeat: true
        onTriggered: root.checkPending()
    }

    // --- Backend Python: una orden a la vez; las acciones van antes que las lecturas ---

    function refresh() {
        if (!isQueued("state"))
            queue = queue.concat([{ command: "state", setting: null }]);
        runNext();
    }

    function enqueueAction(setting, value) {
        const action = { command: "set " + quote(setting) + " " + quote(value), setting: setting, value: value };
        // Si el mismo ajuste ya esperaba en la cola, solo cuenta el último valor.
        const others = queue.filter(item => item.setting !== setting);
        const firstRead = others.findIndex(item => item.setting === null);
        queue = firstRead === -1 ? others.concat([action])
                                 : others.slice(0, firstRead).concat([action], others.slice(firstRead));
        runNext();
    }

    function quote(value) {
        return "'" + String(value).replace(/'/g, "'\\''") + "'";
    }

    function isQueued(command) {
        return (running && running.command === command) || queue.some(item => item.command === command);
    }

    function runNext() {
        if (running !== null || queue.length === 0)
            return;
        running = queue[0];
        queue = queue.slice(1);
        executable.connectSource(backend + " " + running.command);
    }

    function finish(exitCode, stdout, stderr) {
        const item = running;
        running = null;
        handleResponse(item, exitCode, stdout, stderr);
        // La respuesta del backend ya viene verificada: retira el pendiente, salvo que el
        // usuario haya elegido otro valor después.
        if (item.setting !== null && item.setting in pending && pending[item.setting].value === item.value)
            dropPending(item.setting);
        runNext();
    }

    function handleResponse(item, exitCode, stdout, stderr) {
        let response = null;
        try {
            response = exitCode === 0 ? JSON.parse(stdout) : null;
        } catch (error) {
            response = null;
        }
        if (response === null) {
            console.warn("asus-control failed:", exitCode, stderr);
            errorMessage = texts.backendFailure();
            return;
        }
        hw = response.state;
        if (item.setting !== null)
            errorMessage = response.ok ? "" : texts.error(response.error);
    }

    P5Support.DataSource {
        id: executable

        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source);
            root.finish(data["exit code"], data["stdout"], data["stderr"]);
        }
    }

    Timer {
        // Con el panel abierto: sensores, batería y ventilación cada 2 s (y al abrirlo).
        // Perfil, brillo, límite y cinta no se sondean: llegan en vivo por D-Bus.
        interval: root.panelRefreshMs
        running: root.expanded
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Component.onCompleted: refresh()
}
