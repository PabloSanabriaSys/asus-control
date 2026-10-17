/*
 * Applet de bandeja de ASUS Control.
 *
 * Toda la lógica de hardware vive en el backend Python (`asus-control`), que responde
 * con una línea JSON {ok, error, state}. Aquí solo se encolan órdenes y se muestra
 * el estado leído; nunca se marca un control antes de que la lectura lo confirme.
 * Los textos se traducen con i18n() (ver Texts.qml).
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

    property var hw: null
    property bool busy: false
    /** Último error de una acción; vacío si no hay. Los cambios correctos no se anuncian. */
    property string errorMessage: ""

    property var queue: []
    property var running: null

    readonly property bool available: hw !== null && hw.asusdAvailable

    Plasmoid.icon: "asus-control"
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
        if (hw === null)
            return i18n("Reading state…");
        if (!hw.asusdAvailable)
            return i18n("asusd is not available");
        const parts = [i18n("Profile %1", hw.profile)];
        if (hw.battery && hw.battery.percent !== null)
            parts.push(i18n("%1 %", hw.battery.percent));
        if (hw.battery && hw.battery.acOnline !== null)
            parts.push(texts.powerSource(hw.battery.acOnline));
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

    function apply(setting, value) {
        if (busy)
            return;
        busy = true;
        enqueue("set " + quote(setting) + " " + quote(value), true);
    }

    function clearError() {
        errorMessage = "";
    }

    function quote(value) {
        return "'" + String(value).replace(/'/g, "'\\''") + "'";
    }

    function isQueued(command) {
        return (running && running.command === command) || queue.some(item => item.command === command);
    }

    /** `isAction`: cambio de un ajuste (bloquea los controles) frente a una lectura. */
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
            console.warn("asus-control failed:", exitCode, stderr);
            errorMessage = texts.backendFailure();
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

    Component.onCompleted: refresh()
}
