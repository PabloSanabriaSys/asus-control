# Comprobación de ahorro 0.4.1

Verificado el 24 de octubre de 2026 en el G615JH, con asusd 6.5.0 y Plasma/PowerDevil 6.7.5.

## Ciclo real de activación y restauración

Además de comparar los diez ajustes guardados por el backend, se consultaron sysfs, KScreen y D-Bus de forma independiente:

| Dato | Antes | Ahorro activo | Después de desactivar |
|---|---|---|---|
| Perfil del firmware (`/sys/firmware/acpi/platform_profile`) | performance | quiet | performance |
| EPP del CPU (`energy_performance_preference`) | performance | power | performance |
| Frecuencia interna | 165 Hz | 60 Hz | 165 Hz |
| Resolución interna | 1920 × 1200 | 1920 × 1200 | 1920 × 1200 |
| Brillo del panel en KScreen | 0,30 | 0,30 | 0,30 |
| Retroiluminación en sysfs | 31 | 31 | 31 |
| Overdrive en sysfs | 1 | 0 | 1 |
| Monitor HDMI | 144 Hz, brillo 0,61 | Sin cambios | Sin cambios |

Las lecturas de los diez ajustes coincidieron con sus objetivos durante el ahorro y con sus originales al terminar. Se probó también cambiar el límite a 100 % con el ahorro activo: asusd confirmó 100 y el modo siguió encendido. Después se restauró el límite original de 60 %.

Esto comprueba cambios y restauración; no mide cuántas horas de autonomía se obtienen. Los tiempos de apagado y suspensión se comprobaron como configuración de PowerDevil y recarga aceptada, sin esperar a una suspensión física ni cerrar la sesión del usuario. La GPU no se conmuta.

## Actualización de la interfaz

Se ejecutó la ventana real de `plasmawindowed` con un HOME temporal, con un backend de prueba que pasó de 41 % a 54 %. Hubo cinco lecturas de estado en unos siete segundos y la ventana mostró 54 %. Esos porcentajes se usaron solamente en la prueba aislada, no en el hardware ni en la instalación del usuario.

Se comprobó también la acción QML del límite de carga en un paquete temporal conectado al backend y hardware reales. Con el ahorro activo, la acción pasó a 100 % y se verificaron cuatro lecturas: propiedad en vivo de D-Bus, valor mostrado por el control, respuesta del backend y umbral real de asusd. Todas indicaron 100 % y la acción dejó de estar pendiente. Al terminar se restauraron el límite y los ajustes originales.

## Regresiones automatizadas

- Batería leída de nuevo sin consultar asusd.
- Límite de carga editable mientras el ahorro sigue activo.
- Detección de valores modificados externamente sin escribir durante la auditoría.
- Reintento completo cuando se guardó un valor pero falló una operación posterior.
- Restauración única del antiguo brillo y conservación del respaldo si falla.
- Espera acotada del bloqueo para no rechazar inmediatamente acciones del usuario.
