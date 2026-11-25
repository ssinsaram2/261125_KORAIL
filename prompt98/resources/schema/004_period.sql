-- [1.3] 변수 형식에 '기간'(period: 시작일 ~ 종료일)을 더한다.
-- SQLite 는 CHECK 를 고칠 수 없어 variables 표를 다시 만든다(내용·id 보존).
CREATE TABLE variables_new (
    id           INTEGER PRIMARY KEY,
    template_id  INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    type         TEXT    NOT NULL DEFAULT 'text'
                 CHECK (type IN ('text','area','number','date','period','select')),
    options_json TEXT    NOT NULL DEFAULT '[]',
    required     INTEGER NOT NULL DEFAULT 1 CHECK (required IN (0,1)),
    value        TEXT    NOT NULL DEFAULT '',
    UNIQUE (template_id, name)
);
INSERT INTO variables_new (id, template_id, position, name, type, options_json, required, value)
    SELECT id, template_id, position, name, type, options_json, required, value FROM variables;
DROP TABLE variables;
ALTER TABLE variables_new RENAME TO variables;
CREATE INDEX idx_variables_template ON variables(template_id, position);

PRAGMA user_version = 4;
