"""[1.3] 변수 형식 '기간'(시작일 ~ 종료일)."""
import pytest

from prompt98 import db
from prompt98.builder import build_prompt
from prompt98.jsonio import export_payload, parse_import
from prompt98.model import (VAR_TYPES, Block, Template, Variable, join_period, period_days, split_period,
                            valid_date)
from prompt98.paths import res
from prompt98.repository import TemplateRepo


def test_period_is_a_variable_type():
    assert VAR_TYPES["period"] == "기간"


@pytest.mark.parametrize("value,expect", [
    ("2026-12-01 ~ 2026-12-05", ("2026-12-01", "2026-12-05")),
    ("2026-12-01~2026-12-05", ("2026-12-01", "2026-12-05")),
    ("2026-12-01", ("2026-12-01", "")),
    ("", ("", "")),
    ("다음 주 중", ("", "")),                      # 예전에 글로 적어 둔 값은 비운 칸으로
])
def test_split_period(value, expect):
    assert split_period(value) == expect


def test_join_period():
    assert join_period("2026-12-01", "2026-12-05") == "2026-12-01 ~ 2026-12-05"
    assert join_period("2026-12-01", "") == "2026-12-01"
    assert join_period("", "") == ""


@pytest.mark.parametrize("s,e,days", [
    ("2026-12-01", "2026-12-05", 5),
    ("2026-12-01", "2026-12-01", 1),
    ("2026-12-28", "2027-01-03", 7),               # 해를 넘김
    ("2026-12-05", "2026-12-01", None),            # 거꾸로
    ("2026-02-30", "2026-03-01", None),            # 없는 날짜
])
def test_period_days(s, e, days):
    assert period_days(s, e) == days


def test_valid_date():
    assert valid_date("2028-02-29") and not valid_date("2027-02-29") and not valid_date("2026-1-1")


def test_period_variable_saved_and_used_in_prompt():
    c = db.connect(":memory:")
    db.migrate(c)
    repo = TemplateRepo(c)
    t = Template(variables=[Variable("교육기간", "period")], values={"교육기간": "2027-01-11 ~ 2027-01-15"},
                 blocks=[Block("task", content="교육 기간: {{교육기간}}")], intro=False)
    repo.save(t)
    got = repo.get(t.id)
    assert got.var("교육기간").type == "period"
    assert build_prompt(got) == "[지시사항]\n교육 기간: 2027-01-11 ~ 2027-01-15"
    items, dropped = parse_import(export_payload([got]))
    assert dropped == 0 and items[0].var("교육기간").type == "period"
    c.close()


def test_upgrade_v3_db_allows_period(tmp_path):
    old = tmp_path / "schema"
    old.mkdir()
    for f in ("001_init.sql", "002_intro.sql", "003_users_blocktypes.sql"):
        (old / f).write_text(res("schema", f).read_text(encoding="utf-8"), encoding="utf-8")
    c = db.connect(tmp_path / "v3.db")
    db.migrate(c, old)
    with c:
        c.execute("INSERT INTO templates(id, uuid, name) VALUES (1, 'u', '예전')")
        c.execute("INSERT INTO variables(template_id, position, name, type, value) VALUES (1, 0, '날짜', 'date', '2026-12-01')")
    with pytest.raises(Exception):
        c.execute("INSERT INTO variables(template_id, position, name, type) VALUES (1, 1, '기간', 'period')")
    assert db.migrate(c) == 4
    c.execute("INSERT INTO variables(template_id, position, name, type) VALUES (1, 1, '기간', 'period')")
    assert TemplateRepo(c).get(1).values["날짜"] == "2026-12-01"     # 예전 변수 값 보존
    c.close()
