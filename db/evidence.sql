-- Ejecute interactivamente o con psql -f; los dos ERROR están previstos.
SELECT 'ANTES' AS etapa, * FROM memberships WHERE user_id='luis';
BEGIN;
UPDATE memberships SET can_edit=false WHERE board_id='board-1' AND user_id='luis';
SELECT 'DENTRO DE TRANSACCION' AS etapa, * FROM memberships WHERE user_id='luis';
ROLLBACK;
SELECT 'DESPUES DE ROLLBACK' AS etapa, * FROM memberships WHERE user_id='luis';
BEGIN;
INSERT INTO memberships VALUES ('board-1','ana',true);
-- ERROR esperado: clave primaria duplicada.
ROLLBACK;
BEGIN;
INSERT INTO memberships VALUES ('board-1','usuario-inexistente',true);
-- ERROR esperado: clave foranea users.
ROLLBACK;
