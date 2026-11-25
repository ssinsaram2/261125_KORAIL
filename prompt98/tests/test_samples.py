"""코레일 예시(내 템플릿) 시드와 예시 내용 품질."""
import json

import pytest

from prompt98 import db
from prompt98.builder import missing_vars, used_vars
from prompt98.checks import run_checks
from prompt98.model import BLOCK_TYPES, CATEGORIES, VAR_TYPES, Template
from prompt98.paths import res
from prompt98.repository import SettingsRepo, TemplateRepo

SAMPLES = json.loads(res("samples.json").read_text(encoding="utf-8"))


@pytest.fixture
def conn_users():
    from prompt98.repository import UserRepo
    c = db.connect(":memory:")
    db.migrate(c)
    yield c, UserRepo(c, iterations=1_000)
    c.close()


@pytest.fixture
def repo_settings():
    c = db.connect(":memory:")
    db.migrate(c)
    yield TemplateRepo(c), SettingsRepo(c)
    c.close()


V1 = json.loads(res("samples_history", "v1.json").read_text(encoding="utf-8"))


def test_ten_samples():
    assert len(SAMPLES["templates"]) == 10
    assert len({t["name"] for t in SAMPLES["templates"]}) == 10


def test_samples_use_date_and_period_types():
    types = {v["type"] for t in SAMPLES["templates"] for v in t["vars"]}
    assert {"date", "period", "select", "area", "number", "text"} <= types


def test_upgrade_replaces_only_untouched_samples(repo_settings):
    repo, s = repo_settings
    repo.seed_samples(V1, s)                                    # 예전(v1) 예시 7개
    assert repo.count() == 7
    edited = next(x for x in repo.list() if x.name == "보도자료 초안")
    t = repo.get(edited.id)
    t.values["제목"] = "사용자가 고친 제목"
    repo.save(t)
    changed = repo.seed_samples(SAMPLES, s)                     # v2 로 업그레이드
    assert len(changed) == 9                                    # 손대지 않은 6개 갱신 + 새 3개
    assert repo.count() == 10
    kept = repo.get(edited.id)
    assert kept.values["제목"] == "사용자가 고친 제목" and kept.var("운행기간") is None   # 고친 것은 그대로
    weekly = repo.get_by_uuid(next(x.uuid for x in repo.list() if x.name == "신규 직원 교육 안내 공지"))
    assert weekly.var("교육기간").type == "period"              # 손대지 않은 것은 새 내용
    assert repo.seed_samples(SAMPLES, s) == []                  # 같은 버전은 다시 안 함


def test_upgrade_takes_over_pre_login_samples(conn_users):
    conn, users = conn_users
    TemplateRepo(conn).seed_samples(V1, SettingsRepo(conn))      # 로그인 기능 전(주인 없음)
    u = users.create("korail01", "Train2026")                    # 첫 가입자가 넘겨받음
    repo, s = TemplateRepo(conn, u.id), SettingsRepo(conn, u.id)
    s.set("samples_version", 1)
    repo.seed_samples(SAMPLES, s)
    assert repo.count() == 10                                    # 예전 7개 갱신 + 새 3개 (중복 없음)


def test_seed_adds_user_templates_in_file_order(repo_settings):
    repo, s = repo_settings
    added = repo.seed_samples(SAMPLES, s)
    assert len(added) == len(SAMPLES["templates"]) >= 5
    names = [x.name for x in repo.list(library=False)]
    assert names == [t["name"] for t in SAMPLES["templates"]]   # 열기 목록에 파일 순서대로
    assert repo.count(library=True) == 0                          # 라이브러리가 아니라 내 템플릿


def test_seed_runs_once_and_respects_user_changes(repo_settings):
    repo, s = repo_settings
    repo.seed_samples(SAMPLES, s)
    first = repo.list(library=False)
    # 사용자가 하나 지우고 하나 고침
    repo.delete(first[0].id)
    t = repo.get(first[1].id)
    t.values[t.variables[0].name] = "사용자가 고친 값"
    repo.save(t)
    assert repo.seed_samples(SAMPLES, s) == []                    # 같은 버전: 다시 안 넣음
    assert repo.count() == len(first) - 1
    newer = dict(SAMPLES, version=SAMPLES["version"] + 1)
    added = repo.seed_samples(newer, s)                            # 새 버전: 빠진 것만 다시
    assert len(added) == 1
    assert repo.get(first[1].id).values[t.variables[0].name] == "사용자가 고친 값"


@pytest.mark.parametrize("entry", SAMPLES["templates"], ids=lambda e: e["name"])
def test_sample_is_complete_and_clean(entry):
    assert entry["cat"] in CATEGORIES
    assert all(b["type"] in BLOCK_TYPES for b in entry["blocks"])
    assert all(v["type"] in VAR_TYPES for v in entry["vars"])
    t = Template.from_library_entry(entry)
    names = {v.name for v in t.variables}
    assert set(used_vars(t, only_enabled=False)) == names          # 미등록·미사용 변수 없음
    assert missing_vars(t) == []                                   # 값이 모두 채워져 있음
    for v in t.variables:
        if v.type == "select":
            assert t.values[v.name] in v.options()
    r = run_checks(t)
    assert not [f for f in r.security if f.level != "ok"], [f.title for f in r.security]
    assert not [f for f in r.config if f.level == "err"]
