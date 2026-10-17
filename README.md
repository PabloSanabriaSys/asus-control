# ASUS Control

Applet (plasmoide) para la bandeja de KDE Plasma (Wayland) que controla un ASUS ROG Strix G16 G615JH con asusctl 6.5.0. Se muestra en inglés o en español según el idioma del sistema.

## Funciones

- **Rendimiento:** Quiet, Balanced y Performance. Siempre muestra el perfil real.
- **Ventilación:** Normal, Extra, Ultra y Ultra Mega, con las mismas curvas que `~/.local/bin/alternar-ventilacion`. La sección solo aparece en Balanced y nunca cambia el perfil por su cuenta.
- **Iluminación:** slider de brillo con los cuatro niveles del hardware (Apagado, Bajo, Medio y Alto). asusctl expone un único brillo compartido por el teclado y la iluminación.
- **Cinta LED:** interruptor de encendido; no tiene brillo propio. Solo aparece si asusd confirma que admite la zona Lightbar (ver [docs/README.md](docs/README.md#cinta-led)).
- **Batería:** porcentaje con el icono de batería del tema (con enchufe si está conectada), estado de carga y límite de carga de 60, 80 o 100 %.
- **Sensores:** temperatura del paquete CPU y RPM de los ventiladores de CPU, GPU y central, en la parte superior del popup.

### Comportamiento

- Es un applet nativo de la bandeja: un clic en el icono despliega el popup anclado a la barra, igual que los de batería o red.
- **Lecturas:** al abrir el popup, tras cada acción y cada 2 s mientras está abierto. Con el popup cerrado, se comprueba el perfil cada 10 s y el tooltip refleja los cambios externos.
- Al cargar solo se leen datos; nunca se aplica ningún ajuste de hardware.
- Cada cambio se confirma con una lectura posterior y los controles se marcan solo según el estado leído.
- Si falta asusd o un sensor, se muestra «No disponible» o «—» y se deshabilitan los controles afectados.
- **Mensajes:** solo se muestran errores, que permanecen hasta cerrarlos. Un cambio correcto no se anuncia: se ve en el propio control.
- La gestión de perfiles al conectar o desconectar la corriente sigue en manos de asusd. El applet cambia solo el perfil activo, sin tocar los perfiles de corriente y batería.
- **Carga y visibilidad:** Plasma carga el applet en cada sesión, así que no hay autoarranque ni instancias propias. Para ocultarlo: clic derecho en la flecha de la bandeja → *Configurar la bandeja del sistema* → *Entradas*.

### Idioma

El applet usa el idioma de Plasma (*Preferencias del sistema → Región e idioma*): español si es `es`, inglés en cualquier otro caso. Los nombres de perfil (Quiet, Balanced, Performance) y de modo de ventilación son nombres propios y no se traducen.

## Requisitos

- Fedora con KDE Plasma 6 (Wayland) y `asusctl`/`asusd` 6.5.0.
- `/usr/bin/python3` 3.11 o superior. El backend solo usa la biblioteca estándar.
- `gettext` (`msgfmt`) para compilar las traducciones durante la instalación.

## Instalación

```sh
scripts/install.sh               # instala y reinicia plasmashell
scripts/install.sh --no-restart  # instala sin reiniciar Plasma
```

Instala para el usuario actual, sin sudo ni pip:

| Archivo | Uso |
|---|---|
| `~/.local/share/asus-control/` | Backend Python |
| `~/.local/bin/asus-control` | Lanzador del backend (`asus-control state`, `asus-control set …`) |
| `~/.local/share/plasma/plasmoids/com.pablosanabria.asuscontrol/` | Applet de la bandeja |
| `~/.local/share/applications/asus-control.desktop` | Entrada en el lanzador; abre el applet en una ventana (`plasmawindowed`) |
| `~/.local/share/icons/hicolor/scalable/apps/asus-control.svg` | Icono |

Para actualizar, vuelve a ejecutar el script. También elimina la app de bandeja Qt de versiones anteriores y su entrada de autostart.

## Desinstalación

```sh
scripts/uninstall.sh
```

Elimina el applet, el backend, el icono y la entrada del lanzador, y reinicia plasmashell (usa `--no-restart` para evitarlo). No modifica `alternar-ventilacion` ni `/etc/asusd`. Si instalaste la corrección de la cinta LED, revierte con `sudo scripts/lightbar-fix.sh revert`.

## Desarrollo

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy && .venv/bin/pytest
PYTHONPATH=src python3 -m asus_control state               # backend sin instalar
plasmawindowed com.pablosanabria.asuscontrol               # applet instalado, en ventana
```

Tras editar el QML, vuelve a ejecutar `scripts/install.sh` (compila las traducciones y actualiza el applet).

**Traducciones:** todo texto visible del QML va en `i18n()` con el inglés como idioma base. Después de añadir o cambiar textos:

```sh
scripts/update-translations.sh          # actualiza plasmoid/translate/template.pot y es.po
# traduce las entradas nuevas de plasmoid/translate/es.po
scripts/update-translations.sh --check  # también lo ejecuta pytest
LANGUAGE=es plasmawindowed com.pablosanabria.asuscontrol   # probar en español
``` El backend sigue una arquitectura por capas (`domain`, `application`, `infrastructure`, `presentation`), descrita junto con las pruebas en [docs/README.md](docs/README.md#arquitectura).

Se usan Conventional Commits (`feat:`, `fix:`, `docs:`, `build:`, `refactor:`…), sin atribuciones de coautor automáticas. No hay un remoto de GitHub configurado todavía.
