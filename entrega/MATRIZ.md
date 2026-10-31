# Matriz de decisiones · ARSW-EQP-XX

Integrantes:
- Cristian Aristizábal · carnet 1000104617 · GitHub `Cristian-Aristi`
- Santiago Pinzón · carnet 1000103871 · GitHub `els4nty`

| Dato | Motor elegido | Consulta principal | Qué debe ser atómico | Atraso tolerable | Retención / TTL | Consecuencia de perderlo | Alternativa y costo |
|---|---|---|---|---|---|---|---|
| Membresías y permisos | PostgreSQL (Gestión) | `SELECT can_edit FROM memberships WHERE board_id=$1 AND user_id=$2` (por la PK compuesta) | Dar, quitar o revocar un permiso en una transacción. La PK `(board_id, user_id)` evita membresías repetidas y las FK evitan que existan membresías de usuarios o tableros que no existen | Para escribir, ninguno: si ya se revocó, la siguiente edición tiene que fallar. Para mostrar en pantalla aceptamos hasta 60 s | Mientras exista el tablero | Grave: alguien podría editar sin permiso (o al revés, quedar bloqueado) | Guardar los miembros dentro del documento en MongoDB: perdemos las FK y la unicidad y toca validarlo todo en código. Guardarlos solo en Redis: aquí Redis corre sin persistencia (`--save ""`), un reinicio borra los permisos |
| Contenido del tablero | MongoDB (Contenido) | `findOne({_id})` para leer y `findOneAndUpdate({_id, version:N}, {$set, $inc:{version:1}})` para editar | Comparar la versión, cambiar el título y subir la versión en una sola operación sobre el documento | Al leer puede verse la versión anterior por milisegundos. Al escribir no se acepta perder cambios sin aviso: si la versión es vieja, 409 | Permanente | Alta: se pierde lo que escribió el usuario | PostgreSQL con JSONB (`UPDATE ... WHERE id=$1 AND version=$2`): misma garantía y todo en un motor, pero hay que migrar el servicio y acoplarlo a la base de Gestión |
| Preferencias | MongoDB, embebidas en el tablero (`preferences`) | Se leen siempre junto con el tablero | Van en el mismo documento, así que se guardan junto con el contenido y comparten versión | Igual que el contenido | Permanente; son pocos campos | Baja: vuelven a los valores por defecto | Ponerlas aparte: una lectura más, pero tendrían su propia versión y un cambio de fondo no chocaría con un cambio de título |
| Historial creciente (diseño) | Colección aparte `board_history` en MongoDB (o tabla `board_events` en PostgreSQL) | `find({board_id}).sort({version:-1}).limit(20)` con índice `{board_id:1, version:-1}`, paginando por la última versión vista | Una entrada por versión, con `_id = (board_id, version)` para que no se repita. Idealmente en la misma transacción que la edición (o con patrón outbox) | Segundos; no está en el camino crítico | Configurable, por ejemplo 90 días o las últimas N versiones | Media: perdemos la trazabilidad, no el estado actual | Meterlo dentro del documento: crece sin límite (MongoDB tiene tope de 16 MB) y cada lectura del tablero cargaría todo el historial |
| Presencia | Redis, `SET presence:{board}:{user} online EX 20` | `EXISTS presence:{board}:{user}` | Crear o renovar la clave y su TTL en una sola escritura | Hasta 20 s: puede mostrar como conectado a alguien que ya se fue | TTL de 20 s, se renueva con cada heartbeat | Casi ninguna. Si Redis cae se responde `available:false` y se puede seguir editando | Guardarla en MongoDB con índice TTL: muchas escrituras en una base durable para un dato que no sirve después. Sin Redis tendríamos que hacer exactamente eso o quitar la presencia |
| Caché de permisos | Redis, `permission:{board}:{user}` con `EX 60` | `GET` cuando la interfaz pregunta si mostrar los controles de edición | Nada con la fuente real (es una copia); se escribe con un `SET ... EX` | Hasta 60 s, pero solo para la interfaz. No se usa para autorizar escrituras | TTL de 60 s | Ninguna en cuanto a corrección: si falla, se consulta directo a Gestión | Quitar la caché: la UI siempre pregunta a Gestión (más carga, pero el dato está al día). Invalidarla al revocar: la UI se entera antes, pero igual no sirve para autorizar |

## ¿La distribución inicial es apropiada?

Creemos que sí, pero la versión entregada la usaba mal en dos sitios y eso era lo que fallaba, no la elección de motores.

- **PostgreSQL para membresías.** Gestión es quien decide si alguien puede editar, y eso necesita PK, FK y transacciones. En `evidencias/02-evidencia-sql.txt` se ve: la PK rechaza la membresía repetida de Ana, la FK rechaza a `usuario-inexistente` y el `ROLLBACK` deja a Luis con `can_edit = t` como estaba.
- **MongoDB para el tablero.** Casi siempre se pide el tablero completo y la edición cabe en un documento, así que nos basta con la atomicidad por documento. La base perdía ediciones porque filtraba solo por `_id`; con el filtro por versión se arregla sin cambiar de motor.
- **Redis solo para lo que se puede perder o atrasar.** La presencia y la caché de permisos para la UI. Lo que cambiamos fue sacar a Redis de la decisión de si una escritura se permite.

**Alternativas.**
- PostgreSQL con JSONB para el contenido: es la que más nos convence si algún día hay que cerrar del todo la ventana de revocación (explicada en el ADR), porque permitiría revisar el permiso y guardar en la misma transacción. No la hicimos porque implica migrar el servicio y juntar las dos bases, y el laboratorio no lo pide.
- Quitar Redis: también funcionaría. La caché no es necesaria para que el sistema sea correcto, y la presencia podría ir en MongoDB con TTL. Con los ~20 req/s que medimos no habría problema; con muchos usuarios conectados mandando heartbeats sí conviene tener Redis.

## Preguntas del Bloque A

**¿Qué gana y qué cuesta embeber las preferencias?** Se gana que con una sola lectura llega todo y que preferencias y título se guardan juntos de forma atómica. Cuesta que comparten versión: si alguien cambia el fondo mientras otro cambia el título, uno de los dos recibe 409 aunque no tocaron lo mismo. Como son pocos datos y cambian poco, nos parece buen trato.

**¿Qué pasa si el historial crece sin límite?** Si va dentro del documento, el documento crece sin parar hasta chocar con los 16 MB de MongoDB. Además, cada lectura (lo más frecuente, y lo que probamos con k6) trae todo el historial, y cada edición reescribe un documento cada vez más pesado. Por eso lo diseñamos en una colección aparte con paginación.

**¿PostgreSQL podría resolver también el documento?** Sí. Con JSONB y un `UPDATE ... WHERE version = $2` tendríamos el mismo control optimista, y además permisos y contenido en la misma transacción. El costo es migrar y acoplar los servicios. Es la alternativa que dejamos documentada.

**¿Por qué no guardar los permisos solo en Redis?** Porque Redis aquí no es durable (corre sin persistencia), no tiene FK ni unicidad para cuidar las relaciones y no da transacciones como las de PostgreSQL. Si se cae o se reinicia perdemos la fuente de autorización. Además, la caché con TTL es justo lo que dejaba editar a Luis después de revocado.
