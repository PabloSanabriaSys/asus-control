/* Live, read-only asusd state. All writes go through the backend and its locks.
 * PlatformProfile: 0 Balanced, 1 Performance, 2 Quiet; Brightness: 0..3.
 */
import QtQuick
import org.kde.plasma.workspace.dbus as DBus

Item {
    id: live

    readonly property string service: "xyz.ljones.Asusd"
    readonly property var profileCodes: ({ "Balanced": 0, "Performance": 1, "Quiet": 2 })
    readonly property var brightnessCodes: ({ "off": 0, "low": 1, "medium": 2, "high": 3 })
    readonly property int lightbarZone: 2

    property string auraPath: ""

    readonly property bool available: watcher.registered
    readonly property var profile: available ? keyOf(profileCodes, unwrap(platform.properties.PlatformProfile)) : null
    readonly property var chargeLimit: available ? unwrap(platform.properties.ChargeControlEndThreshold) : null
    readonly property var brightness: available && auraPath ? keyOf(brightnessCodes, unwrap(aura.properties.Brightness)) : null
    /** {boot, awake, sleep, shutdown} o null si asusd no admite la cinta. */
    readonly property var lightbar: available && auraPath ? lightbarState() : null

    // Última lectura válida de LedPower: entre un PropertiesChanged y su relectura el valor
    // llega vacío durante un instante, y la cinta no debe parpadear en la interfaz.
    readonly property var ledPowerRead: entriesOf(aura.properties.LedPower)
    property var ledPower: []
    onLedPowerReadChanged: {
        if (ledPowerRead.length > 0)
            ledPower = ledPowerRead;
    }

    DBus.DBusServiceWatcher {
        id: watcher

        busType: DBus.BusType.System
        watchedService: live.service
        // Si asusd se reinicia (p. ej. lightbar-fix.sh), se vuelve a leer todo.
        onRegisteredChanged: {
            if (!registered)
                return;
            live.discoverAura();
            platform.updateAll();
            if (live.auraPath)
                aura.updateAll();
        }
    }

    DBus.Properties {
        id: platform

        busType: DBus.BusType.System
        service: live.service
        path: "/xyz/ljones"
        iface: "xyz.ljones.Platform"
    }

    DBus.Properties {
        id: aura

        busType: DBus.BusType.System
        service: live.service
        path: live.auraPath
        iface: "xyz.ljones.Aura"

        // El módulo decodifica bien las estructuras con Get/GetAll, pero no las que llegan
        // en PropertiesChanged (quedan como ""): LedPower se relee explícitamente.
        onPropertiesChanged: (interfaceName, changed, invalidated) => {
            if ("LedPower" in changed || invalidated.indexOf("LedPower") !== -1)
                Qt.callLater(() => aura.update("LedPower"));
        }
    }

    function refreshAll() {
        platform.updateAll();
        if (auraPath)
            aura.updateAll();
    }

    function discoverAura() {
        const reply = DBus.SystemBus.asyncCall({
            service: service,
            path: "/",
            iface: "org.freedesktop.DBus.ObjectManager",
            member: "GetManagedObjects"
        });
        reply.finished.connect(() => {
            if (reply.isError) {
                console.warn("ASUS Control: no se encontró el dispositivo Aura:", reply.error.message);
                return;
            }
            const paths = Object.keys(reply.value || {}).filter(path => path.indexOf("/xyz/ljones/aura/") === 0);
            auraPath = paths.length > 0 ? paths[0] : "";
        });
    }

    function lightbarState() {
        const zones = aura.properties.SupportedPowerZones;
        if (!isList(zones) || !Array.from(zones, unwrap).includes(lightbarZone))
            return null;
        const entry = ledPower.find(item => item[0] === lightbarZone);
        return entry ? { boot: entry[1], awake: entry[2], sleep: entry[3], shutdown: entry[4] } : null;
    }

    /**
     * Entradas [zona, arranque, activo, suspensión, apagado] de LedPower. Según venga de
     * GetAll o de Get, la lista llega con uno o dos niveles de anidamiento extra.
     */
    function entriesOf(value) {
        while (isList(value) && value.length === 1 && isList(value[0]) && isList(value[0][0]))
            value = value[0];
        if (!isList(value))
            return [];
        const entries = [];
        for (let i = 0; i < value.length; ++i) {
            const entry = value[i];
            if (isList(entry))
                entries.push([unwrap(entry[0]), entry[1], entry[2], entry[3], entry[4]]);
        }
        return entries;
    }

    /** Las listas de D-Bus llegan como secuencias de Qt: Array.isArray() no las reconoce. */
    function isList(value) {
        return value !== null && typeof value === "object" && typeof value.length === "number";
    }

    /** Los enteros sin signo llegan envueltos ({value: n}). */
    function unwrap(value) {
        return value !== null && typeof value === "object" && "value" in value ? value.value : value;
    }

    function keyOf(codes, code) {
        for (const key in codes) {
            if (codes[key] === code)
                return key;
        }
        return null;
    }

    Component.onCompleted: discoverAura()
}
