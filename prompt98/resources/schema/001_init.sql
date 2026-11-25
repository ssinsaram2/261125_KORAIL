PRAGMA foreign_keys = ON;

CREATE TABLE categories (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE templates (
    id           INTEGER PRIMARY KEY,
    uuid         TEXT    NOT NULL UNIQUE,                 -- 내보내기·가져오기용 고유값
    name         TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    description  TEXT    NOT NULL DEFAULT '',
    title_style  TEXT    NOT NULL DEFAULT 'bracket'
                 CHECK (title_style IN ('none','bracket','md','num')),
    is_library   INTEGER NOT NULL DEFAULT 0 CHECK (is_library IN (0,1)),
    created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_templates_category ON templates(category_id);
CREATE INDEX idx_templates_library  ON templates(is_library, name);

CREATE TABLE blocks (
    id           INTEGER PRIMARY KEY,
    template_id  INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,                         -- 0부터, 저장 시 재번호
    type         TEXT    NOT NULL
                 CHECK (type IN ('role','context','task','constraint','format','example','text')),
    title        TEXT    NOT NULL DEFAULT '',
    content      TEXT    NOT NULL DEFAULT '',
    enabled      INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1))
);
CREATE INDEX idx_blocks_template ON blocks(template_id, position);

CREATE TABLE variables (
    id           INTEGER PRIMARY KEY,
    template_id  INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    type         TEXT    NOT NULL DEFAULT 'text'
                 CHECK (type IN ('text','area','number','date','select')),
    options_json TEXT    NOT NULL DEFAULT '[]',            -- select 형식의 선택지 배열
    required     INTEGER NOT NULL DEFAULT 1 CHECK (required IN (0,1)),
    value        TEXT    NOT NULL DEFAULT '',              -- 현재 입력값(=기본값)
    UNIQUE (template_id, name)
);
CREATE INDEX idx_variables_template ON variables(template_id, position);

CREATE TABLE settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

CREATE TABLE autosave (
    id          INTEGER PRIMARY KEY CHECK (id = 1),       -- 항상 1행
    payload     TEXT    NOT NULL,                          -- 현재 작업 JSON
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    clean_exit  INTEGER NOT NULL DEFAULT 0,
    saved_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE check_runs (                                  -- 점검 기록(선택 기능)
    id            INTEGER PRIMARY KEY,
    template_id   INTEGER REFERENCES templates(id) ON DELETE CASCADE,
    score         INTEGER NOT NULL,
    findings_json TEXT    NOT NULL,                        -- 민감값 원문은 저장하지 않음(마스킹 후)
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TRIGGER trg_templates_touch AFTER UPDATE ON templates
BEGIN
    UPDATE templates SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;

INSERT INTO categories(name, sort_order) VALUES
 ('문서 작성',1),('데이터·분석',2),('고객·민원',3),('교육·홍보',4),
 ('기획·아이디어',5),('아티팩트 제작',6),('안전·현장',7),('요약·번역',8),('기타',99);

PRAGMA user_version = 1;
