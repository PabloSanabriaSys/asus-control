# ASUS Control

<div align="center">
    <img src="plasmoid/icons/asus-control.svg" alt="Logo de ASUS Control" width="128">
</div>

<div align="center">
    <img src="https://img.shields.io/badge/KDE_Plasma_6-1D99F3?style=for-the-badge&logo=kde&logoColor=white" alt="KDE Plasma 6">
    <img src="https://img.shields.io/badge/QML-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="QML">
    <img src="https://img.shields.io/badge/Python_3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/D--Bus-4A4A55?style=for-the-badge&logo=freedesktopdotorg&logoColor=white" alt="D-Bus">
    <img src="https://img.shields.io/badge/Wayland-FFBC00?style=for-the-badge&logo=wayland&logoColor=black" alt="Wayland">
    <img src="https://img.shields.io/badge/License-Apache_2.0-D22128?style=for-the-badge&logo=apache&logoColor=white" alt="Apache 2.0">
</div>

## Descripción

Applet (plasmoide) para la bandeja de KDE Plasma 6 que controla un portátil ASUS ROG a través de `asusd`: perfil de rendimiento, modos de ventilación, iluminación del teclado y la cinta LED, límite de carga y sensores, todo desde un popup anclado a la barra.

Está hecho y probado para el **ROG Strix G16 G615JH** con asusd 6.5.0 en Fedora (Wayland). La interfaz QML recibe el estado de asusd por D-Bus; un backend Python sin dependencias externas coordina los cambios y la recuperación de ajustes. Se muestra en inglés o en español según el idioma del sistema.

## Funciones

- **Ahorro máximo de batería:** un interruptor aplica los ajustes compatibles y recupera tu configuración anterior al desactivarlo, incluso después de reiniciar.
- **Rendimiento:** Quiet, Balanced y Performance.
- **Ventilación:** modos Normal, Extra, Ultra y Ultra Mega para el perfil Balanced. La sección solo aparece en Balanced y nunca cambia el perfil por su cuenta. Normal devuelve el control automático a asusd.
- **Iluminación:** brillo del teclado en cuatro niveles. La cinta LED se enciende y apaga con un interruptor; no tiene brillo propio porque el hardware aplica el mismo a teclado y cinta.
- **Batería:** porcentaje, estado de carga y límite de carga de 60, 80 o 100 %.
- **Sensores:** temperatura del paquete CPU y RPM de los ventiladores de CPU, GPU y central.

### Comportamiento

- Un clic en el icono de la bandeja abre el popup, anclado a la barra como el resto de applets.
- Perfil, brillo, límite de carga y cinta LED se actualizan en vivo, incluidos los cambios hechos con otras herramientas (`asusctl`, teclas Fn, conexión del cargador).
- Al tocar un control, el cambio se ve al instante y se confirma con la lectura posterior de asusd. Si no se confirma, el control vuelve al valor real y se muestra el error. Las escrituras pasan por el backend y se ejecutan en orden.
- Al cargarse no aplica ningún ajuste: solo lee.
- Con el ahorro apagado, los perfiles automáticos con y sin cargador siguen a cargo de asusd. Al activarlo se pausan y se restauran al desactivarlo.
- Si asusd no responde o falta un sensor, el dato aparece como «No disponible» o «—» y los controles afectados se deshabilitan.

## Ahorro máximo de batería

Activa **Ahorro máximo de batería** para guardar los ajustes actuales y reducir el consumo. Desactívalo para recuperar los valores que tenías antes. El respaldo sobrevive a cierres del applet, apagados y reinicios: al iniciar sesión en KDE, el servicio de usuario recupera el ahorro si seguía activado.

| Ajuste compatible | Durante el ahorro |
|---|---|
| Rendimiento | Quiet |
| Límite de carga | 100 %, bloqueado durante el ahorro |
| GPU | Gráficos integrados; si cambia el modo, se prepara para el próximo reinicio |
| Ventilación de Balanced y Quiet | Control automático; se guardan las curvas originales completas |
| Teclado y cinta LED | Apagados; la cinta también se desactiva en arranque, suspensión y apagado |
| Pantalla interna | 60 Hz o menos, conservando la resolución |
| Overdrive del panel | Desactivado |
| Pantalla inactiva | Apagado después de 2 minutos |
| Suspensión por inactividad | Después de 10 minutos, si el sistema admite suspender |

Conserva los ajustes de brillo y frecuencia de los monitores externos y la acción de la tapa. Los cambios automáticos de perfil de asusd y de teclado/perfil de KDE se coordinan temporalmente con el ahorro y se restauran después. Los controles manuales, incluido el límite de carga, quedan bloqueados hasta desactivar el ahorro y completar la restauración. El servicio vuelve a fijar el límite en 100 % si otra herramienta lo cambia durante el ahorro.

Los ajustes no compatibles se indican en el panel. Para la GPU se usan las solicitudes diferidas de asusd: el modo integrado se aplica al próximo reinicio, sin cerrar tu sesión automáticamente. Hasta entonces el applet indica **pendiente de reinicio**, no «GPU integrada activa».

Si desactivas el ahorro antes de reiniciar, se cancela la solicitud de GPU. Si ya reiniciaste con la integrada, volver al modo de GPU anterior puede necesitar otro reinicio; el respaldo se conserva hasta confirmarlo. Las salidas externas conectadas a la GPU dedicada pueden dejar de funcionar en modo integrado. Consulta la [documentación de cambio de GPU de ASUS Linux](https://opengamingcollective.github.io/asusctl/faq/gpu-switching.html).

No se sustituye una solicitud de GPU que ya estuviera pendiente desde otra herramienta. Si falta el soporte de conmutación diferida o `asus-shutdown.service`, se informa de que la GPU no se pudo administrar. El nombre del modo describe sus ajustes de ahorro, no garantiza una autonomía determinada.

El servicio comprueba conexión del cargador y reanudaciones cada 15 segundos, y verifica los ajustes activos cada minuto. Con el ahorro desactivado no lee ni modifica el hardware. Si una aplicación externa cambia ajustes administrados durante el ahorro, el servicio vuelve a aplicar los valores del modo.

Si falla una aplicación o restauración, se muestran los ajustes pendientes y se conserva el respaldo para reintentar. Un respaldo ilegible bloquea los cambios para evitar perder tu configuración. La desinstalación también intenta restaurarla antes de retirar el programa.

Desde la terminal:

```sh
asus-control power-saving on                    # activa el ahorro
asus-control power-saving off                   # restaura los valores anteriores
asus-control power-saving audit                 # compara objetivos y valores leídos ahora
asus-control state                              # estado y comprobaciones en vivo
asus-control battery                            # batería sin consultar asusd
```

El ahorro no fija un brillo de pantalla propio: ese ajuste queda a cargo de KDE y de tus cambios manuales. La configuración se guarda en `${XDG_STATE_HOME:-~/.local/state}/asus-control/power-saving.json`. No borres ese archivo mientras haya cambios pendientes de restaurar.

### Porcentaje de batería y límite de carga

El porcentaje del encabezado es la carga real leída del equipo. Los botones **60 / 80 / 100 %** fijan el límite de carga. Al activar el ahorro, el límite pasa automáticamente a **100 %** y se bloquea ahí; al desactivarlo, se restaura el límite anterior.

Cambiar el límite permite cargar más, pero no aumenta instantáneamente el porcentaje: la batería debe estar conectada y cargar físicamente. Con el ahorro apagado puedes elegir el límite manualmente.

La batería y los sensores se actualizan cada 2 segundos con el popup o la ventana independiente visibles. Con el panel cerrado se actualiza únicamente la batería cada 30 segundos, sin consultar los controles de asusd. El icono muestra carga en curso solo cuando el equipo informa «Cargando».

Las comprobaciones del ahorro leen los valores actuales: si otra aplicación cambia un ajuste o falla una lectura, el panel deja de mostrarlo como confirmado y permite reintentar. La auditoría no cambia la configuración. La [comprobación de la versión 0.4.2](docs/validation-0.4.2.md) detalla las pruebas reales y sus límites.

## Requisitos

- KDE Plasma 6 con `asusd` en ejecución (paquete `asusctl`).
- Para el ahorro de pantalla: PowerDevil y `kscreen-doctor` (los controles no disponibles se omiten).
- Sesión de usuario con systemd para recuperar el ahorro al iniciar y reanudar.
- `/usr/bin/python3` 3.11 o superior (sin paquetes adicionales).
- `gettext` (`msgfmt`) para compilar las traducciones al instalar.

Los modos de ventilación y la detección de la cinta LED están pensados para el G615JH. En otros modelos ROG los controles generales (perfil, brillo, carga) deberían funcionar, pero no se ha probado.

## Instalación

```sh
scripts/install.sh               # instala y reinicia plasmashell
scripts/install.sh --no-restart  # instala sin reiniciar Plasma
```

Instala para el usuario actual, sin sudo:

| Ruta | Contenido |
|---|---|
| `~/.local/share/asus-control/` | Backend Python |
| `~/.local/bin/asus-control` | Backend (`asus-control state`, `asus-control set …`) |
| `~/.local/share/plasma/plasmoids/com.pablosanabria.asuscontrol/` | Applet, con sus traducciones compiladas |
| `~/.local/share/applications/asus-control.desktop` | Entrada del lanzador: abre el applet en una ventana |
| `~/.local/share/icons/hicolor/scalable/apps/asus-control*.svg` | Iconos |
| `~/.config/systemd/user/asus-control-power-saving.service` | Recuperación y mantenimiento del ahorro durante la sesión |
| `~/.local/state/asus-control/power-saving.json` | Respaldo persistente, creado al activar el ahorro |

Plasma añade el applet a la bandeja automáticamente. Para actualizar, vuelve a ejecutar el script; conserva las preferencias y el respaldo de restauración.

### Cinta LED en el G615JH

asusd 6.5.0 no incluye el G615JH en su lista de modelos y solo ofrece la zona del teclado, así que la cinta LED no aparece. `scripts/lightbar-fix.sh` instala una definición local (con respaldo y reversión); ver [docs/README.md](docs/README.md#cinta-led).

## Desinstalación

```sh
scripts/uninstall.sh               # reinicia plasmashell al terminar
scripts/uninstall.sh --no-restart
```

Restaura primero los ajustes si el ahorro estaba activado. Si falla o la restauración de GPU requiere reiniciar, conserva la instalación y el respaldo para reintentar. Después elimina el applet, el backend, el servicio, los iconos y la entrada del lanzador. No toca `/etc/asusd`: si instalaste la corrección de la cinta, revierte con `sudo scripts/lightbar-fix.sh revert`.

## Desarrollo

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy && .venv/bin/pytest

PYTHONPATH=src python3 -m asus_control state    # backend sin instalar
scripts/install.sh --no-restart                 # tras editar el QML
plasmawindowed com.pablosanabria.asuscontrol    # abrir el applet en una ventana
```

**Traducciones:** todo texto visible del QML va en `i18n()`, con el inglés como idioma base. Después de añadir o cambiar textos:

```sh
scripts/update-translations.sh                            # actualiza template.pot y es.po
# traduce las entradas nuevas de plasmoid/translate/es.po
scripts/update-translations.sh --check                    # pytest también lo ejecuta
LANGUAGE=es plasmawindowed com.pablosanabria.asuscontrol  # probar en español
```

La arquitectura, las fuentes de datos y las pruebas están en [docs/README.md](docs/README.md).

## Licencia

[Apache License 2.0](LICENSE).
