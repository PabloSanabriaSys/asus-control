# Validación 0.4.3

Se corrige el bloqueo de controles al apagar el ahorro cuando la GPU debe volver a su modo anterior después de reiniciar.

- El respaldo conserva solo la GPU pendiente tras verificar los demás originales. Los controles manuales vuelven a estar disponibles y sus valores dejan de auditarse contra el respaldo anterior.
- Si se reactiva durante esa espera, se guardan los valores manuales actuales sin perder el original de la GPU.
- Las restauraciones fallidas siguen mostrando el error y permiten reintentar; una espera normal de reinicio no bloquea los controles.

Pruebas automáticas: 141 aprobadas, incluyendo cambios manuales durante la espera, reconciliación, reinicio simulado y reactivación antes del reinicio. Ruff, formato, mypy y sintaxis de los scripts correctos.

Prueba real con el backend instalado: al apagar el ahorro quedó únicamente `gpu.configuration` pendiente y sin errores. Se cambió el límite manualmente a 80 %, se ejecutó reconciliación y se verificó que permanecía en 80 %. Después se devolvió el límite original de 60 % y se reactivó el ahorro, como estaba al comenzar; volvió a 100 % sin errores. No se reinició el equipo para esta comprobación.
