import asyncio
import os
from contextlib import asynccontextmanager, suppress
import httpx
import redis
from redis.exceptions import RedisError
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from common.metrics import instrument, DEPS, SERVICE, CACHE, CONFLICTS, DEGRADED
from services.content import decisions

mongo = MongoClient(os.getenv('MONGO_URI','mongodb://mongo:27017'), serverSelectionTimeoutMS=1500, connectTimeoutMS=1500, socketTimeoutMS=2000)
boards = mongo.boards.documents
cache = redis.Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'), decode_responses=True, socket_connect_timeout=.3, socket_timeout=.3)
MGMT = os.getenv('MANAGEMENT_URL','http://management:8000')
CACHE_TTL = 60
PRESENCE_TTL = 20

def authoritative_permission(user, board_id):
    try:
        r = httpx.get(f'{MGMT}/permissions/{board_id}/{user}', timeout=2)
        r.raise_for_status()
        return r.json()['can_edit']
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, 'No se puede validar el permiso; escritura no autorizada')

def cached_permission(user, board_id):
    key = f'permission:{board_id}:{user}'
    try:
        value = cache.get(key)
        if value is not None:
            CACHE.labels('hit').inc()
            return value == '1'
        CACHE.labels('miss').inc()
    except RedisError:
        CACHE.labels('error').inc()
    allowed = authoritative_permission(user, board_id)
    try:
        cache.set(key, '1' if allowed else '0', ex=CACHE_TTL)
    except RedisError:
        pass
    return allowed

def check_user(user):
    if user not in ('ana','luis'):
        raise HTTPException(400, 'Usuario de demostración: ana o luis')

def public(doc):
    return {'id':doc['_id'], 'title':doc['title'], 'version':doc['version'], 'preferences':doc.get('preferences',{})}

def probe():
    for name, fn in [('mongo', lambda: mongo.admin.command('ping')), ('redis', cache.ping)]:
        try:
            fn()
            DEPS.labels(SERVICE, name).set(1)
        except (PyMongoError, RedisError):
            DEPS.labels(SERVICE, name).set(0)
    try:
        r = httpx.get(f'{MGMT}/permissions/board-1/ana', timeout=2)
        DEPS.labels(SERVICE, 'management').set(int(r.status_code==200))
    except httpx.HTTPError:
        DEPS.labels(SERVICE, 'management').set(0)

async def monitor():
    while True:
        await asyncio.to_thread(probe)
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app):
    boards.update_one({'_id':'board-1'}, {'$setOnInsert':{'title':'Tablero ARSW','version':1,'preferences':{'background':'white'}}}, upsert=True)
    task = asyncio.create_task(monitor())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    mongo.close()
    cache.close()

app = FastAPI(title='ARSW · Contenido y colaboración', lifespan=lifespan)
instrument(app)

class Edit(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    expected_version: int = Field(ge=1)

@app.get('/boards/{board_id}')
def read_board(board_id: str):
    # El tablero de demostración es público para lectura, edición requiere permiso.
    try:
        doc = boards.find_one({'_id':board_id})
        if not doc:
            raise HTTPException(404, 'Tablero inexistente')
        return public(doc)
    except PyMongoError:
        raise HTTPException(503, 'MongoDB no disponible')

@app.get('/permissions/{board_id}')
def read_permission(board_id: str, x_user: str = Header('ana')):
    check_user(x_user)
    return {'can_edit':cached_permission(x_user, board_id), 'source':'cache-or-management', 'ttl_seconds':CACHE_TTL}

@app.put('/boards/{board_id}')
def edit_board(board_id: str, body: Edit, x_user: str = Header('ana')):
    check_user(x_user)
    if not decisions.permission_for_write(x_user, board_id, cached_permission, authoritative_permission):
        raise HTTPException(403, 'Permiso de edición revocado o inexistente')
    try:
        doc = decisions.save_board(boards, board_id, body.expected_version, body.title)
        if doc is None:
            CONFLICTS.inc()
            raise HTTPException(409, 'Versión obsoleta o tablero inexistente: recargue antes de editar')
        return public(doc)
    except PyMongoError:
        raise HTTPException(503, 'MongoDB no disponible')

@app.post('/presence/{board_id}')
def presence(board_id: str, x_user: str = Header('ana')):
    check_user(x_user)
    try:
        ok = decisions.touch_presence(cache, f'presence:{board_id}:{x_user}', PRESENCE_TTL)
    except RedisError:
        # La base falla aquí; TODO 3 debe manejar la degradación en decisions.py.
        raise HTTPException(503, 'Redis no disponible: implementar degradación')
    if not ok:
        DEGRADED.labels('presence').inc()
    return {'available':bool(ok), 'ttl_seconds':PRESENCE_TTL if ok else None}

@app.get('/presence/{board_id}')
def list_presence(board_id: str):
    try:
        users = [u for u in ('ana','luis') if cache.exists(f'presence:{board_id}:{u}')]
        return {'available':True, 'users':users}
    except RedisError:
        return {'available':False, 'users':[]}

@app.post('/lab/reset')
def reset(x_lab_key: str = Header('')):
    if x_lab_key != os.getenv('LAB_ADMIN_KEY','lab-admin'):
        raise HTTPException(403, 'Clave incorrecta')
    try:
        boards.replace_one({'_id':'board-1'}, {'_id':'board-1','title':'Tablero ARSW','version':1,'preferences':{'background':'white'}}, upsert=True)
        for key in ('permission:board-1:ana','permission:board-1:luis','presence:board-1:ana','presence:board-1:luis'):
            cache.delete(key)
        for user in ('ana','luis'):
            r = httpx.put(f'{MGMT}/permissions/board-1/{user}', json={'can_edit':True}, headers={'X-Lab-Key':x_lab_key}, timeout=2)
            r.raise_for_status()
        return {'reset':True}
    except (PyMongoError, RedisError, httpx.HTTPError):
        raise HTTPException(503, 'Restablezca dependencias antes de reiniciar los datos')
