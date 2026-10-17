# ASUS Control

Applet (plasmoide) para la bandeja de KDE Plasma 6 que controla un portátil ASUS ROG a través de `asusd`. Está hecho y probado para el **ROG Strix G16 G615JH** con asusd 6.5.0 en Fedora (Wayland). Se muestra en inglés o en español según el idioma del sistema.

## Funciones

- **Rendimiento:** Quiet, Balanced y Performance.
- **Ventilación:** modos Normal, Extra, Ultra y Ultra Mega para el perfil Balanced. La sección solo aparece en Balanced y nunca cambia el perfil por su cuenta. Normal devuelve el control automático a asusd.
- **Iluminación:** brillo del teclado en cuatro niveles. La cinta LED se enciende y apaga con un interruptor; no tiene brillo propio porque el hardware aplica el mismo a teclado y cinta.
- **Batería:** porcentaje, estado de carga y límite de carga de 60, 80 o 100 %.
- **Sensores:** temperatura del paquete CPU y RPM de los ventiladores de CPU, GPU y central.

### Comportamiento

- Un clic en el icono de la bandeja abre el popup, anclado a la barra como el resto de applets.
- Perfil, brillo, límite de carga y cinta LED se actualizan en vivo, incluidos los cambios hechos con otras herramientas (`asusctl`, teclas Fn, conexión del cargador).
- Al tocar un control, el cambio se ve al instante y se confirma con la lectura posterior de asusd. Si no se confirma, el control vuelve al valor real y se muestra el error.
- Al cargarse no aplica ningún ajuste: solo lee.
- El applet cambia solo el perfil activo. Los perfiles automáticos con y sin cargador siguen a cargo de asusd.
- Si asusd no responde o falta un sensor, el dato aparece como «No disponible» o «—» y los controles afectados se deshabilitan.

## Requisitos

- KDE Plasma 6 con `asusd` en ejecución (paquete `asusctl`).
- `/usr/bin/python3` 3.11 o superior. El backend solo usa la biblioteca estándar.
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

Plasma añade el applet a la bandeja automáticamente. Para actualizar, vuelve a ejecutar el script.

### Cinta LED en el G615JH

asusd 6.5.0 no incluye el G615JH en su lista de modelos y solo ofrece la zona del teclado, así que la cinta LED no aparece. `scripts/lightbar-fix.sh` instala una definición local (con respaldo y reversión); ver [docs/README.md](docs/README.md#cinta-led).

## Desinstalación

```sh
scripts/uninstall.sh               # reinicia plasmashell al terminar
scripts/uninstall.sh --no-restart
```

Elimina el applet, el backend, los iconos y la entrada del lanzador. No toca `/etc/asusd`: si instalaste la corrección de la cinta, revierte con `sudo scripts/lightbar-fix.sh revert`.

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

La arquitectura, las fuentes de datos y las pruebas están en [docs/README.md](docs/README.md). Los commits siguen [Conventional Commits](https://www.conventionalcommits.org/).

## Licencia

[Apache License 2.0](LICENSE).
