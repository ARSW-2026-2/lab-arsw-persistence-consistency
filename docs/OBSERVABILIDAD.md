# Construir el tablero y explicar la evidencia

Duplique el dashboard inicial y conserve sus paneles de `up` y solicitudes/s. Añada estos **seis paneles** usando la fuente Prometheus. Use panel Time series salvo que prefiera State timeline para dependencias. Títulos y unidades deben ser claros.

| Panel | PromQL | Unidad / interpretación |
|---|---|---|
| P95 por servicio | `histogram_quantile(0.95, sum by (le, service) (rate(lab_http_duration_seconds_bucket[1m])))` | segundos; estimación por buckets |
| Errores técnicos | `sum by (service) (rate(lab_http_requests_total{status=~"5.."}[1m]))` | solicitudes/s con 5xx |
| Dependencias | `lab_dependency_up` | 1/0 por servicio y dependencia |
| Aciertos de caché | `sum(rate(lab_cache_total{result="hit"}[1m])) / clamp_min(sum(rate(lab_cache_total{result=~"hit|miss"}[1m])), 0.000001)` | fracción 0–1; excluye errores Redis |
| Conflictos de edición | `sum(rate(lab_conflicts_total[1m]))` | conflictos/s; eventos esperados bajo edición concurrente |
| Presencia degradada | `sum(rate(lab_degraded_total{feature="presence"}[1m]))` | operaciones/s degradadas, aunque sean HTTP 200 |

Si no hay datos todavía, provoque el evento: carga para HTTP, consultar permiso dos veces para caché, edición obsoleta para conflicto, heartbeat con Redis caído para degradación. No convierta ausencia de muestras en una prueba de que el sistema está sano.

Opcional: respuestas por código `sum by (service,status) (rate(lab_http_requests_total[1m]))`. Separar 403/409 de fallos técnicos permite explicar por qué rechazar una operación puede ser correcto.

Disponibilidad técnica observada entre peticiones: puede estimarse como `1 - (tasa de 5xx / tasa total)` en una ventana con tráfico y servicios observables. No es una medición completa de disponibilidad de negocio: omite solicitudes que nunca llegaron, silencios y resultados 200 incorrectos. `up` tampoco cubre esos casos.

## Secuencia recomendada

1. Últimos 15 minutos, refresh 5 s; comprobar targets.
2. Carga k6 sin fallos; registrar P95, tasa y recursos del equipo.
3. Sin k6 activo, ejecutar acceptance: ubicar conflictos y revocación.
4. Detener Redis; enviar heartbeats y editar: comparar `up`, dependencia y degradación.
5. Restaurar Redis y comprobar recuperación.
6. Registrar hora inicio/fin de cada experimento y exportar el dashboard JSON.

**Cuatro respuestas obligatorias:**

- ¿Por qué puede subir el contador de conflictos mientras baja la pérdida de cambios?
- ¿Por qué el panel de caché no demuestra que una escritura fue autorizada correctamente?
- ¿Qué ve Grafana cuando Redis cae, pero la API sigue contestando 200?
- ¿Por qué el P95 de k6 y el P95 del backend no tienen necesariamente el mismo valor?

Los histogramas registran solicitudes del backend sin `/health` ni `/metrics`. La lectura de permisos de los sondeos sí genera tráfico en Gestión. Los recursos de las bases (CPU, conexiones, memoria) no están instrumentados con exporters en esta práctica; la métrica de dependencia solo comprueba conectividad.
