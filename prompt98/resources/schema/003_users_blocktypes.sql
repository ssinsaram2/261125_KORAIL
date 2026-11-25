-- [1.2] 로그인 사용자 + 사용자별 템플릿 + 사용자가 만든 블록 종류

-- 사용자 계정. 비밀번호는 원문 대신 PBKDF2-SHA256 해시와 솔트만 저장한다.
CREATE TABLE users (
    id           INTEGER PRIMARY KEY,
    username     TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT    NOT NULL DEFAULT '',
    pw_hash      TEXT    NOT NULL,
    pw_salt      TEXT    NOT NULL,
    pw_iter      INTEGER NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    last_login   TEXT
);

-- 내 템플릿의 주인 (라이브러리는 NULL = 모두가 같이 씀)
ALTER TABLE templates ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_templates_owner ON templates(owner_id, is_library);

-- 자동 저장이 누구의 작업인지 (다른 사용자가 로그인하면 복구 질문을 하지 않는다)
ALTER TABLE autosave ADD COLUMN user_id INTEGER;

-- 블록 종류를 사용자가 추가할 수 있도록 type 의 고정 목록 CHECK 를 없앤다 (SQLite 는 표를 다시 만들어야 함)
CREATE TABLE blocks_new (
    id           INTEGER PRIMARY KEY,
    template_id  INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,
    type         TEXT    NOT NULL CHECK (length(type) BETWEEN 1 AND 40),
    title        TEXT    NOT NULL DEFAULT '',
    content      TEXT    NOT NULL DEFAULT '',
    enabled      INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1))
);
INSERT INTO blocks_new (id, template_id, position, type, title, content, enabled)
    SELECT id, template_id, position, type, title, content, enabled FROM blocks;
DROP TABLE blocks;
ALTER TABLE blocks_new RENAME TO blocks;
CREATE INDEX idx_blocks_template ON blocks(template_id, position);

PRAGMA user_version = 3;
