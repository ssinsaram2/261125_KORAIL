"""[1.2] 로그인·회원가입, 사용자별 자료, 사용자 블록 종류, 스키마 3판."""
import json

import pytest

from prompt98 import auth, db
from prompt98.jsonio import export_payload, import_block_types, parse_import
from prompt98.model import (BLOCK_TYPES, Block, Template, block_name, custom_block_types, set_custom_block_types)
from prompt98.paths import res
from prompt98.repository import (AuthError, AutosaveRepo, SettingsRepo, TemplateRepo, UserRepo, sample_uuid)

SAMPLES = json.loads(res("samples.json").read_text(encoding="utf-8"))


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def users(conn):
    return UserRepo(conn, iterations=1_000)   # 테스트는 빠르게(실제는 200,000회)


@pytest.fixture(autouse=True)
def reset_block_types():
    set_custom_block_types([])
    yield
    set_custom_block_types([])


# ---------------------------------------------------------------- 비밀번호
def test_password_is_hashed_not_stored(conn, users):
    users.create("korail01", "Train2026", "홍길동", confirm="Train2026")
    row = conn.execute("SELECT * FROM users").fetchone()
    assert "Train2026" not in " ".join(str(v) for v in tuple(row))
    assert len(row["pw_hash"]) == 64 and len(row["pw_salt"]) == 32


def test_same_password_different_salt():
    h1, s1, _ = auth.hash_password("Train2026", iterations=1000)
    h2, s2, _ = auth.hash_password("Train2026", iterations=1000)
    assert s1 != s2 and h1 != h2
    assert auth.verify_password("Train2026", h1, s1, 1000)
    assert not auth.verify_password("train2026", h1, s1, 1000)


@pytest.mark.parametrize("uid,pw,confirm,msg", [
    ("ab", "Train2026", "Train2026", "아이디는"),
    ("한글아이디", "Train2026", "Train2026", "아이디는"),
    ("korail01", "short1", "short1", "8~64자"),
    ("korail01", "onlyletters", "onlyletters", "영문과 숫자"),
    ("korail01", "korail01xx9", "korail01xx9", "아이디를 그대로"),
    ("korail01", "Train2026", "Train2027", "일치하지"),
])
def test_signup_rules(users, uid, pw, confirm, msg):
    with pytest.raises(AuthError, match=msg):
        users.create(uid, pw, confirm=confirm)


def test_duplicate_username_case_insensitive(users):
    users.create("korail01", "Train2026")
    with pytest.raises(AuthError, match="이미 쓰고"):
        users.create("KORAIL01", "Train2026")


def test_login(users):
    u = users.create("korail01", "Train2026", "홍길동")
    assert users.authenticate("korail01", "Train2026").id == u.id
    assert users.authenticate("korail01", "wrong1234") is None
    assert users.authenticate("nobody", "Train2026") is None
    assert u.label == "홍길동"


def test_change_password(users):
    u = users.create("korail01", "Train2026")
    with pytest.raises(AuthError, match="지금 비밀번호"):
        users.change_password(u.id, "nope", "NewPass99", "NewPass99")
    users.change_password(u.id, "Train2026", "NewPass99", "NewPass99")
    assert users.authenticate("korail01", "NewPass99") and not users.authenticate("korail01", "Train2026")


def test_login_throttle():
    now = [0.0]
    t = auth.LoginThrottle(limit=3, lock_seconds=30, clock=lambda: now[0])
    for _ in range(3):
        t.failed("Kim")
    assert t.wait_seconds("kim") == 30
    now[0] = 31
    assert t.wait_seconds("kim") == 0


# ---------------------------------------------------------------- 사용자별 자료
def test_templates_and_settings_are_per_user(conn, users):
    a, b = users.create("alice01", "Train2026"), users.create("bob0001", "Train2026")
    ra, rb = TemplateRepo(conn, a.id), TemplateRepo(conn, b.id)
    sa, sb = SettingsRepo(conn, a.id), SettingsRepo(conn, b.id)
    t = Template(name="앨리스 것", blocks=[Block("task", content="x")])
    ra.save(t)
    assert [x.name for x in ra.list()] == ["앨리스 것"] and rb.list() == []
    assert rb.get_by_uuid(t.uuid) is None
    with pytest.raises(Exception):
        rb.delete(t.id)
    sa.set("wizard_quick_features", '["A"]')
    assert sb.get("wizard_quick_features") is None
    sa.set("boot_sound_enabled", False)          # 프로그램 설정은 모두가 같이 씀
    assert sb.get_bool("boot_sound_enabled", True) is False


def test_samples_seeded_per_user(conn, users):
    a, b = users.create("alice01", "Train2026"), users.create("bob0001", "Train2026")
    n = len(SAMPLES["templates"])
    assert len(TemplateRepo(conn, a.id).seed_samples(SAMPLES, SettingsRepo(conn, a.id))) == n
    assert len(TemplateRepo(conn, b.id).seed_samples(SAMPLES, SettingsRepo(conn, b.id))) == n
    assert TemplateRepo(conn, a.id).count() == n and TemplateRepo(conn, b.id).count() == n
    assert TemplateRepo(conn, b.id).get_by_uuid(sample_uuid(b.id, "열차 지연 안내문")).name == "열차 지연 안내문"


def test_first_user_takes_over_pre_login_data(conn, users):
    old = TemplateRepo(conn)                      # 로그인 기능 전(주인 없음)
    old.seed_samples(SAMPLES, SettingsRepo(conn))
    SettingsRepo(conn).set("last_template_uuid", "u-old")
    AutosaveRepo(conn).save("{}", None)
    first = users.create("korail01", "Train2026")
    assert TemplateRepo(conn, first.id).count() == len(SAMPLES["templates"])
    s = SettingsRepo(conn, first.id)
    assert s.get("last_template_uuid") == "u-old"
    assert TemplateRepo(conn, first.id).seed_samples(SAMPLES, s) == []      # 예시를 또 넣지 않음
    assert AutosaveRepo(conn).load()["user_id"] == first.id
    second = users.create("bob0001", "Train2026")
    assert TemplateRepo(conn, second.id).count() == 0                       # 두 번째 가입자는 받지 않음


# ---------------------------------------------------------------- 사용자 블록 종류
def test_custom_block_types_register_and_save(conn, users):
    u = users.create("korail01", "Train2026")
    defs = set_custom_block_types([{"key": "c_ref", "name": "참고 자료", "color": "#005f87"},
                                   {"key": "c_bad", "name": ""},                       # 이름 없음 → 버림
                                   {"key": "role", "name": "가짜"},                    # 기본 키 → 버림
                                   {"key": "c_dup", "name": "역할"}])                  # 기본 이름과 겹침 → 버림
    assert [d["key"] for d in defs] == ["c_ref"] and block_name("c_ref") == "참고 자료"
    repo = TemplateRepo(conn, u.id)
    t = Template(blocks=[Block("c_ref", content="자료 링크")])
    repo.save(t)
    assert repo.get(t.id).blocks[0].type == "c_ref"
    set_custom_block_types([])                                                         # 종류를 지워도
    got = repo.get(t.id).blocks[0]
    assert got.type == "c_ref" and got.title == "참고 자료" and "c_ref" not in BLOCK_TYPES   # 블록은 남음


def test_json_carries_custom_block_types():
    set_custom_block_types([{"key": "c_ref", "name": "참고 자료", "color": "#005f87"}])
    t = Template(blocks=[Block("c_ref", content="링크"), Block("task", content="요약")])
    payload = json.loads(json.dumps(export_payload([t]), ensure_ascii=False))
    assert payload["blockTypes"][0]["name"] == "참고 자료"
    set_custom_block_types([])                     # 다른 PC: 이 종류가 없음
    assert parse_import(payload)[1] == 1           # 등록 전에는 그 블록이 버려지고
    set_custom_block_types(import_block_types(payload))
    items, dropped = parse_import(payload)         # 등록하면 살아남는다
    assert dropped == 0 and items[0].blocks[0].type == "c_ref"
    assert custom_block_types()[0]["key"] == "c_ref"


# ---------------------------------------------------------------- 스키마 3판
def test_upgrade_v2_db_keeps_blocks(tmp_path):
    v2 = tmp_path / "schema"
    v2.mkdir()
    for f in ("001_init.sql", "002_intro.sql"):
        (v2 / f).write_text(res("schema", f).read_text(encoding="utf-8"), encoding="utf-8")
    c = db.connect(tmp_path / "old.db")
    db.migrate(c, v2)
    with c:   # 2판 DB에 예전 방식으로 쓴 자료
        c.execute("INSERT INTO templates(id, uuid, name) VALUES (1, 'u-old', '예전')")
        c.execute("INSERT INTO blocks(template_id, position, type, content) VALUES (1, 0, 'role', '역할 내용')")
        c.execute("INSERT INTO blocks(template_id, position, type, content) VALUES (1, 1, 'task', '할 일')")
    with pytest.raises(Exception):
        c.execute("INSERT INTO blocks(template_id, position, type) VALUES (1, 9, 'c_new')")  # 2판은 막힘
    assert db.migrate(c) == 4
    t = TemplateRepo(c).list()[0]
    got = TemplateRepo(c).get(t.id)
    assert [b.content for b in got.blocks] == ["역할 내용", "할 일"]
    c.execute("INSERT INTO blocks(template_id, position, type) VALUES (?, 9, 'c_new')", (t.id,))  # 3판은 됨
    c.close()
