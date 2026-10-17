# ASUS Control

Applet en español para la bandeja de KDE Plasma (Wayland) que controla un ASUS ROG Strix G16 G615JH con asusctl 6.5.0.

## Funciones

- **Rendimiento:** Quiet, Balanced y Performance. Siempre muestra el perfil real.
- **Ventilación:** Normal, Extra, Ultra y Ultra Mega, con las mismas curvas que `~/.local/bin/alternar-ventilacion`. La sección solo aparece en Balanced y nunca cambia el perfil por su cuenta.
- **Iluminación:** Apagado, Bajo, Medio y Alto. asusctl expone un brillo compartido para teclado e iluminación.
- **Cinta LED:** interruptor de encendido. Solo aparece si asusd confirma que admite la zona Lightbar (ver [docs/README.md](docs/README.md#cinta-led)).
- **Batería:** porcentaje, conexión a corriente y límite de carga de 60, 80 o 100 %.
- **Sensores:** temperatura del paquete CPU y RPM de los ventiladores de CPU, GPU y central.

### Comportamiento

- Es un applet nativo de la bandeja: un clic en el icono despliega el popup anclado a la barra, igual que los de batería o red.
- **Lecturas:** al abrir el popup, tras cada acción y cada 2 s mientras está abierto. Con el popup cerrado, se comprueba el perfil cada 10 s y el tooltip refleja los cambios externos.
- Al cargar solo se leen datos; nunca se aplica ningún ajuste de hardware.
- Cada cambio se confirma con una lectura posterior y los controles se marcan solo según el estado leído.
- Si falta asusd o un sensor, se muestra «No disponible» o «—» y se deshabilitan los controles afectados.
- **Mensajes:** los errores permanecen hasta cerrarlos; las confirmaciones desaparecen a los 4 s.
- La gestión de perfiles al conectar o desconectar la corriente sigue en manos de asusd. El applet cambia solo el perfil activo, sin tocar los perfiles de corriente y batería.
- **Carga y visibilidad:** Plasma carga el applet en cada sesión, así que no hay autoarranque ni instancias propias. Para ocultarlo: clic derecho en la flecha de la bandeja → *Configurar la bandeja del sistema* → *Entradas*.

## Requisitos

- Fedora con KDE Plasma 6 (Wayland) y `asusctl`/`asusd` 6.5.0.
- `/usr/bin/python3` 3.11 o superior. El backend solo usa la biblioteca estándar.

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

Tras editar el QML: `kpackagetool6 -t Plasma/Applet --upgrade plasmoid` y vuelve a abrir el applet o reinicia plasmashell. La arquitectura y las pruebas están descritas en [docs/README.md](docs/README.md).

Se usan Conventional Commits (`feat:`, `fix:`, `docs:`, `build:`, `refactor:`…), sin atribuciones de coautor automáticas. No hay un remoto de GitHub configurado todavía.
