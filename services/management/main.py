import asyncio
import os
from contextlib import asynccontextmanager, suppress
import psycopg
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from common.metrics import instrument, DEPS, SERVICE

def connect():
    return psycopg.connect(connect_timeout=2)

def probe():
    try:
        with connect() as conn:
            conn.execute('SELECT 1')
        DEPS.labels(SERVICE, 'postgres').set(1)
    except psycopg.Error:
        DEPS.labels(SERVICE, 'postgres').set(0)

async def monitor():
    while True:
        await asyncio.to_thread(probe)
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(monitor())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

app = FastAPI(title='ARSW · Gestión de tableros', lifespan=lifespan)
instrument(app)

class Permission(BaseModel):
    can_edit: bool

@app.get('/permissions/{board}/{user}')
def permission(board: str, user: str):
    try:
        with connect() as conn:
            row = conn.execute('SELECT can_edit FROM memberships WHERE board_id=%s AND user_id=%s', (board,user)).fetchone()
        return {'can_edit':bool(row and row[0])}
    except psycopg.Error:
        raise HTTPException(503, 'PostgreSQL no disponible: no se puede validar el permiso')

@app.put('/permissions/{board}/{user}')
def set_permission(board: str, user: str, body: Permission, x_lab_key: str = Header('')):
    if x_lab_key != os.getenv('LAB_ADMIN_KEY','lab-admin'):
        raise HTTPException(403, 'Clave de administración de laboratorio incorrecta')
    try:
        with connect() as conn:
            row = conn.execute('UPDATE memberships SET can_edit=%s WHERE board_id=%s AND user_id=%s RETURNING user_id', (body.can_edit,board,user)).fetchone()
            if not row:
                raise HTTPException(404, 'Membresía inexistente')
        return {'user':user, 'can_edit':body.can_edit}
    except psycopg.Error:
        raise HTTPException(503, 'PostgreSQL no disponible')
