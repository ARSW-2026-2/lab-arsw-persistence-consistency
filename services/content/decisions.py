"""ÚNICO archivo de código que deben modificar los estudiantes.
La base arranca, pero los tres TODO incumplen contratos intencionalmente.
Consultar README y docs/CONTRATOS.md antes de cambiar cada función.
"""
from pymongo import ReturnDocument
from redis.exceptions import RedisError

def save_board(collection, board_id, expected_version, title):
    # TODO 1: incluir la versión esperada en el filtro de la misma operación.
    # Debe retornar None si otro usuario ya cambió esa versión; no hacer find+update.
    return collection.find_one_and_update(
        {'_id': board_id},
        {'$set': {'title': title}, '$inc': {'version': 1}},
        return_document=ReturnDocument.AFTER,
    )

def permission_for_write(user, board_id, cached_permission, authoritative_permission):
    # TODO 2: una concesión en caché no prueba que siga vigente.
    # Elegir la fuente para escrituras críticas. Ambas funciones reciben user, board_id.
    # Si la fuente autoritativa falla, dejar propagar el error: la API lo convierte a 503.
    return cached_permission(user, board_id)

def touch_presence(client, key, ttl):
    # TODO 3: usar TTL en la misma escritura. Si Redis falla, retornar False.
    # True = presencia registrada; False = capacidad temporal no disponible.
    client.set(key, 'online')
    return True
