# Comprobación de carga y GPU 0.4.2

Verificado en el G615JH con asusd 6.5.0. No se reinició ni se cerró la sesión del usuario para esta comprobación.

## Hardware real

- La GPU partía de `dgpu_disable=0`, `gpu_mux_mode=1`, sin valores pendientes.
- Al solicitar la integrada, asusd mantuvo `CurrentValue=0` y confirmó `QueuedGpuValue=1` para `dgpu_disable`. La GPU no se marcó como aplicada en vivo.
- Se canceló esa solicitud y se comprobó que volviera a la configuración original, sin modificar el respaldo del ahorro.
- Al instalar la versión nueva con el ahorro ya activo, se conservaron los diez registros originales de la sesión anterior y se añadieron los originales de carga y GPU antes de aplicar los nuevos objetivos.
- El límite de carga quedó en 100 %. La CLI rechazó intentar fijarlo en 60 % mientras el ahorro seguía activo.
- Un cambio externo temporal a 80 % apareció en la auditoría como no confirmado; la reconciliación volvió a fijarlo en 100 %.

El modo integrado queda preparado para el siguiente reinicio del usuario. Su aplicación física después del reinicio se cubre con simulaciones de la interfaz de asusd, no se afirma haberla verificado en un reinicio real durante esta tarea.

## Regresiones automatizadas

- Activación, reinicio simulado, desactivación y nuevo reinicio restauran el modo original, tanto con MUX como sin él.
- Desactivar antes de reiniciar cancela la solicitud.
- Una GPU ya integrada no exige otro reinicio.
- No se sustituye una solicitud de GPU preexistente de otra herramienta.
- Solo se confirma una GPU activa leyendo los valores actuales; una cola válida se indica como pendiente de reinicio.
- Las verificaciones de una cola estable no reescriben continuamente el respaldo.
- El límite pasa a 100 %, se corrigen cambios externos y se restaura el valor original al terminar.
- Las actualizaciones de sesiones activas agregan controles sin sustituir los originales existentes.
- La desinstalación se bloquea si la restauración de GPU sigue pendiente de reiniciar.

La implementación sigue la [conmutación documentada por ASUS Linux](https://opengamingcollective.github.io/asusctl/faq/gpu-switching.html) y utiliza los setters diferidos y el manejador `asus-shutdown`; no llama `ApplyQueuedGpuValue` desde la sesión gráfica.
