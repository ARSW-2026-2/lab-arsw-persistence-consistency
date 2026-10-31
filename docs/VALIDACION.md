# Validación del paquete

Antes de la entrega se verificaron:

- 21 pruebas automatizadas de políticas y endpoints, con dobles de MongoDB/Redis y de la autoridad de permisos.
- Diferencias intencionales entre base y solución docente: conflicto, caché obsoleta, TTL y degradación.
- Rechazo por 403/409/503, payload inválido y etiquetas de métricas sin IDs de tableros.
- Sintaxis Python/JavaScript, parseo de YAML/JSON, montajes y enlaces relativos.
- Compose contra el esquema oficial de Compose Specification.

**Límite:** el entorno de preparación no dispone de Docker. No se ejecutó aquí el conjunto de contenedores ni se midió rendimiento real. Los dobles validan comportamiento de código, no sustituyen las pruebas con motores reales.

Antes de la clase, el profesor debe ejecutar el arranque y smoke en su equipo. La guía docente contiene el recorrido de aceptación completo; `.github/workflows/smoke.yml` permite comprobar el arranque en GitHub Actions al publicar.

Los resultados de rendimiento deben producirse en cada equipo, no se suministran cifras inventadas.
