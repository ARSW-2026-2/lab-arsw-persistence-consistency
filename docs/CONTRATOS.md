# Contratos observables

| Operación | Contrato a implementar | Estado inicial |
|---|---|---|
| Dos PUT con igual versión | Exactamente un 200 y un 409; versión aumenta una vez | Ambos guardan y se pierde un cambio |
| PUT iniciado después de revocación confirmada | 403, documento intacto, incluso con permiso cacheado | Caché permite escribir durante su TTL |
| PUT sin autoridad accesible | 503; no aceptar una concesión vieja | La caché puede ocultar la falla |
| Heartbeat | Presencia caduca a los 20 s sin renovación | Clave sin expiración |
| Heartbeat con Redis detenido | 200 + `available:false`, métrica de degradación | 503 |
| Edición válida con Redis detenido | 200 si MongoDB y Gestión/PostgreSQL responden | El adaptador de caché ya tiene fallback |

`save_board` devuelve el documento actualizado o `None` si no coincide la condición. La API transforma `None` en 409 (incluye tablero inexistente en esta demo simplificada).

`permission_for_write` retorna un booleano. El callback autoritativo puede lanzar HTTPException 503; no debe transformarse en un permiso concedido.

`touch_presence` retorna un booleano; capture errores específicos de Redis, no cualquier excepción de programación. Use el argumento `ttl`, no un número duplicado.

La autorización y la escritura ocurren en servicios distintos. Hay una ventana entre comprobar el permiso y escribir. Una garantía estricta frente a revocaciones concurrentes exigiría otro protocolo o una frontera transaccional diferente. El laboratorio exige rechazo cuando la revocación termina antes de comenzar la nueva escritura.

No use IDs de usuarios o tableros como etiquetas Prometheus: produciría cardinalidad innecesaria. Los detalles de cada caso pertenecen a resultados y logs.
