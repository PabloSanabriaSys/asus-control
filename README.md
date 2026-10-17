# ASUS Control

Panel de bandeja en español para controlar un ASUS ROG Strix G16 G615JH (asusctl 6.5.0) en KDE Plasma con Wayland.

## Funciones

- **Rendimiento:** Quiet, Balanced y Performance. Siempre muestra el perfil real.
- **Ventilación:** Normal, Extra, Ultra y Ultra Mega, con las mismas curvas que `~/.local/bin/alternar-ventilacion`. La sección solo aparece en Balanced y nunca cambia el perfil por su cuenta.
- **Iluminación:** Apagado, Bajo, Medio y Alto. asusctl expone un brillo compartido para teclado e iluminación.
- **Cinta LED:** encendido y apagado. Solo aparece si asusd confirma que admite la zona Lightbar (ver [docs/README.md](docs/README.md#cinta-led)).
- **Batería:** porcentaje, conexión a corriente y límite de carga de 60, 80 o 100 %.
- **Sensores:** temperatura del paquete CPU y RPM de los ventiladores de CPU, GPU y central.

### Comportamiento

- Un clic en el icono abre o cierra el panel. Cerrar el panel no cierra la aplicación, que sigue en la bandeja.
- **Menú contextual:** Abrir, Inicio automático (activado por defecto) y Salir.
- Solo hay una instancia por sesión. Si se lanza otra, se muestra el panel existente.
- Al iniciar solo se leen datos; no se aplica ningún ajuste de hardware.
- **Lecturas:** al abrir el panel, tras cada acción y cada 2 s mientras el panel está visible. Además, se comprueba el perfil cada 10 s en segundo plano.
- Cada cambio se confirma con una lectura posterior. Si falta asusd o un sensor, se muestra «No disponible» y se deshabilitan los controles afectados.
- La gestión de perfiles al conectar o desconectar la corriente sigue en manos de asusd. La aplicación cambia solo el perfil activo, sin tocar los perfiles de corriente y batería.

## Requisitos

- Fedora con KDE Plasma (Wayland), `asusctl`/`asusd` 6.5.0.
- `/usr/bin/python3` (3.11 o superior) con PySide6 del sistema (`python3-pyside6`).

## Instalación

```sh
scripts/install.sh
```

Instala para el usuario actual, sin sudo ni pip:

| Archivo | Uso |
|---|---|
| `~/.local/share/asus-control/` | Código de la aplicación |
| `~/.local/bin/asus-control` | Lanzador |
| `~/.local/share/applications/asus-control.desktop` | Entrada en el lanzador de Plasma |
| `~/.local/share/icons/hicolor/scalable/apps/asus-control.svg` | Icono |
| `~/.config/autostart/asus-control.desktop` | Inicio automático (lo crea la aplicación en su primer arranque) |

Al terminar, la aplicación se inicia en la bandeja; usa `--no-start` para evitarlo. Para actualizar, vuelve a ejecutar el script: detiene la instancia en ejecución y la reinicia.

## Desinstalación

```sh
scripts/uninstall.sh          # conserva ~/.config/asus-control
scripts/uninstall.sh --purge  # elimina también la configuración
```

No modifica `alternar-ventilacion` ni `/etc/asusd`. Si instalaste la corrección de la cinta LED, revierte con `sudo scripts/lightbar-fix.sh revert`.

## Desarrollo

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy && .venv/bin/pytest
PYTHONPATH=src python3 -m asus_control   # ejecutar sin instalar (ASUS_CONTROL_DEBUG=1 para más registro)
```

El `.venv` solo se usa para las herramientas de desarrollo; la aplicación instalada usa el Python del sistema. La arquitectura y las pruebas están descritas en [docs/README.md](docs/README.md).

Se usan Conventional Commits (`feat:`, `fix:`, `docs:`, `build:`, `test:`…), sin atribuciones de coautor automáticas. No hay un remoto de GitHub configurado todavía.
