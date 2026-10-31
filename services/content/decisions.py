"""ÚNICO archivo de código que deben modificar los estudiantes.
Contiene las tres decisiones del laboratorio: control optimista de versiones,
fuente autoritativa para escrituras y presencia efímera con degradación.
Consultar README y docs/CONTRATOS.md antes de cambiar cada función.
"""
from pymongo import ReturnDocument
from redis.exceptions import RedisError


def save_board(collection, board_id, expected_version, title):
    """TODO 1 · Control optimista de versiones (compare-and-set).

    La versión esperada forma parte del filtro de la MISMA operación
    find_one_and_update. MongoDB garantiza atomicidad a nivel de documento:
    si dos clientes leyeron la versión N, solo el primero encuentra
    {_id, version: N}; el segundo ya no encuentra coincidencia y recibe None,
    que la API convierte en HTTP 409. La versión se incrementa en la misma
    escritura, de modo que no existe una ventana entre comparar y actualizar.
    """
    return collection.find_one_and_update(
        {'_id': board_id, 'version': expected_version},
        {'$set': {'title': title}, '$inc': {'version': 1}},
        return_document=ReturnDocument.AFTER,
    )


def permission_for_write(user, board_id, cached_permission, authoritative_permission):
    """TODO 2 · Una escritura crítica se autoriza con la fuente autoritativa.

    La caché de permisos (Redis, TTL 60 s) solo se usa para la interfaz.
    Para escribir se consulta Gestión/PostgreSQL en cada petición, por lo que
    una revocación confirmada antes de iniciar la escritura produce 403.
    Si la autoridad no responde, authoritative_permission lanza HTTPException
    503; se deja propagar a propósito: nunca se degrada a la concesión
    cacheada (fail-closed). Costo: una llamada HTTP adicional por escritura y
    dependencia de disponibilidad de Gestión para editar.
    """
    return authoritative_permission(user, board_id)


def touch_presence(client, key, ttl):
    """TODO 3 · Presencia efímera con TTL en una sola escritura.

    SET key value EX ttl crea o renueva la clave y su expiración de forma
    atómica (cada heartbeat reinicia el TTL). Si Redis no responde se retorna
    False: la presencia es una capacidad opcional y su falla no debe impedir
    editar el tablero. Solo se capturan errores de Redis, no errores de
    programación.
    """
    try:
        return bool(client.set(key, 'online', ex=ttl))
    except RedisError:
        return False
