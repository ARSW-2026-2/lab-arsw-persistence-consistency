"""Pruebas de aceptación con resultados JSON. Solo datos ficticios del laboratorio."""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import time
import httpx
BASE = os.getenv('BASE_URL','http://localhost:8080')
KEY = os.getenv('LAB_ADMIN_KEY','lab-admin')
results=[]
def request(method,path,body=None,user='ana'):
    return httpx.request(method,BASE+path,json=body,headers={'X-User':user,'X-Lab-Key':KEY},timeout=10)
def require(r,status=200):
    if r.status_code!=status:
        raise RuntimeError(f'{r.request.method} {r.request.url}: HTTP {r.status_code}: {r.text[:200]}')
    return r.json()
def record(name,ok,evidence):
    results.append({'test':name,'passed':bool(ok),'evidence':evidence})
def reset():
    require(request('POST','/api/lab/reset'))
def smoke():
    require(request('GET','/api/health'))
    require(request('GET','/management/health'))
    b=require(request('GET','/api/boards/board-1'))
    record('arranque',b['version']>=1,b)
def conflict():
    reset()
    b=require(request('GET','/api/boards/board-1'))
    def edit(user):
        return request('PUT','/api/boards/board-1',{'title':'Cambio de '+user,'expected_version':b['version']},user)
    with ThreadPoolExecutor(2) as pool:
        responses=list(pool.map(edit,['ana','luis']))
    final=require(request('GET','/api/boards/board-1'))
    statuses=sorted(r.status_code for r in responses)
    record('ediciones_concurrentes',statuses==[200,409] and final['version']==b['version']+1,{'statuses':statuses,'before':b,'after':final})
def revoke():
    reset()
    prime=require(request('GET','/api/permissions/board-1',user='luis'))
    require(request('PUT','/management/permissions/board-1/luis',{'can_edit':False}))
    try:
        r=request('PUT','/api/boards/board-1',{'title':'Cambio prohibido','expected_version':1},'luis')
        final=require(request('GET','/api/boards/board-1'))
        record('permiso_revocado',prime['can_edit'] and r.status_code==403 and final['version']==1,{'cached_before':prime,'write_status':r.status_code,'after':final})
    finally:
        require(request('PUT','/management/permissions/board-1/luis',{'can_edit':True}))
def expiry():
    reset()
    require(request('POST','/api/presence/board-1'))
    initial=require(request('GET','/api/presence/board-1'))
    time.sleep(22)
    after=require(request('GET','/api/presence/board-1'))
    record('presencia_expira',initial['available'] and 'ana' in initial['users'] and after['available'] and 'ana' not in after['users'],{'before':initial,'after_22s':after})
def redis_down():
    # No reset: Redis debe estar detenido antes de invocar esta prueba.
    b=require(request('GET','/api/boards/board-1'))
    edit=request('PUT','/api/boards/board-1',{'title':'Edicion sin Redis','expected_version':b['version']})
    presence=request('POST','/api/presence/board-1')
    record('degradacion_redis',edit.status_code==200 and presence.status_code==200 and presence.json().get('available') is False,{'edit_status':edit.status_code,'presence_status':presence.status_code,'presence':presence.text})
def authority_down():
    # Preparar caché y detener management según README antes de ejecutar.
    b=require(request('GET','/api/boards/board-1'))
    edit=request('PUT','/api/boards/board-1',{'title':'Sin autoridad','expected_version':b['version']})
    record('autoridad_no_disponible',edit.status_code==503,{'edit_status':edit.status_code,'body':edit.text})
parser=argparse.ArgumentParser()
parser.add_argument('mode', choices=['baseline','acceptance','smoke','reset','redis-down','authority-down'])
args=parser.parse_args()
try:
    if args.mode in ('baseline','acceptance'):
        smoke();conflict();revoke();expiry()
    elif args.mode=='smoke': smoke()
    elif args.mode=='reset': reset();record('reset',True,{})
    elif args.mode=='redis-down': redis_down()
    else: authority_down()
except Exception as exc:
    record('ejecucion',False,{'error':str(exc)})
report={'mode':args.mode,'utc':datetime.now(timezone.utc).isoformat(),'results':results}
Path('results').mkdir(exist_ok=True)
name=f"{args.mode}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
Path('results',name).write_text(json.dumps(report,indent=2,ensure_ascii=False))
print(json.dumps(report,indent=2,ensure_ascii=False))
print('Resultado guardado en results/'+name)
# Baseline registra defectos esperados; no oculta problemas de arranque o ejecución.
failed=[x for x in results if not x['passed']]
if args.mode=='baseline':
    failed=[x for x in failed if x['test'] in ('arranque','ejecucion')]
raise SystemExit(1 if failed else 0)
