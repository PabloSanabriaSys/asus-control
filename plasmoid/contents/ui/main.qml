/* Live asusd readings plus serialized, verified backend writes.
 * A deferred GPU restoration does not own the released manual controls.
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
    // Writes go through the backend to serialize them with battery-saving transitions.
    readonly property var saving: hw && hw.powerSaving ? hw.powerSaving : null
    readonly property bool savingActive: saving !== null && (saving.enabled || saving.restoring)
    readonly property bool savingAvailable: saving !== null && saving.available
    readonly property bool savingRestartRequired: saving !== null && (saving.checks || []).some(check => check.restartRequired)
    readonly property bool savingRetryNeeded: saving !== null && ((saving.errors || []).length > 0 || (saving.pending || []).some(key => !(saving.checks || []).some(check => check.key === key && check.restartRequired)))
    readonly property bool savingControlsLocked: saving !== null && (saving.enabled || (saving.restoring && savingRetryNeeded))
    readonly property bool savingTransition: "power-saving" in pending
    readonly property bool savingChecked: savingTransition ? pending["power-saving"].value === "on" : (saving !== null && saving.enabled)
    property bool panelVisible: false

    /** Respuesta del backend Python: ventilación, sensores y batería. */
    property var hw: null
    /** Cambios sin confirmar: {ajuste: {value}}. Se muestran en lugar del valor leído. */
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
        onVisibleChanged: root.panelVisible = visible
        Component.onCompleted: root.panelVisible = visible
        Component.onDestruction: root.panelVisible = false
    }

    readonly property Texts texts: Texts {}

    function tooltipText() {
        if (!live.available)
            return i18n("asusd is not available");
        if (!live.profile)
            return i18n("Reading state…");
        const parts = [i18n("Profile %1", live.profile)];
        if (saving !== null && saving.enabled)
            parts.push(i18n("Maximum battery saving"));
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
        if (setting !== "power-saving" && (savingControlsLocked || savingTransition || !savingAvailable))
            return;
        pending = Object.assign({}, pending, { [setting]: { value: value } });
        enqueueAction(setting, value);
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
            // La sección de ventilación depende del perfil: se relee el estado del backend.
            root.refresh();
        }
    }

    // --- Backend Python: una orden a la vez; las acciones van antes que las lecturas ---

    function refresh() {
        if (!isQueued("state"))
            queue = queue.concat([{ command: "state", setting: null }]);
        runNext();
    }

    function enqueueAction(setting, value) {
        const command = setting === "power-saving"
            ? "power-saving " + quote(value)
            : "set " + quote(setting) + " " + quote(value);
        const action = { command: command, setting: setting, value: value };
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
        if (item.command === "battery") {
            if (hw === null) {
                refresh();
                return;
            }
            hw = Object.assign({}, hw, { battery: response.state.battery });
            return;
        }
        hw = response.state;
        if (item.setting === "power-saving")
            live.refreshAll();
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
        running: root.expanded || root.panelVisible
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Timer {
        interval: 30000
        running: !root.expanded && !root.panelVisible
        repeat: true
        onTriggered: {
            if (!root.isQueued("battery")) {
                root.queue = root.queue.concat([{ command: "battery", setting: null }]);
                root.runNext();
            }
        }
    }

    Component.onCompleted: refresh()
}
