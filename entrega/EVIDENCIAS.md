# Evidencias · ARSW-EQP-XX

## Entorno
- Sistema operativo: Linux (kernel 6.18, x86_64), contenedor de desarrollo en la nube
- CPU / RAM: 4 vCPU · 15 GB RAM disponibles para Docker (sin límite adicional configurado)
- Docker Engine 29.9.2 · Docker Compose v5.6.1
- Imágenes: las fijadas en `compose.yaml` (postgres 16.6, mongo 7.0.16, redis 7.4.2, prometheus v3.1.0, grafana 11.5.1, k6 0.57.0, nginx 1.27.3)
- Zona horaria de todos los registros: **UTC** (2026-10-31). Las capturas llevan una marca horaria UTC en la esquina superior derecha y las de Grafana muestran el rango temporal.
- Nota: la imagen de la API se construyó con una copia local del `Dockerfile` que solo añade la CA del proxy de red del entorno (ver ADR, sección de reproducibilidad). El código y el `Dockerfile` del repositorio son los mismos.

## Registro

| Experimento | Inicio / fin (UTC) | Archivo / captura | Resultado observado | Interpretación |
|---|---|---|---|---|
| Smoke y recorrido | 13:01:54 | `evidencias/01-smoke.txt`, `00-compose-ps.txt`, `03-inspeccion-mongo-redis.txt`, `capturas/prometheus-targets.png` | `arranque: passed`; 8 contenedores `healthy`/`Up`; targets `content` y `management` UP; documento `board-1` versión 1 | El entorno arranca; Redis vacío antes de usar la app |
| Baseline (antes) | 13:02:06 – 13:02:30 | `evidencias/04-baseline.txt`, `base-baseline.json`, `capturas/antes-*.png` | Concurrencia `[200,200]` y versión 1→3 (título de Luis perdido); revocado → **200** y versión 2; presencia sigue a los 22 s | Los tres defectos esperados: edición perdida, caché usada como autoridad, clave sin TTL |
| Base con Redis / autoridad caídos (antes) | 13:02:36 – 13:03:01 | `evidencias/05-base-redis-down.txt`, `06-base-authority-down.txt`, `base-redis-down.json`, `base-authority-down.json` | Redis caído: edición 200, presencia **503**. Gestión caída: edición **200** ("Sin autoridad", versión 2) | La base no degrada la presencia y, peor, autoriza escrituras con un permiso cacheado sin poder validarlo |
| Restricciones SQL y rollback | 13:01:55 | `evidencias/02-evidencia-sql.txt` | `ROLLBACK` deja `can_edit=t` para Luis; PK duplicada `(board-1, ana)` rechazada; FK `usuario-inexistente` rechazada | PK compuesta = una sola membresía por usuario y tablero; FK = no hay membresías huérfanas; la transacción revierte la revocación completa |
| Dos pestañas (Exp. 1) | antes 13:05:42 · después 13:09:15 | `capturas/antes-exp1-*.png`, `capturas/despues-exp1-*.png` | Antes: pestaña 1 **200** v2, pestaña 2 **200** v3 (sobrescribe a Ana). Después: pestaña 1 **200** v2, pestaña 2 **409** "Versión obsoleta… recargue" | El 409 es un rechazo de negocio correcto (el servidor detectó la versión obsoleta), no una caída: no aparece en el panel de 5xx |
| Revocación desde la UI | antes 13:05:4x · después 13:09:18 | `capturas/antes-rev*.png`, `capturas/despues-rev*.png` | Con permiso cacheado y revocación confirmada: antes **200**, después **403** "Permiso de edición revocado" | La escritura consulta la autoridad, no la caché |
| Presencia con TTL | después 13:09:2x – 13:09:4x | `capturas/despues-pres*.png` (y `antes-pres*.png`) | Después: `users:["ana"]` en t=0 y `users:[]` a los 22 s. Antes: seguía presente | `SET … EX 20` expira sin renovación |
| Acceptance corregido | 13:06:39 – 13:07:02 | `evidencias/08-acceptance.txt`, `solucion-acceptance.json` | 4/4 `passed: true`, exit 0 (`[200,409]`, versión +1; revocado 403; presencia expira) | TODO 1–3 cumplen contratos |
| Redis detenido y recuperación | 13:07:09 – 13:07:53 (Redis detenido 13:07:10 – ~13:07:48) | `evidencias/09-redis-down.txt`, `solucion-redis-down.json`, `10-acceptance-post-redis.txt`, `capturas/grafana-fallos-solucion.png` | `degradacion_redis: passed` (edición 200, presencia 200 `available:false`); 16 heartbeats degradados; `lab_dependency_up{dependency="redis"}=0` mientras `up{job="content"}=1`; `PING → PONG` y acceptance 4/4 después (13:08:06) | Degradación controlada: la capacidad opcional se apaga y el contenido sigue |
| Autoridad detenida y recuperación | 13:08:29 – 13:09:05 (Gestión detenida 13:08:31) | `evidencias/11-authority-down.txt`, `solucion-authority-down.json`, `capturas/grafana-fallos-solucion.png` | Permiso de Ana cacheado (`GET` → `1`, TTL 60). Edición → **503** "No se puede validar el permiso". Lectura del tablero 200. `up{job="management"}=0`. Gestión restaurada (`alive:true`) + `restart frontend` | Fail-closed: indisponibilidad deliberada de la escritura para no aceptar una concesión vieja. Los 503 aparecen en el panel de errores técnicos (10 PUT adicionales a propósito) |
| Acceptance final de cierre | 13:12:33 – 13:12:56 | `evidencias/13-acceptance-final.txt`, `solucion-acceptance-final.json` | 4/4 `passed: true`, exit 0 | Todas las dependencias restauradas |
| Carga k6 (base) | 13:03:28 – 13:05:12 | `evidencias/07-k6-base.txt`, `k6-carga-summary-base.json`, `capturas/grafana-k6-base.png` | 1 984 req, 19,8 req/s, P95 **8,83 ms**, P90 7,93 ms, máx 34,9 ms, 0 % fallos, checks 100 %, 0 errores semánticos | Umbrales cumplidos (P95 < 500 ms, errores < 1 %) |
| Carga k6 (solución) | 13:09:42 – 13:11:22 | `evidencias/12-k6-solucion.txt`, `k6-carga-summary-solucion.json`, `capturas/grafana-k6-solucion.png` | 1 981 req, 19,8 req/s, P95 **9,62 ms**, P90 8,47 ms, máx 51,3 ms, 0 % fallos, checks 100 %, 0 errores semánticos | Sin diferencia relevante: k6 solo lee (`GET /boards`) y los cambios afectan escrituras. La variación de ~0,8 ms está dentro del ruido de una sola corrida |

Backend (Prometheus, `histogram_quantile` sobre buckets, ventana 1 m) durante la carga: P95 de `content` ≈ 7,2 ms (base, 13:04:30) y ≈ 7,9 ms (solución, 13:10:30).

## Observabilidad

Dashboard **ARSW-EQP-XX · Persistencia** (`entrega/dashboard.json`, uid `arsw-eqp-persistencia`, fuente `prometheus`) con 9 paneles: los 2 iniciales (`up` y solicitudes/s), los 6 de `docs/OBSERVABILIDAD.md` (P95, 5xx, dependencias, aciertos de caché, conflictos y presencia degradada) y el opcional de respuestas por código. Capturas: `capturas/grafana-dashboard-completo.png` (13:00–13:11 UTC), `grafana-k6-base.png`, `grafana-fallos-solucion.png`, `grafana-k6-solucion.png`.

**¿Por qué puede subir el contador de conflictos mientras baja la pérdida de cambios?**
Porque cada conflicto es justamente una pérdida de cambios evitada. En la base las dos escrituras concurrentes respondían 200 y la segunda sobrescribía a la primera sin que nadie se enterara; el contador quedaba en 0 porque el sistema no detectaba nada. Con el CAS por versión, la segunda escritura se rechaza con 409 y `lab_conflicts_total` aumenta (picos de ≈0,018/s en 13:06–13:10, uno por cada ejecución de acceptance y del experimento de dos pestañas). Más conflictos visibles = menos sobrescrituras silenciosas.

**¿Por qué el panel de caché no demuestra que una escritura fue autorizada correctamente?**
El panel mide la fracción de *lecturas* de permiso servidas por Redis (`lab_cache_total` solo se incrementa en `cached_permission`, que ahora solo usa la consulta de la UI). Una tasa alta de aciertos dice que la caché es útil para la interfaz, no que el valor sea vigente; precisamente un acierto tras una revocación es una respuesta *desactualizada*. La corrección de la autorización se demuestra con el contrato (PUT revocado → 403, autoridad caída → 503) en acceptance y authority-down, no con métricas de caché.

**¿Qué ve Grafana cuando Redis cae, pero la API sigue contestando 200?**
`up{job="content"}` sigue en 1 (Prometheus puede leer `/metrics`) y el panel de 5xx sigue en 0; en cambio `lab_dependency_up{service="content",dependency="redis"}` baja a 0 y el panel *Presencia degradada* sube (≈0,25 ops/s entre 13:07:10 y 13:07:48). Es decir, el servicio está vivo y responde, pero una capacidad está degradada: un HTTP 200 con `available:false`. Por eso `up` no equivale a disponibilidad funcional.

**¿Por qué el P95 de k6 y el P95 del backend no tienen necesariamente el mismo valor?**
k6 mide el recorrido completo del cliente (red de Docker, Nginx como proxy, serialización y la aplicación), y calcula el percentil exacto sobre todas las muestras de la corrida. El backend mide solo el procesamiento dentro de FastAPI y Prometheus *estima* el P95 interpolando entre los límites de los buckets del histograma, en ventanas móviles de 1 minuto y excluyendo `/health` y `/metrics`. En nuestra corrida: k6 P95 ≈ 8,8–9,6 ms frente a backend ≈ 7,2–7,9 ms; la diferencia (~1,5 ms) corresponde aproximadamente a Nginx + red, más el error de estimación por buckets.

## Problemas pendientes

- **Ventana validar→escribir:** no está resuelta (ni se pide); documentada en el ADR con alternativas (misma transacción en PostgreSQL+JSONB, token/época de permisos).
- **Bloqueo de ediciones si Gestión cae:** es intencional (fail-closed), pero reduce la disponibilidad de la edición; se ve como 503 en el panel de errores técnicos durante 13:08:31–13:09:00.
- **Métrica de caché con pocas muestras:** como la caché ya no participa en escrituras, el panel de aciertos solo tiene datos cuando alguien consulta el permiso desde la UI (máx. 50 % en nuestras ventanas). La ausencia de datos no es evidencia de salud.
- **Una sola corrida de carga por versión, solo lecturas:** no permite concluir diferencias de rendimiento; las pruebas de estrés, pico y resistencia no se ejecutaron (opcionales).
- **Número de equipo e integrantes:** completar `ARSW-EQP-XX` y la lista de integrantes antes de entregar.
