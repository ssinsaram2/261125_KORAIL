import json

import pytest

from prompt98 import db
from prompt98.jsonio import ImportFormatError, export_payload, parse_import
from prompt98.model import Block, Template, Variable
from prompt98.paths import res
from prompt98.repository import AutosaveRepo, CheckRunRepo, ReadOnlyError, SettingsRepo, TemplateRepo


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def repo(conn):
    return TemplateRepo(conn)


def sample():
    return Template(name="테스트", category="문서 작성", title_style="md",
                    variables=[Variable("이름"), Variable("어조", "select", "공식적,친근한", False)],
                    values={"이름": "홍길동", "어조": "친근한"},
                    blocks=[Block("role", content="역할"), Block("task", "할 일", "{{이름}} 님께", enabled=False)])


def test_migrate_is_idempotent(conn):
    assert db.user_version(conn) == 4
    assert db.migrate(conn) == 4
    assert conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 9


def test_save_load_roundtrip(repo):
    t = sample()
    tid = repo.save(t)
    t2 = repo.get(tid)
    assert t2.to_dict() == t.to_dict()


def test_intro_flag_saved(repo):
    t = sample()
    t.intro = False
    repo.save(t)
    assert repo.get(t.id).intro is False
    t.intro = True
    repo.save(t)
    assert repo.get(t.id).intro is True


def test_upgrade_v1_db_keeps_templates_and_turns_intro_on(tmp_path):
    """이미 쓰던(버전 1) DB를 열면 intro 칸이 추가되고 기존 템플릿은 켜짐."""
    from prompt98.paths import res as _res
    v1 = tmp_path / "schema"
    v1.mkdir()
    (v1 / "001_init.sql").write_text(_res("schema", "001_init.sql").read_text(encoding="utf-8"), encoding="utf-8")
    c = db.connect(tmp_path / "old.db")
    db.migrate(c, v1)
    c.execute("INSERT INTO templates(uuid, name) VALUES ('u-1', '예전 템플릿')")
    c.commit()
    assert db.migrate(c) == 4
    t = TemplateRepo(c).get_by_uuid("u-1")
    assert t.intro is True
    c.close()


def test_rename_and_resave_keeps_one_row(repo):
    t = sample()
    repo.save(t)
    t.name = "바뀐 이름"
    t.variables.pop()
    t.values.pop("어조")
    t.blocks.reverse()
    repo.save(t)
    assert repo.count() == 1
    t2 = repo.get(t.id)
    assert t2.name == "바뀐 이름" and len(t2.variables) == 1 and t2.blocks[0].type == "task"


def test_delete_cascades(repo, conn):
    t = sample()
    repo.save(t)
    repo.delete(t.id)
    assert conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM variables").fetchone()[0] == 0


def test_long_name_clipped(repo):
    t = sample()
    t.name = "가" * 100
    repo.save(t)
    assert len(repo.get(t.id).name) == 60


def test_library_seed_and_readonly(repo, conn):
    s = SettingsRepo(conn)
    data = json.loads(res("library.json").read_text(encoding="utf-8"))
    assert repo.seed_library(data, s) is True
    assert repo.count(library=True) == 17
    assert repo.seed_library(data, s) is False  # 같은 버전이면 그대로
    user = sample()
    repo.save(user)
    data["version"] += 1
    assert repo.seed_library(data, s) is True
    assert repo.count(library=True) == 17 and repo.count() == 1  # 사용자 템플릿은 건드리지 않음

    lib = repo.library_by_name("주간 업무 보고서")
    with pytest.raises(ReadOnlyError):
        repo.save(lib)
    with pytest.raises(ReadOnlyError):
        repo.delete(lib.id)
    copy = lib.editable_copy()
    repo.save(copy)
    assert copy.uuid != lib.uuid and repo.count() == 2


def test_settings_and_autosave(conn):
    s = SettingsRepo(conn)
    assert s.get("autosave_seconds") == "2"
    s.set("boot_sound_enabled", False)
    assert s.get_bool("boot_sound_enabled", True) is False
    a = AutosaveRepo(conn)
    assert a.load() is None
    a.save('{"x":1}', 999)  # 없는 템플릿 id 는 NULL 로
    row = a.load()
    assert row["clean_exit"] == 0 and row["template_id"] is None
    a.set_clean_exit(True)
    assert a.load()["clean_exit"] == 1
    a.save('{"x":2}', None)
    assert a.load()["clean_exit"] == 0 and a.load()["payload"] == '{"x":2}'


def test_check_runs(conn):
    CheckRunRepo(conn).add(None, 80, [{"level": "err", "title": "t", "detail": "010-****-5678"}])
    assert conn.execute("SELECT score FROM check_runs").fetchone()[0] == 80


# ---------------------------------------------------------------- JSON
WEB_EXPORT = {
    "app": "prompt98", "version": 1,
    "current": {"name": "현재"},
    "saved": [{"id": "abc123", "name": "주간 업무 보고서", "cat": "문서 작성", "at": 1764000000000,
               "data": {"id": "x", "sid": "abc123", "name": "주간 업무 보고서", "cat": "문서 작성", "ts": "bracket",
                        "vars": [{"id": "v1", "name": "부서명", "type": "text", "opts": "", "req": True},
                                 {"id": "v2", "name": "잘못된 이름!", "type": "text", "opts": "", "req": True},
                                 {"id": "v3", "name": "모양", "type": "color", "opts": "", "req": True}],
                        "values": {"부서명": "여객사업처 영업팀"},
                        "blocks": [{"id": "b1", "type": "role", "title": "역할", "content": "...", "on": True},
                                   {"id": "b2", "type": "chart", "title": "?", "content": "...", "on": True},
                                   {"id": "b3", "type": "task", "title": "지시", "content": "{{부서명}}", "on": False}]}}],
}


def test_import_web_export():
    items, dropped = parse_import(WEB_EXPORT)
    assert len(items) == 1 and dropped == 3
    t = items[0]
    assert [v.name for v in t.variables] == ["부서명"]
    assert [b.type for b in t.blocks] == ["role", "task"] and t.blocks[1].enabled is False
    assert t.values["부서명"] == "여객사업처 영업팀"


def test_export_then_import_roundtrip(repo):
    t = sample()
    payload = json.loads(json.dumps(export_payload([t], current=t), ensure_ascii=False))
    assert payload["app"] == "prompt98" and payload["saved"][0]["data"]["vars"][1]["opts"] == "공식적,친근한"
    items, dropped = parse_import(payload)
    assert dropped == 0
    got = items[0]
    assert got.uuid == t.uuid
    assert [b.to_dict() for b in got.blocks] == [b.to_dict() for b in t.blocks]
    assert got.values == t.values


@pytest.mark.parametrize("bad", [{}, [], {"app": "other"}, "문자열", {"app": "prompt98", "saved": [{"data": {}}]}])
def test_import_rejects_bad(bad):
    with pytest.raises(ImportFormatError):
        parse_import(bad)


def test_import_single_template_and_array():
    one = {"name": "a", "vars": [], "blocks": [{"type": "task", "content": "x"}]}
    assert len(parse_import(one)[0]) == 1
    assert len(parse_import([one, one])[0]) == 2
