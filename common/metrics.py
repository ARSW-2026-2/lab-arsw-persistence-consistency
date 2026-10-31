import os
import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
SERVICE = os.getenv('SERVICE_NAME', 'test')
REQUESTS = Counter('lab_http_requests_total', 'Respuestas HTTP del servicio', ['service','route','method','status'])
LATENCY = Histogram('lab_http_duration_seconds', 'Latencia HTTP del servicio', ['service','route','method'], buckets=(.005,.01,.025,.05,.1,.25,.5,1,2,5))
DEPS = Gauge('lab_dependency_up', 'Sondeo de dependencia; 1 disponible', ['service','dependency'])
CACHE = Counter('lab_cache_total', 'Consultas de cache de permisos', ['result'])
CONFLICTS = Counter('lab_conflicts_total', 'Ediciones rechazadas por version')
DEGRADED = Counter('lab_degraded_total', 'Operaciones degradadas', ['feature'])
def instrument(app):
    @app.middleware('http')
    async def observe(request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            path = request.url.path
            if path not in ('/metrics', '/health'):
                route = request.scope.get('route')
                template = getattr(route, 'path', 'unmatched')
                REQUESTS.labels(SERVICE, template, request.method, str(status)).inc()
                LATENCY.labels(SERVICE, template, request.method).observe(time.perf_counter()-start)
    @app.get('/metrics', include_in_schema=False)
    def metrics():
        return Response(generate_latest(), headers={'Content-Type':CONTENT_TYPE_LATEST})
    @app.get('/health')
    def health():
        return {'service':SERVICE, 'alive':True}
