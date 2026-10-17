/*
 * Applet de bandeja de ASUS Control.
 *
 * Toda la lógica de hardware vive en el backend Python (`asus-control`), que responde
 * con una línea JSON {ok, message, state}. Aquí solo se encolan órdenes y se muestra
 * el estado leído; nunca se marca un control antes de que la lectura lo confirme.
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
    readonly property int profileCheckMs: 10000
    readonly property int successMessageMs: 4000

    property var hw: null
    property bool busy: false
    property string message: ""
    property bool messageIsError: false

    property var queue: []
    property var running: null

    readonly property bool available: hw !== null && hw.asusdAvailable

    Plasmoid.icon: "asus-control"
    Plasmoid.status: PlasmaCore.Types.ActiveStatus
    toolTipMainText: "ASUS Control"
    toolTipSubText: tooltipText()
    switchWidth: Kirigami.Units.gridUnit * 16
    switchHeight: Kirigami.Units.gridUnit * 20

    fullRepresentation: FullRepresentation {
        applet: root
    }

    function tooltipText() {
        if (hw === null)
            return "Leyendo estado…";
        if (!hw.asusdAvailable)
            return "asusd no disponible";
        const parts = ["Perfil " + hw.profile];
        if (hw.battery && hw.battery.percent !== null)
            parts.push(hw.battery.percent + " %");
        if (hw.battery && hw.battery.acOnline !== null)
            parts.push(hw.battery.acOnline ? "Conectado a corriente" : "Con batería");
        return parts.join(" · ");
    }

    // --- Cola de órdenes: una sola a la vez ---------------------------------------

    function refresh() {
        if (!isQueued("state"))
            enqueue("state", false);
    }

    function checkProfile() {
        if (!isQueued("profile") && !isQueued("state"))
            enqueue("profile", false);
    }

    function apply(args) {
        if (busy)
            return;
        busy = true;
        enqueue("set " + args.map(quote).join(" "), true);
    }

    function clearMessage() {
        message = "";
        messageIsError = false;
    }

    function quote(value) {
        return "'" + String(value).replace(/'/g, "'\\''") + "'";
    }

    function isQueued(command) {
        return (running && running.command === command) || queue.some(item => item.command === command);
    }

    function enqueue(command, isAction) {
        queue = queue.concat([{ command: command, isAction: isAction }]);
        runNext();
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
        if (item.isAction)
            busy = false;
        handleResponse(item, exitCode, stdout, stderr);
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
            console.warn("asus-control falló:", exitCode, stderr);
            showMessage("No se pudo comunicar con el backend de ASUS Control.", true);
            return;
        }
        if (item.command === "profile") {
            // Cambio externo (otra herramienta o la conexión a corriente): leer todo.
            if (hw === null || response.state.profile !== hw.profile)
                refresh();
            return;
        }
        hw = response.state;
        if (item.isAction)
            showMessage(response.message, !response.ok);
    }

    function showMessage(text, isError) {
        message = text || "";
        messageIsError = isError;
        if (!isError)
            successTimer.restart();
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
        // Con el panel abierto: lectura completa cada 2 s (y al abrirlo).
        interval: root.panelRefreshMs
        running: root.expanded
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Timer {
        // Con el panel cerrado: solo el perfil, para reflejar cambios externos.
        interval: root.profileCheckMs
        running: !root.expanded
        repeat: true
        onTriggered: root.checkProfile()
    }

    Timer {
        id: successTimer

        interval: root.successMessageMs
        onTriggered: {
            if (!root.messageIsError)
                root.clearMessage();
        }
    }

    Component.onCompleted: refresh()
}
