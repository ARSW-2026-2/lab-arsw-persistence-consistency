CREATE TABLE IF NOT EXISTS users (id text PRIMARY KEY, name text NOT NULL);
CREATE TABLE IF NOT EXISTS boards (id text PRIMARY KEY, owner_id text NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS memberships (
  board_id text REFERENCES boards(id), user_id text REFERENCES users(id),
  can_edit boolean NOT NULL DEFAULT false, PRIMARY KEY (board_id, user_id)
);
INSERT INTO users VALUES ('ana','Ana'),('luis','Luis') ON CONFLICT DO NOTHING;
INSERT INTO boards VALUES ('board-1','ana') ON CONFLICT DO NOTHING;
INSERT INTO memberships VALUES ('board-1','ana',true),('board-1','luis',true) ON CONFLICT DO NOTHING;
