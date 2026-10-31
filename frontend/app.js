let version = null;
const el = id => document.getElementById(id);
async function call(path, method='GET', body, admin=false) {
  const headers = {'Content-Type':'application/json','X-User':el('user').value};
  if(admin) headers['X-Lab-Key']=el('key').value;
  try {
    const r = await fetch(path,{method,headers,body:body === undefined ? undefined : JSON.stringify(body)});
    const raw = await r.text();
    let data; try {data=JSON.parse(raw);} catch {data={message:raw};}
    el('status').textContent=`HTTP ${r.status} · ${method} ${path}`;
    el('status').style.color=r.ok ? '#1b633a' : '#990000';
    el('response').textContent=JSON.stringify(data,null,2);
    return r.ok ? data : null;
  } catch(error) {
    el('status').textContent='No se pudo conectar con el servidor';
    el('response').textContent=error.message;
    return null;
  }
}
function apply(data) { if(data) {version=data.version;el('title').value=data.title;el('version').textContent=`Versión ${version}`;} }
el('load').onclick=async()=>apply(await call('/api/boards/board-1'));
el('save').onclick=async()=>{
  if(version===null) {el('status').textContent='Primero cargue una versión.';return;}
  apply(await call('/api/boards/board-1','PUT',{title:el('title').value,expected_version:version}));
};
el('permission').onclick=()=>call('/api/permissions/board-1');
el('touch').onclick=()=>call('/api/presence/board-1','POST');
el('presence').onclick=()=>call('/api/presence/board-1');
el('revoke').onclick=()=>call('/management/permissions/board-1/luis','PUT',{can_edit:false},true);
el('grant').onclick=()=>call('/management/permissions/board-1/luis','PUT',{can_edit:true},true);
el('reset').onclick=async()=>{if(confirm('¿Restablecer título, versión, permisos y presencia de este laboratorio?')) {const r=await call('/api/lab/reset','POST',{},true);if(r)apply(await call('/api/boards/board-1'));}};
