# Documentación técnica

## Arquitectura

El proyecto es un **plugin de Plasma** (plasmoide de la bandeja) con un backend Python sin dependencias externas. En Wayland solo Plasma puede anclar un popup al icono de la bandeja; por eso la interfaz es QML y toda la lógica está en Python.

```
plasmoid/ (QML)  ──sh──▶  asus-control <orden>  ──▶  presentation → application → domain
                                                                         ▲
                                                     infrastructure ─────┘ (implementa los puertos)
```

### Capas del backend (`src/asus_control/`)

| Capa | Contenido | Puede importar |
|---|---|---|
| `domain/` | `models.py` (enums y dataclasses inmutables), `errors.py`, `fan_modes.py` (curvas de `alternar-ventilacion` y detección del modo) | nada |
| `application/` | `ports.py` (`PlatformPort`, `LightbarPort`, `SensorPort`, `FanLock`), `fan_service.py`, `hardware_service.py` (casos de uso) | `domain` |
| `infrastructure/` | `asusctl.py` + `asusctl_parsing.py`, `aura.py` (D-Bus de asusd), `sysfs.py`, `fan_lock.py`, `process.py`, `errors.py` | `domain`, `application` |
| `presentation/` | `cli.py` (órdenes y JSON), `serialization.py`, `labels.py` (textos en español) | `domain`, `application` |
| `bootstrap.py` | Raíz de composición: crea los adaptadores, los inyecta en los servicios y arranca la CLI | todo |

- **Regla de dependencias:** las dependencias apuntan hacia dentro. `tests/test_architecture.py` la hace cumplir analizando los imports, y además comprueba que el dominio no use E/S (`subprocess`, `json`, `fcntl`).
- **Puertos y adaptadores:** la aplicación define con `Protocol` lo que necesita y la infraestructura lo implementa; mypy verifica que cada adaptador cumpla su puerto.
  - `AsusCtl` implementa `PlatformPort`.
  - `AsusdLightbar` implementa `LightbarPort`: lee por D-Bus y escribe con asusctl.
  - `SysfsSensors` implementa `SensorPort`.
  - `fan_lock` implementa `FanLock`.
- **Errores:** la aplicación solo conoce `HardwareAccessError` (dominio). La infraestructura lanza las subclases concretas `CommandError` y `ParseError`.
- **Formatos externos fuera del dominio:** el argumento `med` de asusctl, el formato `40c:51,…` de las curvas y los números de zona de D-Bus viven en infraestructura. Las etiquetas en español viven en presentación.
- **CLI:**
  - `argparse` solo acepta valores cerrados, derivados de los enums. Cada ajuste se declara una vez en la tabla `_SETTINGS`.
  - Un error esperado (`AsusControlError`) devuelve `ok: false`, un `error` con código estable (ver [Idiomas](#idiomas)) y el estado actual.
  - Un error no previsto devuelve código 1 con la traza en stderr.
- **Confirmación de cambios:** cada acción vuelve a leer el valor. Si no coincide, se lanza `VerificationError`.

### Plugin de Plasma (`plasmoid/`)

- `main.qml` ejecuta el backend con el motor `executable` de Plasma5Support. Una cola garantiza que solo corra una orden a la vez y que no se dupliquen lecturas pendientes. Los valores se citan para `sh`, aunque solo provienen de listas fijas.
- `FullRepresentation.qml` es el popup; `SegmentedRow.qml`, `Section.qml` y `SensorTile.qml` son componentes reutilizables.
- Los botones y el interruptor siguen siempre al estado leído: tras un clic se vuelven a enlazar con él, así que nunca se marcan de forma optimista.

### Idiomas

- **Un solo punto de traducción, el applet.** El backend no produce textos para el usuario: el estado lleva valores crudos (`"Discharging"`, `"medium"`) y los errores, códigos estables con sus datos.
  - Ejemplos: `{"code": "fanModeFailed", "mode": "Ultra", "restored": true}` o `{"code": "notConfirmed", "setting": "profile"}`.
  - `presentation/serialization.py` convierte cada excepción del dominio en su código.
  - `plasmoid/contents/ui/Texts.qml` la convierte en una frase con `i18n()`.
- **Catálogos:** el inglés es el idioma base. Las traducciones están en `plasmoid/translate/*.po` (dominio `plasma_applet_com.pablosanabria.asuscontrol`).
- **Instalación:** `scripts/install.sh` compila cada `.po` en `contents/locale/<idioma>/LC_MESSAGES/` dentro de una copia temporal del paquete, y Plasma carga esa traducción del propio paquete. En el repositorio no se guardan `.mo`.
- **Mantenimiento:** `scripts/update-translations.sh` extrae las cadenas con `xgettext`. Con `--check` falla si la plantilla no coincide con el QML o si queda alguna entrada sin traducir; `tests/test_translations.py` lo ejecuta.
- **Errores técnicos:** el detalle de un error de acceso al hardware, como la salida de asusctl, se muestra sin traducir dentro del mensaje traducido.
- **Metadatos:** la descripción del applet (`metadata.json`) y la entrada del lanzador incluyen versiones `[es]`.

### Pruebas por capa (`tests/`)

- `domain/`: reglas puras, incluida la comparación con el script real.
- `application/`: casos de uso con dobles en memoria de los puertos (`tests/fakes.py`).
- `infrastructure/`: salidas reales de asusctl y busctl en `fixtures/`, procesos, bloqueo entre procesos, sysfs falso y una integración con `fake_asusd.py` que simula asusctl con estado.
- `presentation/`: CLI y JSON.

### Fuentes de datos

| Dato | Lectura | Escritura |
|---|---|---|
| Perfil | `asusctl profile get` | `asusctl profile set <P>` (sin `-a`/`-b`) |
| Ventilación | `asusctl fan-curve --mod-profile Balanced` | `--fan cpu/gpu/mid --data …`, `--enable-fan-curves true/false` |
| Brillo | `asusctl leds get` | `asusctl leds set off/low/med/high` |
| Límite de carga | `asusctl battery info` | `asusctl battery limit N` |
| Cinta LED | D-Bus `xyz.ljones.Aura`: `SupportedPowerZones`, `LedPower` (vía `busctl`) | `asusctl aura power lightbar [--boot] [--awake] …` |
| Sensores | hwmon `asus` (`cpu_fan`, `gpu_fan`, `mid_fan`) y `coretemp` (`Package id 0`) | — |
| Batería | `power_supply` con `type=Battery` (sin `scope=Device`) y `type=Mains` | — |

Los dispositivos hwmon y power_supply se buscan por `name`, `*_label` y `type`, nunca por su número.

## Ventilación

- `fans.py` copia literalmente `TEMPS` y `CURVES` de `~/.local/bin/alternar-ventilacion`. La prueba `test_curves_are_identical_to_alternar_ventilacion` lee el script con `ast` y falla si alguna curva cambia.
- **Bloqueo compartido:** el mismo `flock` no bloqueante sobre `$XDG_RUNTIME_DIR/alternar-ventilacion.lock`. Si el script está aplicando un cambio, la app avisa «Hay otro cambio de ventilación en curso», y viceversa (el script sale sin hacer nada).
- **Secuencia de aplicación:**
  1. Tomar el bloqueo.
  2. Revalidar que el perfil sea Balanced.
  3. Escribir las tres curvas.
  4. Activarlas.
  5. Volver a leer y comparar.
- **Normal:** desactiva las curvas personalizadas.
- **Recuperación:** si falla cualquier paso posterior a la revalidación, la app desactiva las curvas, comprueba que se haya recuperado el control automático e informa si se logró o no.
- **Curvas desconocidas:** si las curvas activas no coinciden con ningún modo, el applet indica «Curvas personalizadas» y no marca ningún botón.
- **Acceso «Alternar ventilación»:** el script, su `.desktop` y su atajo de teclado siguen funcionando sin cambios.

## Cinta LED

### Diagnóstico (17-10-2026)

- `asusctl info` identifica la placa como `G615JH`. El teclado Aura es `0b05:19b6`.
- `/usr/share/asusd/aura_support.ron` incluye `G615JHR`, pero no `G615JH`. asusd registra *«the aura_support.ron file has no entry for this model: G615JH, 19b6. Using a default»* y solo publica la zona Keyboard (`SupportedPowerZones = [1]`).
- **La corrección anterior no quedó guardada:** el journal muestra que a las 02:12:16 asusd cargó `/etc/asusd/asusd_user_ledmodes.ron` (*«Matched to G615JH»*). Pero tras el reinicio de las 02:12:56 el archivo ya no existía y volvió la configuración genérica.

### Corrección persistente (opcional, una sola vez)

[`system/asusd_user_ledmodes.ron`](../system/asusd_user_ledmodes.ron) contiene una única entrada `G615JH`/`19b6` con `power_zones: [Keyboard, Lightbar]`. asusd 6.5.0 lee esa ruta y la combina con el archivo del sistema, que no se modifica.

```sh
scripts/lightbar-fix.sh status        # diagnóstico, sin cambios
sudo scripts/lightbar-fix.sh apply    # respaldo + instalación + reinicio de asusd + encendido
sudo scripts/lightbar-fix.sh revert   # vuelve a la configuración genérica
```

`apply` hace lo siguiente:
1. Verifica que la placa sea G615JH.
2. Respalda `/etc/asusd/asusd_user_ledmodes.ron` (si existe) y `/etc/asusd/aura_19b6.ron` como `*.bak-FECHA`.
3. Instala el archivo con permisos 0644 y reinicia asusd.
4. Comprueba que la zona Lightbar aparezca en D-Bus.
5. Ejecuta `asusctl aura power lightbar --boot --awake`.

La aplicación nunca modifica `/etc`. Sin la corrección, la sección «Cinta LED» permanece oculta.

## Pruebas

```sh
.venv/bin/pytest
```

Cubren:
- Parsers con salidas reales capturadas en `tests/fixtures/`.
- Argumentos exactos de cada orden.
- Simulación con estado de asusd: los cuatro modos, el rechazo fuera de Balanced, un fallo parcial con recuperación, una recuperación fallida, una escritura no confirmada y el bloqueo entre procesos.
- Sensores sobre un sysfs falso con números hwmon distintos.
- Lecturas que nunca escriben en el hardware.
- Serialización JSON, códigos de error, cada orden `set` de la CLI, errores esperados como `ok: false`, rechazo de argumentos no válidos y código de salida ante errores no previstos.
- Regla de dependencias entre capas (`tests/test_architecture.py`).
- Traducciones completas y al día (`tests/test_translations.py`).

El QML no tiene pruebas automáticas (no hay `qmltestrunner` ni `plasmoidviewer` instalados). Se verifica en Plasma con `plasmawindowed` y revisando `journalctl --user -u plasma-plasmashell`.

### Verificación manual realizada en el equipo

- Cambio de Quiet → Performance → Balanced, confirmado con `asusctl profile get`. Los perfiles de corriente y batería (Balanced/Quiet) no cambian.
- En Quiet y Performance, la ventilación se rechaza sin cambiar el perfil.
- Extra → Ultra → Ultra Mega → Normal aplicados y detectados, también con la orden citada tal como la ejecuta el applet (`sh -c "… set 'fan' 'Ultra Mega'"`).
- Brillo Apagado/Bajo/Medio/Alto y límite 80/100/60 % aplicados y confirmados.
- Con el bloqueo tomado, `alternar-ventilacion` sale sin hacer cambios. El ciclo completo del script es reconocido en cada paso.
- Applet instalado con `scripts/install.sh`: Plasma lo añade automáticamente a la bandeja. `plasmawindowed` muestra el estado real y el journal no registra errores QML del applet.
- Con el sistema en inglés el applet aparece en inglés, y con `LANGUAGE=es` en español, cargando el `.mo` incluido en el paquete.

## Limitaciones conocidas

- **Brillo compartido:** asusctl 6.5.0 solo expone un brillo para teclado e iluminación, así que no hay controles separados para cada uno.
- **Cinta LED:** queda oculta mientras no se aplique `lightbar-fix.sh`. El apagado (`aura power lightbar` sin `--awake`) solo se podrá verificar en el equipo después de aplicar la corrección.
- **Costo de cada lectura:** cada lectura arranca un proceso Python (~0,5 s, en segundo plano). Con el popup abierto se lee cada 2 s; cerrado, solo el perfil cada 10 s.
- **Tamaño del popup:** el popup de la bandeja tiene el tamaño que define la bandeja de Plasma. Si el contenido no cabe, se desplaza verticalmente.
