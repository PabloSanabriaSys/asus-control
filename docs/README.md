# Documentación técnica

## Arquitectura

ASUS Control tiene dos partes:

- **El applet** (`plasmoid/`, QML): la interfaz de la bandeja. Lee los ajustes simples de asusd por D-Bus en vivo y envía todas las escrituras al backend.
- **El backend** (`src/asus_control/`, Python sin dependencias externas): coordina las escrituras, la ventilación, el ahorro reversible y la lectura de sensores y batería. El applet lo ejecuta como orden: `asus-control state` o `asus-control set …`, que responden con una línea JSON.

```
                    ┌── D-Bus (en vivo) ──▶ asusd: perfil, brillo, límite de carga, cinta LED
plasmoid/ (QML) ────┤
                    └── sh ──▶ asus-control ──▶ asusd + KDE/PowerDevil + sysfs
```

| Ajuste | Lectura | Escritura | Confirmación |
|---|---|---|---|
| Perfil, brillo, límite de carga, cinta LED | `AsusdLive.qml` (`DBus.Properties`), en vivo por `PropertiesChanged` | `asus-control set …` | lectura posterior verificada por el backend |
| Ventilación | backend (`asus-control state`) | backend (`asus-control set fan …`) | respuesta verificada del backend |
| Sensores y batería | backend, cada 2 s con el popup o ventana visibles; batería sola cada 30 s con el panel cerrado | — | — |
| Ahorro | estado persistente del backend | `asus-control power-saving on/off` | verificación de cada ajuste y conservación del respaldo |

### Backend por capas

| Capa | Contenido | Puede importar |
|---|---|---|
| `domain/` | `models.py` (enums y dataclasses inmutables), `errors.py`, `fan_modes.py` (curvas y detección del modo) | nada |
| `application/` | `ports.py` (`PlatformPort`, `LightbarPort`, `SensorPort`, `FanLock`), `fan_service.py`, `hardware_service.py` | `domain` |
| `infrastructure/` | `asusd.py` (adaptadores sobre D-Bus), `busctl.py` (cliente D-Bus), `sysfs.py`, `fan_lock.py`, `process.py`, `errors.py` | `domain`, `application` |
| `presentation/` | `cli.py` (órdenes), `serialization.py` (estado y errores a JSON) | `domain`, `application` |
| `bootstrap.py` | Raíz de composición: crea los adaptadores y los inyecta en los servicios | todo |

- **Regla de dependencias:** las dependencias apuntan hacia dentro. `tests/test_architecture.py` la hace cumplir analizando los imports, y además comprueba que el dominio no haga E/S.
- **Puertos y adaptadores:** la aplicación define con `Protocol` lo que necesita y mypy verifica que cada adaptador lo cumpla.
  - `AsusdPlatform` implementa `PlatformPort`.
  - `AsusdLightbar` implementa `LightbarPort`.
  - `SysfsSensors` implementa `SensorPort`.
  - `fan_lock` implementa `FanLock`.
- **Errores:** la aplicación solo conoce `HardwareAccessError`; la infraestructura lanza sus subclases (`CommandError`, `ParseError`). Los errores del dominio llevan datos estructurados, no textos.
- **CLI:**
  - Solo acepta valores cerrados, derivados de los enums.
  - Un error esperado devuelve `ok: false` con un código estable y el estado actual.
  - Un error no previsto devuelve código de salida 1, con la traza en stderr.
- **Verificación:** cada cambio se confirma con una lectura posterior; si no coincide, se lanza `VerificationError`.

El applet usa `set profile|brightness|charge-limit|lightbar|fan` y `power-saving on|off`. Las escrituras manuales toman el bloqueo del ahorro. Todos los ajustes manuales, incluido `charge-limit`, se rechazan mientras exista una sesión activa o una restauración pendiente. Las lecturas no escriben.

### Applet

- **`main.qml`:** coordina el applet.
  - Guarda los cambios pendientes (`pending`): el valor elegido se muestra al instante y los demás controles siguen disponibles. Al confirmarse, se muestra el valor leído; si falla, el control vuelve al valor real y aparece el error.
  - Gestiona la cola de órdenes del backend: una a la vez, las acciones antes que las lecturas, y solo el último valor si se cambia el mismo ajuste varias veces seguidas.
- **`AsusdLive.qml`:** lecturas en vivo de asusd; no escribe.
  - Descubre solo la ruta del dispositivo Aura (`GetManagedObjects`).
  - Si asusd se reinicia, vuelve a leer todo.
- **`FullRepresentation.qml`:** el popup. Usa los componentes `Section`, `SegmentedRow`, `BrightnessSlider` y `SensorTile`.
- **`Texts.qml`:** textos que dependen de datos (códigos de error, estado de la batería). Ver [Idiomas](#idiomas).
- **Iconos** (`plasmoid/icons/`):
  - `asus-control.svg` es el icono a color para el lanzador.
  - Los `*-symbolic.svg` son monocromos y Plasma los colorea según el tema (clase `ColorScheme-Text`): el logo de la bandeja y los iconos de teclado y cinta.
  - Tienen nombres propios para que ningún tema de iconos los sustituya.

**Limitaciones del módulo QML de D-Bus de Plasma** (`org.kde.plasma.workspace.dbus`), y cómo se sortean:

| Limitación | Solución |
|---|---|
| No puede enviar `uint32` ni `byte` dentro de un `variant`, y escribir en su mapa de propiedades no llega al bus | Las escrituras se delegan al backend |
| No envía estructuras | LedPower y las curvas se escriben desde el backend |
| Las estructuras que llegan en `PropertiesChanged` quedan vacías | `LedPower` se relee con `update()` y se conserva la última lectura válida |
| Los enteros sin signo llegan envueltos (`{value: n}`) | Se desenvuelven al leer |
| Las listas son secuencias de Qt (`Array.isArray()` devuelve `false`) | Se comprueban como objetos con `length` |

## Fuentes de datos

Los controles ASUS pasan por la interfaz D-Bus de asusd (servicio `xyz.ljones.Asusd`), la misma que usa `asusctl`. El backend la consulta con `busctl --json=short`.

| Dato | Origen |
|---|---|
| Perfil | `Platform.PlatformProfile` (0 Balanced, 1 Performance, 2 Quiet). Los perfiles predeterminados OnAc/OnBattery no se tocan; el ahorro respalda y pausa los booleanos ChangePlatformProfileOnAc/OnBattery. |
| Límite de carga | `Platform.ChargeControlEndThreshold` |
| Brillo | `Aura.Brightness` (0 Off … 3 High) |
| Cinta LED | `Aura.SupportedPowerZones` y `Aura.LedPower`. `LedPower` se escribe completo, conservando la zona del teclado. |
| Ventilación | `FanCurves.FanCurveData`, `SetFanCurve` y `SetFanCurvesEnabled` sobre Balanced (código 0) |
| Sensores | sysfs: hwmon `asus` (`cpu_fan`, `gpu_fan`, `mid_fan`) y `coretemp` (`Package id 0`) |
| Batería | sysfs: `power_supply` con `type=Battery` (excepto periféricos, `scope=Device`) y `type=Mains` |

- Los códigos y la forma de las respuestas se verificaron en el equipo y están en `tests/fixtures/dbus_*.json`.
- Los dispositivos de sysfs se buscan por `name`, `*_label` y `type`, nunca por su número, que cambia entre arranques.

## Ahorro reversible

- `domain/power_saving.py`: sesión inmutable con intención de encendido/apagado, valores originales, objetivos y ajustes pendientes.
- `application/power_saving_service.py`: captura primero, persiste antes de escribir y confirma cada cambio. La reactivación y reconciliación reutilizan el respaldo original. La restauración conserva los fallos pendientes y verifica todo el conjunto antes de liberar el respaldo.
- `infrastructure/power_saving_store.py`: JSON con versión 1 bajo `XDG_STATE_HOME`, archivo 0600 y directorio 0700 al crearlo. Usa archivo temporal, `fsync`, reemplazo atómico y sincronización del directorio. Un esquema desconocido o un archivo dañado genera un error sin sobrescribirlo.
- `infrastructure/power_saving_device.py`: registro de ajustes reversibles de asusd y KDE. Cada ajuste modificado tiene lectura, escritura, valor original y objetivo. Las curvas guardan puntos y activación por ventilador, incluidos estados personalizados y Quiet.
- `infrastructure/kde_power.py`: frecuencia mediante `kscreen-doctor`, conservando resolución y resolviendo modos por conector/tamaño/Hz después de cada arranque. Solo cambia las entradas administradas de `powerdevilrc`, conserva las entradas ausentes como tales y recarga PowerDevil por D-Bus. El brillo solo conserva compatibilidad de restauración para respaldos antiguos; no se aplica en sesiones nuevas.
- `infrastructure/power_saving_watch.py`: servicio de usuario ligado a `graphical-session.target`. Cada 15 s comprueba estado persistente y, solo si existe una sesión guardada, conexión AC y reanudación mediante CLOCK_BOOTTIME. Reconcilia al iniciar, reanudar, cambiar AC, encontrar pendientes o cada minuto. Sin cambios necesarios, no vuelve a escribir el respaldo.

La política de PowerDevil usa los mismos valores en AC, Battery y LowBattery durante el ahorro. Se suspende a RAM tras 600 s solo si logind devuelve `CanSuspend=yes`, y se apaga la pantalla tras 120 s. Los inhibidores y capacidades siguen a cargo de KDE. La acción de la tapa y los ajustes de brillo/frecuencia de monitores externos permanecen fuera del conjunto administrado. El límite de carga se respalda y se fuerza a 100 %.

El bloqueo `asus-control-power-saving.lock` admite una espera acotada de 3 s para que un clic no falle inmediatamente cuando el servicio está verificando. Serializa las escrituras manuales con las transiciones del ahorro. Las transiciones además toman `alternar-ventilacion.lock` para no competir con el script externo de ventilación; los bloqueos se adquieren siempre en ese orden.

El estado JSON añade `powerSaving` con `available`, `enabled`, `restoring`, `pending`, `settings`, `unavailable`, `errors` y `checks` (incluido `restartRequired`) (objetivo, lectura actual y confirmación por ajuste). `power-saving audit` y `state` comparan valores reales sin escribir; no usan el respaldo como prueba de que un ajuste sigue aplicado. Un fallo esperado conserva la convención CLI de salida 0 con `ok:false`; los scripts deben examinar el JSON. El instalador preserva el respaldo en actualizaciones y el desinstalador aborta si no logra restaurar.

Las claves de PowerDevil se contrastaron con su [esquema oficial](https://github.com/KDE/powerdevil/blob/master/PowerDevilProfileSettings.kcfg), y las interfaces D-Bus se verificaron por introspección en el G615JH con asusd 6.5.0.

### Recuperación y actualización desde 0.4.0

El control de brillo de pantalla y la opción CLI `--brightness` se retiraron. No se captura ni aplica `display.brightness` en sesiones nuevas. Si existe un respaldo de 0.4.0, el servicio conserva la compatibilidad necesaria para restaurar ese valor una sola vez antes de eliminarlo del respaldo. Si falla, lo conserva para reintentar. La migración no sustituye los originales de los demás ajustes.

Un ajuste pendiente cuya escritura guardó un valor pero falló en una operación posterior (por ejemplo, recargar PowerDevil) debe repetir la escritura completa al reintentar. Una lectura coincidente no basta para dar esa operación por terminada.

El applet comunica la visibilidad de `FullRepresentation` al coordinador: `PlasmoidItem.expanded` por sí solo no cubre `plasmawindowed`. El refresco de batería con el panel cerrado utiliza una orden `battery` separada y combina su respuesta con el estado existente.

## Ventilación

- **Modos:**
  - Normal desactiva las curvas personalizadas, con lo que vuelve el control automático.
  - Extra, Ultra y Ultra Mega escriben tres curvas fijas (CPU, GPU y central) sobre 8 temperaturas.
- **Solo en Balanced:** fuera de Balanced, el cambio se rechaza sin tocar el perfil.
- **Secuencia:**
  1. Tomar el bloqueo.
  2. Revalidar que el perfil sea Balanced.
  3. Escribir las curvas y activarlas.
  4. Volver a leer y comparar.
- **Recuperación:** si falla cualquier paso posterior a la revalidación, se desactivan las curvas, se comprueba que vuelva el control automático y se informa de si se logró.
- **Curvas desconocidas:** si las curvas activas no coinciden con ningún modo, el applet indica «Curvas personalizadas» y no marca ningún botón.

### Compatibilidad con `alternar-ventilacion` (opcional)

Las curvas de `domain/fan_modes.py` son las del script personal `~/.local/bin/alternar-ventilacion`, que alterna los mismos modos con un atajo de teclado. Ambos comparten un bloqueo (`flock` sobre `$XDG_RUNTIME_DIR/alternar-ventilacion.lock`), así que no pueden cambiar la ventilación a la vez.

- Si el script existe, `tests/domain/test_fan_modes.py` comprueba que las curvas sigan siendo idénticas.
- Si no existe, ese test se omite y todo lo demás funciona igual.

## Cinta LED

asusd 6.5.0 no tiene una entrada para el G615JH en `/usr/share/asusd/aura_support.ron`. Usa entonces una configuración genérica que solo ofrece la zona del teclado (`SupportedPowerZones = [1]`), y la cinta LED no aparece.

[`system/asusd_user_ledmodes.ron`](../system/asusd_user_ledmodes.ron) define el modelo (`G615JH`, teclado `19b6`) con las zonas `Keyboard` y `Lightbar`. asusd lee esa ruta y la combina con su lista, que no se modifica.

```sh
scripts/lightbar-fix.sh status        # diagnóstico, sin cambios
sudo scripts/lightbar-fix.sh apply    # instala la definición y enciende la cinta
sudo scripts/lightbar-fix.sh revert   # vuelve a la configuración genérica
```

`apply` hace lo siguiente:
1. Verifica que la placa sea G615JH.
2. Respalda `/etc/asusd/asusd_user_ledmodes.ron` (si existe) y `/etc/asusd/aura_19b6.ron` como `*.bak-FECHA`.
3. Instala el archivo con permisos 0644 y reinicia asusd.
4. Comprueba que la zona Lightbar aparezca en D-Bus.
5. Enciende la cinta.

El applet nunca modifica `/etc`: sin la definición, la fila de la cinta LED no aparece.

## Idiomas

- **Un solo punto de traducción, el applet.** El backend no produce textos para el usuario.
  - El estado lleva valores crudos, como `"Discharging"` o `"medium"`.
  - Los errores llevan códigos estables con sus datos, por ejemplo `{"code": "fanModeFailed", "mode": "Ultra", "restored": true}` o `{"code": "notConfirmed", "setting": "profile"}`.
  - `presentation/serialization.py` convierte cada excepción en su código y `Texts.qml` la convierte en una frase con `i18n()`.
- **Catálogos:** el inglés es el idioma base. Las traducciones están en `plasmoid/translate/*.po` (dominio `plasma_applet_com.pablosanabria.asuscontrol`).
- **Instalación:**
  - `scripts/install.sh` compila cada `.po` en `contents/locale/<idioma>/LC_MESSAGES/` dentro de una copia temporal del paquete, y Plasma carga la traducción del propio paquete.
  - El repositorio no guarda archivos `.mo`.
- **Mantenimiento:** `scripts/update-translations.sh` extrae las cadenas con `xgettext` y actualiza los `.po`, eliminando las entradas de textos que ya no existen. Con `--check` falla si la plantilla no coincide con el QML o si queda algo sin traducir.
- **Nombres propios:** los perfiles (Quiet, Balanced, Performance) y los modos de ventilación no se traducen.
- **Detalles técnicos:** el detalle de un error de acceso al hardware, por ejemplo la salida de `busctl`, se muestra sin traducir dentro del mensaje traducido.

## Pruebas

```sh
.venv/bin/pytest
```

| Carpeta | Qué cubre |
|---|---|
| `tests/domain/` | Detección de modos de ventilación y equivalencia con `alternar-ventilacion` |
| `tests/application/` | Casos de uso con dobles en memoria de los puertos (`tests/fakes.py`): los cuatro modos, rechazo fuera de Balanced, fallo parcial con recuperación, recuperación fallida, escritura no confirmada, bloqueo ocupado, lecturas que nunca escriben |
| `tests/infrastructure/` | Respuestas D-Bus reales (`fixtures/`), argumentos de `busctl`, integración con un asusd simulado con estado (`fake_asusd_bus.py`), sysfs falso con números hwmon distintos, bloqueo entre procesos, ejecución de procesos |
| `tests/presentation/` | Órdenes de la CLI, JSON del estado y códigos de error |
| `tests/test_architecture.py` | Regla de dependencias entre capas |
| `tests/test_translations.py` | Traducciones completas y al día |
| `tests/test_lifecycle.py` | Actualización sin pérdida de preferencias o respaldo; desinstalación bloqueada si no puede restaurar |

El QML no tiene pruebas automáticas. Se comprueba en Plasma con `plasmawindowed com.pablosanabria.asuscontrol` y revisando `journalctl --user -u plasma-plasmashell`.

## Limitaciones conocidas

- **Brillo compartido:** asusd expone un único brillo (`Aura.Brightness`) y el firmware lo aplica a teclado y cinta por igual. En el G615JH, la cinta tampoco admite un color propio por zona, así que no hay forma de regular su intensidad por separado.
- **Interfaz QML:** se verifica manualmente en Plasma; las escrituras y la lógica de restauración están cubiertas en el backend.
- **GPU:** las solicitudes se aplican durante el apagado mediante asus-shutdown y se confirman después de reiniciar. No se descarga el controlador ni se fuerza el MUX en la sesión gráfica.
- **Inicio:** la recuperación ocurre al iniciar sesión de usuario en KDE, no antes del login.

## GPU y límite de carga desde 0.4.2

`infrastructure/gpu.py` lee CurrentValue, QueuedGpuValue y PossibleValues de `dgpu_disable` y del MUX si existe. El objetivo integrado usa dgpu_disable=1 y gpu_mux_mode=1. Solo se escriben los setters diferidos de CurrentValue; nunca se llama ApplyQueuedGpuValue desde la sesión gráfica. Se requiere asus-shutdown activo y se rechazan colas preexistentes al capturar la GPU.

Una GPU en cola conserva su ajuste pendiente, sin tratarlo como fallo ni confirmarlo como activo. `PowerSavingDevice.restart_required` diferencia una cola correcta de una escritura fallida. Después de reiniciar se verifica el valor real antes de confirmar. Apagar el ahorro antes del reinicio cancela la cola; si ya cambió la GPU, se solicita el modo original y el respaldo permanece hasta el siguiente reinicio. El desinstalador no retira el backend mientras esa restauración siga pendiente.

`PowerSavingMigration` añade battery.chargeLimit y gpu.configuration a sesiones antiguas todavía activas: captura y persiste solo los originales de los controles nuevos, sin sustituir los originales de los demás. La carga al 100 % se mantiene y verifica como cualquier otro ajuste administrado; la CLI y el applet impiden cambios manuales mientras existe una sesión.
