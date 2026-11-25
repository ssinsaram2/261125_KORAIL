from prompt98.builder import (INTRO_TEXT, build_prompt, build_segments, missing_vars, rename_variable,
                              substitute, used_vars)
from prompt98.history import History
from prompt98.model import Block, Template, Variable


def tpl(**kw):
    """블록 조립만 보는 테스트용: 첫 문장(intro)은 기본으로 끈다."""
    t = Template(variables=[Variable("부서명"), Variable("기간")], values={"부서명": "영업팀", "기간": ""},
                 blocks=[Block("role", content="당신은 기획자입니다."),
                         Block("task", content="{{부서명}}의 {{기간}} 보고서를 쓰세요.")], intro=False)
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def test_new_template_has_intro_by_default():
    assert Template().intro is True and Template.blank().intro is True


def test_intro_is_first_sentence():
    t = tpl(intro=True)
    out = build_prompt(t)
    assert out.startswith(INTRO_TEXT + "\n\n[역할]\n당신은")
    segs = build_segments(t)
    assert segs[0] == (INTRO_TEXT, "intro") and "".join(s for s, _ in segs) == out


def test_intro_off():
    assert not build_prompt(tpl(intro=False)).startswith(INTRO_TEXT)


def test_intro_not_added_to_empty_prompt():
    t = Template(blocks=[Block("task", content="   ")])
    assert t.intro and build_prompt(t) == "" and build_segments(t) == []


def test_substitute_filled_and_missing():
    assert substitute("{{a}}와 {{b}}", {"a": "1", "b": ""}) == "1와 {{b}}"


def test_substitute_spaces_inside_braces():
    assert substitute("{{ 부서명 }} 팀", {"부서명": "영업"}) == "영업 팀"


def test_whitespace_value_counts_as_empty():
    assert substitute("{{a}}", {"a": "   "}) == "{{a}}"


def test_disabled_and_blank_blocks_excluded():
    t = tpl()
    t.blocks.append(Block("format", content="   "))
    t.blocks.append(Block("example", content="숨김", enabled=False))
    out = build_prompt(t)
    assert "숨김" not in out and "[출력 형식]" not in out
    assert out.count("\n\n") == 1  # 블록 두 개 사이 빈 줄 하나


def test_title_styles():
    t = tpl(title_style="none")
    assert build_prompt(t).startswith("당신은")
    t.title_style = "bracket"
    assert build_prompt(t).startswith("[역할]\n당신은")
    t.title_style = "md"
    assert "## 지시사항\n" in build_prompt(t)
    t.title_style = "num"
    assert "2. 지시사항\n" in build_prompt(t)


def test_segments_match_text_and_tags():
    t = tpl()
    segs = build_segments(t)
    assert "".join(s for s, _ in segs) == build_prompt(t)
    tags = {s: tag for s, tag in segs}
    assert tags["영업팀"] == "filled"
    assert tags["{{기간}}"] == "missing"
    assert tags["[역할]"] == "heading"


def test_used_and_missing():
    t = tpl()
    assert used_vars(t) == ["부서명", "기간"]
    assert missing_vars(t) == ["기간"]


def test_rename_variable_updates_blocks_and_values():
    t = tpl()
    rename_variable(t, "부서명", "팀명")
    assert t.var("팀명") and not t.var("부서명")
    assert "{{팀명}}" in t.blocks[1].content
    assert t.values["팀명"] == "영업팀"


def test_history_undo_redo():
    h = History(limit=3)
    for s in "abcd":
        h.push(s)
    assert len(h) == 3  # 가장 오래된 것은 버림
    assert h.undo("e") == "d"
    assert h.redo("d") == "e"
    h.push("x")
    assert not h.can_redo()


def test_template_dict_roundtrip():
    t = tpl()
    t2 = Template.from_dict(t.to_dict())
    assert t2.to_dict() == t.to_dict()
