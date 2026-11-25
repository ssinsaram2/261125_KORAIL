import pytest

from prompt98.checks import (Finding, apply_fix, mask_template, mask_text, run_checks, score_of, sec_scan,
                             SEC_BY_KEY)
from prompt98.model import Block, Template, Variable


def keys(text):
    return [p.key for p, _ in sec_scan(text)]


@pytest.mark.parametrize("text,key", [
    ("주민번호 900101-1234567 입니다", "rrn"),
    ("주민번호9001011234567", "rrn"),
    ("카드 1234-5678-9012-3456", "card"),
    ("연락처 010-1234-5678", "phone"),
    ("계좌 110-123-456789", "acct"),
    ("메일 hong@korail.com", "email"),
    ("비번 1234", "pw"),
    ("password: abc123", "pw"),
    ("키 sk-abcdefghijklmnop1234", "key"),
    ("서버 192.168.0.10", "ip"),
    ("서버 172.20.1.1", "ip"),
    ("이 자료는 대외비입니다", "conf"),
])
def test_detects(text, key):
    assert key in keys(text)


@pytest.mark.parametrize("text", [
    "회의는 2026-11-25에 합니다",       # 날짜는 계좌가 아님
    "공개 IP 8.8.8.8",
    "172.32.0.1 은 내부망이 아님",
    "버전 1.2.3",
    "open 함수",                        # pin 단어 일부(open) 오탐 없음
])
def test_no_false_positive(text):
    assert keys(text) == []


def test_phone_not_reported_as_account():
    assert keys("010-1234-5678") == ["phone"]


@pytest.mark.parametrize("key,src,want", [
    ("rrn", "900101-1234567", "900101-1******"),
    ("card", "1234-5678-9012-3456", "****-****-****-3456"),
    ("phone", "010-1234-5678", "010-****-5678"),
    ("acct", "110-123-456789", "110-***-****"),
    ("email", "hong@korail.com", "h***@korail.com"),
    ("pw", "비번 1234", "비번 ****"),
    ("key", "sk-abcdefghijklmnop1234", "sk-a****"),
    ("ip", "10.1.2.3", "x.x.x.x"),
])
def test_mask(key, src, want):
    assert mask_text(src, SEC_BY_KEY[key]) == want


def test_mask_template_values_blocks_and_titles():
    t = Template(variables=[Variable("연락처")], values={"연락처": "010-1234-5678"},
                 blocks=[Block("task", title="010-9999-8888 담당", content="전화 {{연락처}} 또는 010-2222-3333")])
    mask_template(t, ["phone"])
    assert t.values["연락처"] == "010-****-5678"
    assert "010-****-3333" in t.blocks[0].content
    assert t.blocks[0].title.startswith("010-****-8888")


def test_score():
    f = [Finding("err", "a"), Finding("warn", "b"), Finding("info", "c"), Finding("ok", "d")]
    assert score_of(f) == 100 - 18 - 8 - 3
    assert score_of([Finding("err", "x")] * 10) == 0


def test_config_checks_and_fixes():
    t = Template(variables=[Variable("안씀")], blocks=[Block("context", content="{{없는변수}} 이야기")])
    r = run_checks(t)
    titles = [f.title for f in r.config]
    assert any("지시사항" in x for x in titles)
    assert any("등록되지 않은 변수" in x for x in titles)
    assert any("쓰이지 않는 변수" in x for x in titles)
    for f in list(r.config):
        if f.fix:
            apply_fix(t, f.fix)
    new_task = next(b for b in t.blocks if b.type == "task")
    assert new_task.content == ""  # 수정 버튼은 빈 블록을 추가하고, 내용은 사용자가 채운다
    new_task.content = "요약해 주세요."
    r2 = run_checks(t)
    assert not [f for f in r2.config if f.level == "err"]
    assert t.var("없는변수") and not t.var("안씀")


def test_security_details_are_masked():
    t = Template(blocks=[Block("task", content="제 번호는 010-1234-5678 입니다. 이걸로 안내문을 만들어 주세요.")])
    r = run_checks(t)
    detail = " ".join(f.detail for f in r.security)
    assert "010-1234-5678" not in detail and "010-****-5678" in detail
    assert r.maskable == ["phone"]


def test_clean_prompt_scores_high():
    t = Template(blocks=[Block("role", content="당신은 행정 전문가입니다."),
                         Block("task", content="신규 직원 안내문을 작성해 주세요. 핵심 일정과 준비물을 포함합니다."),
                         Block("constraint", content="300자 이내"),
                         Block("format", content="제목 / 본문 / 요약 3줄")])
    r = run_checks(t)
    assert r.score == 100
