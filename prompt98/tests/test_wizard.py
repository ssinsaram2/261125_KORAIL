"""아티팩트 마법사: 자주 쓰는 기능 목록 저장, 결과 템플릿."""
import pytest

from prompt98 import db
from prompt98.builder import INTRO_TEXT, build_prompt
from prompt98.dialogs.wizard import (MAX_QUICK, MAX_QUICK_LEN, QUICK_FEATURES, QUICK_KEY, clean_quick,
                                     load_quick_features, make_template, save_quick_features)
from prompt98.repository import SettingsRepo


@pytest.fixture
def settings():
    c = db.connect(":memory:")
    db.migrate(c)
    yield SettingsRepo(c)
    c.close()


def test_default_list_when_nothing_saved(settings):
    assert load_quick_features(settings) == QUICK_FEATURES
    assert load_quick_features(None) == QUICK_FEATURES


def test_save_and_reload(settings):
    save_quick_features(settings, ["출석 체크", "  QR 코드로   입장 확인 ", "출석 체크", ""])
    assert load_quick_features(settings) == ["출석 체크", "QR 코드로 입장 확인"]


def test_empty_list_is_kept(settings):
    save_quick_features(settings, [])
    assert load_quick_features(settings) == []          # 모두 지웠으면 기본값으로 되살리지 않음


def test_broken_setting_falls_back(settings):
    settings.set(QUICK_KEY, "{망가진 json")
    assert load_quick_features(settings) == QUICK_FEATURES


def test_clean_limits():
    items = clean_quick(["가" * 100] + [f"기능{i}" for i in range(50)])
    assert len(items) == MAX_QUICK and len(items[0]) == MAX_QUICK_LEN


def test_make_template_numbers_features():
    t = make_template("출석부", "교육 출석 관리", "", ["출석 체크", "", "엑셀(CSV)로 내보내기"], "", "", "제작해줘.")
    out = build_prompt(t)
    assert out.startswith("아래의 지시에 따라 아티팩트를 제작해줘.")
    assert "1) 출석 체크\n2) 엑셀(CSV)로 내보내기" in out


def test_wizard_result_has_no_default_intro():
    t = make_template("출석부", "교육 출석 관리", "", ["출석 체크"], "", "", "제작해줘.")
    assert t.intro is False
    assert INTRO_TEXT not in build_prompt(t)


def test_library_intro_off_only_for_self_introducing_templates():
    import json
    from prompt98.model import Template
    from prompt98.paths import res
    lib = json.loads(res("library.json").read_text(encoding="utf-8"))["templates"]
    off = {e["name"] for e in lib if not Template.from_library_entry(e).intro}
    assert off == {"아티팩트 제작 프롬프트 요청", "교육 홍보 이미지"}
