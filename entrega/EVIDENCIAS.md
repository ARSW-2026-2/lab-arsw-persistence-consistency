# Evidencias · ARSW-EQP-XX

Cristian Aristizábal (1000104617, `Cristian-Aristi`) · Santiago Pinzón (1000103871, `els4nty`)

## Entorno
- Linux x86_64 · 4 vCPU · 15 GB de RAM disponibles para Docker
- Docker Engine 29.9.2 · Docker Compose v5.6.1
- Imágenes: las de `compose.yaml` (postgres 16.6, mongo 7.0.16, redis 7.4.2, prometheus v3.1.0, grafana 11.5.1, k6 0.57.0, nginx 1.27.3)
- Todas las horas están en **UTC** y son del 31/10/2026. Las capturas del frontend tienen la hora arriba a la derecha y las de Grafana muestran el rango de tiempo.
- La imagen de la API se construyó con una copia del `Dockerfile` que agrega el certificado del proxy de nuestra red (detalle en el ADR). El código es el del repositorio.

## Registro

| Experimento | Inicio / fin (UTC) | Archivo / captura | Resultado observado | Interpretación |
|---|---|---|---|---|
| Smoke y recorrido | 13:01:54 | `evidencias/01-smoke.txt`, `00-compose-ps.txt`, `03-inspeccion-mongo-redis.txt`, `capturas/prometheus-targets.png` | Smoke en `passed: true`, los 8 contenedores arriba, targets `content` y `management` en UP, `board-1` en versión 1 | El entorno arrancó bien. Redis estaba vacío porque nadie había usado la app |
| Baseline (antes) | 13:02:06 – 13:02:30 | `evidencias/04-baseline.txt`, `base-baseline.json`, `capturas/antes-*.png` | Edición concurrente `[200, 200]` y versión de 1 a 3, con el cambio de Luis perdido. Luis revocado guardó con 200. La presencia seguía a los 22 s | Aparecen los tres problemas: se pierden ediciones, la caché decide los permisos y la presencia no expira |
| Redis y Gestión caídos con la base (antes) | 13:02:36 – 13:03:01 | `evidencias/05-base-redis-down.txt`, `06-base-authority-down.txt`, `base-redis-down.json`, `base-authority-down.json` | Con Redis caído, editar dio 200 pero la presencia dio 503. Con Gestión caída, se guardó una edición ("Sin autoridad", versión 2) | La base no sabía degradar la presencia y, peor, dejaba editar sin poder confirmar el permiso |
| Restricciones SQL y rollback | 13:01:55 | `evidencias/02-evidencia-sql.txt` | Después del `ROLLBACK` Luis sigue con `can_edit = t`. Se rechazó la membresía duplicada `(board-1, ana)` por la PK y la de `usuario-inexistente` por la FK | La PK compuesta asegura una sola membresía por usuario y tablero. La FK impide membresías de usuarios que no existen. La transacción deshace la revocación completa |
| Dos pestañas (Exp. 1) | antes 13:05:42 · después 13:09:15 | `capturas/antes-exp1-*.png`, `capturas/despues-exp1-*.png` | Antes: pestaña 1 guarda con 200 (v2) y pestaña 2 también con 200 (v3), pisando a Ana. Después: pestaña 1 con 200 (v2) y pestaña 2 con **409** "Versión obsoleta… recargue" | El 409 no es una caída: el servidor está bien y detectó que Luis editaba sobre una versión vieja. Por eso no aparece en el panel de errores 5xx |
| Revocación desde la interfaz | antes ~13:05:45 · después 13:09:18 | `capturas/antes-rev*.png`, `capturas/despues-rev*.png` | Con el permiso en caché y la revocación ya confirmada, antes guardaba con 200 y ahora da **403** "Permiso de edición revocado" | La escritura ya no le cree a la caché; le pregunta a Gestión |
| Presencia con TTL | ~13:09:20 – 13:09:45 | `capturas/despues-pres*.png` (y `antes-pres*.png`) | Después: Ana aparece al registrar y a los 22 s ya no. Antes: seguía apareciendo | El `SET … EX 20` hace que expire si no se renueva |
| Acceptance con la solución | 13:06:39 – 13:07:02 | `evidencias/08-acceptance.txt`, `solucion-acceptance.json` | 4 de 4 en `passed: true` y código 0 (`[200, 409]` con la versión subiendo una vez, revocado 403, presencia expira) | Los tres TODO cumplen lo que piden los contratos |
| Redis detenido y recuperado | 13:07:09 – 13:07:53 (Redis apagado de 13:07:10 a ~13:07:48) | `evidencias/09-redis-down.txt`, `solucion-redis-down.json`, `10-acceptance-post-redis.txt`, `capturas/grafana-fallos-solucion.png` | `degradacion_redis` pasó: editar 200, presencia 200 con `available:false`. Mandamos 15 heartbeats más; el contador de degradación quedó en 16. En Grafana `lab_dependency_up` de redis bajó a 0 mientras `up` de content seguía en 1. Al volver, `PONG` y acceptance 4/4 (13:08:06) | La presencia se apagó sola y el tablero siguió funcionando |
| Gestión detenida y recuperada | 13:08:29 – 13:09:05 (Gestión apagada desde 13:08:31) | `evidencias/11-authority-down.txt`, `solucion-authority-down.json`, `capturas/grafana-fallos-solucion.png` | Primero dejamos el permiso de Ana en caché (valor `1`, TTL 60). Con Gestión apagada, editar dio **503** "No se puede validar el permiso"; leer el tablero siguió en 200; `up` de management en 0. Al restaurar respondió `alive:true` y reiniciamos el frontend | Preferimos no dejar editar a aceptar un permiso que no podemos confirmar. Mandamos 10 PUT más a propósito para que los 503 se vieran en Grafana |
| Acceptance final | 13:12:33 – 13:12:56 | `evidencias/13-acceptance-final.txt`, `solucion-acceptance-final.json` | 4 de 4 en `passed: true` y código 0 | Todo quedó restaurado |
| Carga k6 (base) | 13:03:28 – 13:05:12 | `evidencias/07-k6-base.txt`, `k6-carga-summary-base.json`, `capturas/grafana-k6-base.png` | 1984 peticiones, 19,8 req/s, P95 **8,83 ms**, P90 7,93 ms, máximo 34,9 ms, 0 % de fallos, checks al 100 %, 0 errores semánticos | Cumple los umbrales (P95 < 500 ms y errores < 1 %) |
| Carga k6 (solución) | 13:09:42 – 13:11:22 | `evidencias/12-k6-solucion.txt`, `k6-carga-summary-solucion.json`, `capturas/grafana-k6-solucion.png` | 1981 peticiones, 19,8 req/s, P95 **9,62 ms**, P90 8,47 ms, máximo 51,3 ms, 0 % de fallos, checks al 100 %, 0 errores semánticos | Prácticamente igual. k6 solo hace `GET` y nuestros cambios tocan las escrituras. La diferencia de ~0,8 ms es ruido de una sola corrida |

En Prometheus, durante las cargas, el P95 del backend (`content`) estaba cerca de 7,2 ms con la base (13:04:30) y 7,9 ms con la solución (13:10:30).

## Preguntas del Bloque C

**¿Qué se degradó de forma controlada?** La presencia. Con Redis caído el heartbeat responde 200 con `available:false`, se cuenta en `lab_degraded_total` y se puede seguir leyendo y editando.

**¿Qué dejó de estar disponible a propósito?** Editar cuando Gestión no responde. Respondemos 503 aunque el permiso esté en caché.

**¿Qué garantía protege eso?** Que una edición solo se acepta si Gestión (PostgreSQL) confirma el permiso en ese momento. Con eso nadie revocado vuelve a editar después de confirmada la revocación, y si no se puede confirmar no se guarda. Al mismo tiempo, el control por versión asegura que nunca se pisa un cambio sin avisar.

**¿Qué cambia si falla MongoDB?** Ahí no hay degradación posible para el contenido: leer y editar dan 503 porque MongoDB es la única copia del tablero. La presencia y la consulta de permisos seguirían funcionando porque no dependen de MongoDB, pero sin el tablero no sirven de mucho. Se vería `lab_dependency_up{dependency="mongo"} = 0` y 5xx en el panel de errores, con `up` todavía en 1.

## Observabilidad

El dashboard se llama **ARSW-EQP-XX · Persistencia** (`entrega/dashboard.json`, uid `arsw-eqp-persistencia`, fuente `prometheus`). Tiene 9 paneles: los 2 que venían (`up` y solicitudes por segundo), los 6 de `docs/OBSERVABILIDAD.md` (P95, errores 5xx, dependencias, aciertos de caché, conflictos y presencia degradada) y el opcional de respuestas por código. Capturas: `capturas/grafana-dashboard-completo.png` (13:00 a 13:11 UTC), `grafana-k6-base.png`, `grafana-fallos-solucion.png` y `grafana-k6-solucion.png`.

**¿Por qué puede subir el contador de conflictos mientras baja la pérdida de cambios?**
Porque cada conflicto es un cambio que no se perdió. En la base las dos ediciones daban 200 y la segunda borraba a la primera sin que nadie lo notara; el contador quedaba en 0 porque el sistema ni se enteraba. Ahora la segunda edición recibe 409 y `lab_conflicts_total` sube. En la gráfica se ven picos de unos 0,018/s entre 13:06 y 13:10, uno por cada acceptance y por la prueba de las dos pestañas. Que haya más conflictos visibles significa que hay menos cambios pisados en silencio.

**¿Por qué el panel de caché no demuestra que una escritura fue autorizada correctamente?**
Porque ese panel solo cuenta las lecturas de permiso que respondió Redis, y ahora esas lecturas solo las hace la interfaz. Que haya muchos aciertos dice que la caché sirve, no que el dato esté al día; de hecho, un acierto justo después de revocar es un dato viejo. Que la autorización funciona lo demuestran las pruebas (revocado da 403, sin Gestión da 503), no esta métrica.

**¿Qué ve Grafana cuando Redis cae, pero la API sigue contestando 200?**
`up` de content sigue en 1 porque Prometheus puede leer `/metrics`, y el panel de 5xx sigue en 0. Lo que cambia es `lab_dependency_up` de redis, que baja a 0, y el panel de presencia degradada, que subió a unos 0,25 op/s entre 13:07:10 y 13:07:48. O sea, el servicio está vivo y responde, pero una parte no funciona: devuelve 200 con `available:false`. Por eso `up` en 1 no quiere decir que todo funcione.

**¿Por qué el P95 de k6 y el P95 del backend no tienen necesariamente el mismo valor?**
k6 mide todo el viaje desde el cliente: la red de Docker, Nginx, la serialización y la aplicación, y calcula el percentil exacto con todas las muestras. El backend solo mide lo que tarda FastAPI, y Prometheus estima el P95 interpolando entre los buckets del histograma, en ventanas de 1 minuto y sin contar `/health` ni `/metrics`. A nosotros nos dio de 8,8 a 9,6 ms en k6 contra 7,2 a 7,9 ms en el backend. Esos ~1,5 ms de diferencia son más o menos Nginx y la red, más el error de estimar con buckets.

## Problemas pendientes

- La ventana entre validar el permiso y guardar no está resuelta (el laboratorio no lo pide). En el ADR dejamos cómo se podría cerrar.
- Si Gestión se cae no se puede editar. Lo decidimos así, pero baja la disponibilidad de la edición; se ve como 503 entre 13:08:31 y 13:09:00.
- El panel de aciertos de caché tiene pocas muestras, porque ahora la caché solo la usa la interfaz (llegó como máximo a 50 %). Que no haya datos no quiere decir que todo esté bien.
- Hicimos una sola corrida de carga por versión y solo con lecturas, así que no podemos sacar conclusiones de rendimiento. No corrimos estrés, pico ni resistencia (eran opcionales).
