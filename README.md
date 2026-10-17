# ASUS Control

Panel de bandeja en español para controlar un ASUS ROG Strix G16 G615JH en KDE Plasma con Wayland.

## Estado

Proyecto inicializado. La aplicación todavía no está implementada.

## Funciones previstas

- Perfiles Quiet, Balanced y Performance.
- Ventilación Normal, Extra, Ultra y Ultra Mega, visible únicamente en Balanced.
- Brillo compartido de teclado e iluminación; control de cinta LED sujeto al soporte real del equipo.
- Límite de carga, estado de batería, temperatura CPU y RPM de ventiladores.
- Panel compacto, instancia única e inicio automático configurable.

## Base técnica

Python 3.11+, PySide6 y `asusctl` 6.5.0. La interfaz se ejecutará como usuario normal y delegará los controles de hardware en `asusd`.

El código de la aplicación estará en `src/asus_control`, las pruebas en `tests` y la documentación en `docs`.

## Desarrollo

Usar Conventional Commits, por ejemplo `feat: add tray panel`, `fix: refresh active profile` o `test: cover fan recovery`. No añadir atribuciones de coautor automáticas.

No hay un remoto de GitHub configurado todavía.
