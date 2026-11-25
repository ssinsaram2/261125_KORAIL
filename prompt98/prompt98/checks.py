"""구성·보안 점검 (GUI와 무관한 순수 함수)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .builder import build_prompt, is_filled, used_vars, missing_vars
from .model import Template, Block

LEVELS = ("ok", "info", "warn", "err")


@dataclass
class Finding:
    level: str              # 'ok' | 'info' | 'warn' | 'err'
    title: str
    detail: str = ""
    fix: str | None = None  # 'addblock:task' / 'mkvar:이름' / 'delvar:이름' / 'mask:rrn'
    fix_label: str = ""

    def to_dict(self) -> dict:
        return {"level": self.level, "title": self.title, "detail": self.detail}


@dataclass
class SecPattern:
    key: str
    name: str
    regex: re.Pattern
    mask: Callable[[str], str] | None = None
    skip: Callable[[str], bool] | None = None
    note: str = ""

    def should_skip(self, s: str) -> bool:
        return bool(self.skip and self.skip(s))


_A = re.ASCII  # \b, \d 를 웹판(JS)과 같이 ASCII 기준으로

SEC_PATTERNS: list[SecPattern] = [
    SecPattern("rrn", "주민등록번호", re.compile(r"\b\d{6}-?[1-4]\d{6}\b", _A),
               mask=lambda s: re.sub(r"^(\d{6}-?\d)\d{6}$", r"\1******", s)),
    SecPattern("card", "카드번호", re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b", _A),
               mask=lambda s: "****-****-****-" + s[-4:]),
    SecPattern("phone", "휴대전화 번호", re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b", _A),
               mask=lambda s: re.sub(r"^(01\d-?)\d{3,4}(-?\d{4})$", r"\1****\2", s)),
    SecPattern("acct", "계좌번호로 보이는 숫자", re.compile(r"\b\d{3,6}-\d{2,6}-\d{3,7}\b", _A),
               skip=lambda s: bool(re.match(r"^01[016789]-", s) or re.match(r"^\d{6}-[1-4]\d{6}$", s)
                                   or re.match(r"^\d{4}-\d{2}-\d{2}$", s)),
               mask=lambda s: re.sub(r"^(\d+)-.*$", r"\1-***-****", s)),
    SecPattern("email", "이메일 주소", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+", _A),
               mask=lambda s: s[0] + "***@" + s.split("@", 1)[1]),
    SecPattern("pw", "비밀번호·PIN",
               re.compile(r"(비밀번호|비번|패스워드|암호|(?<![A-Za-z])(?:password|passwd|pw|pin))"
                          r"(\s*(?:은|는|:|：|=)?\s*)([A-Za-z0-9!@#$%^&*]{3,})", _A | re.I),
               mask=lambda s: re.sub(r"([A-Za-z0-9!@#$%^&*]{3,})$", "****", s),
               note="아티팩트나 프롬프트가 공유되면 그대로 노출됩니다. 시연용 임시 값인지 확인하고, "
                    "실제 쓰는 비밀번호라면 바꾸세요."),
    SecPattern("key", "API 키·토큰",
               re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}"
                          r"|AIza[0-9A-Za-z_-]{20,})\b", _A),
               mask=lambda s: s[:4] + "****"),
    SecPattern("ip", "내부망 IP 주소",
               re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}"
                          r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b", _A),
               mask=lambda s: "x.x.x.x"),
    SecPattern("conf", "대외비 표시", re.compile(r"대외비|기밀|사내\s?한정|내부\s?용|confidential", re.I),
               note="외부 AI 서비스에 넣어도 되는 자료인지 보안 규정을 확인하세요."),
]
SEC_BY_KEY = {p.key: p for p in SEC_PATTERNS}

VAGUE_RE = re.compile(r"적당히|알아서|대충|잘\s?좀|좋게|멋지게")


# ---------------------------------------------------------------- 보안
def sec_scan(text: str) -> list[tuple[SecPattern, str]]:
    out = []
    for p in SEC_PATTERNS:
        for m in p.regex.finditer(text):
            if not p.should_skip(m.group(0)):
                out.append((p, m.group(0)))
    return out


def mask_text(text: str, p: SecPattern) -> str:
    if not p.mask:
        return text
    return p.regex.sub(lambda m: m.group(0) if p.should_skip(m.group(0)) else p.mask(m.group(0)), text)


def mask_template(t: Template, keys: list[str]) -> None:
    """입력값·블록 내용·블록 제목 모두에서 민감 정보를 가린다(제자리 수정)."""
    for k in keys:
        p = SEC_BY_KEY.get(k)
        if not p or not p.mask:
            continue
        for name, val in list(t.values.items()):
            t.values[name] = mask_text(str(val), p)
        for b in t.blocks:
            b.content = mask_text(b.content, p)
            b.title = mask_text(b.title, p)


# ---------------------------------------------------------------- 점수
def score_of(findings: list[Finding]) -> int:
    n = {lv: sum(1 for f in findings if f.level == lv) for lv in LEVELS}
    return max(0, 100 - 18 * n["err"] - 8 * n["warn"] - 3 * n["info"])


@dataclass
class CheckResult:
    config: list[Finding] = field(default_factory=list)
    security: list[Finding] = field(default_factory=list)
    score: int = 100
    maskable: list[str] = field(default_factory=list)

    @property
    def all(self) -> list[Finding]:
        return self.config + self.security

    def problems(self, which: str) -> int:
        lst = self.config if which == "config" else self.security
        return sum(1 for f in lst if f.level != "ok")


def check_config(t: Template, text: str | None = None) -> list[Finding]:
    text = build_prompt(t) if text is None else text
    c: list[Finding] = []
    on: list[Block] = [b for b in t.blocks if b.enabled]
    has = lambda typ: any(b.type == typ and b.content.strip() for b in on)  # noqa: E731
    reg = {v.name for v in t.variables}
    used = used_vars(t)

    if not on:
        c.append(Finding("err", "포함된 블록이 없어요", "블록을 추가하거나 \"프롬프트에 포함\"을 켜세요."))
    empty = [b for b in on if not b.content.strip()]
    if empty:
        c.append(Finding("warn", f"비어 있는 블록 {len(empty)}개",
                         ", ".join(b.title for b in empty) + " — 내용이 없으면 프롬프트에서 빠집니다."))
    c.append(Finding("ok", "지시사항이 있어요") if has("task") or has("text") else
             Finding("err", "무엇을 해 달라는지(지시사항)가 없어요", "AI가 할 일을 한 문장으로 적어 주세요.",
                     "addblock:task", "지시사항 블록 추가"))
    c.append(Finding("ok", "역할이 정해져 있어요") if has("role") else
             Finding("info", "역할 블록이 없어요 (권장)", "\"당신은 ~ 전문가입니다\"처럼 역할을 주면 답의 수준이 안정됩니다.",
                     "addblock:role", "역할 블록 추가"))
    c.append(Finding("ok", "출력 형식이 정해져 있어요") if has("format") else
             Finding("warn", "출력 형식이 없어요", "표, 목록, 글자 수 등 원하는 결과 모양을 정하면 다시 묻는 일이 줄어듭니다.",
                     "addblock:format", "출력 형식 블록 추가"))
    c.append(Finding("ok", "조건·제약이 있어요") if has("constraint") else
             Finding("info", "조건·제약이 없어요 (권장)", "\"입력에 없는 내용은 지어내지 말 것\" 같은 한 줄이 실수를 줄입니다.",
                     "addblock:constraint", "조건 블록 추가"))
    for k in used:
        if k not in reg:
            c.append(Finding("err", f"등록되지 않은 변수 「{k}」", "블록에 쓰였지만 변수 영역에 없어서 입력 칸이 생기지 않아요.",
                             f"mkvar:{k}", "변수 만들기"))
    used_all = set(used_vars(t, only_enabled=False))
    for v in t.variables:
        if v.name not in used_all:
            c.append(Finding("info", f"쓰이지 않는 변수 {v.name}", "어느 블록에도 들어가 있지 않아요.",
                             f"delvar:{v.name}", "변수 삭제"))
    miss = [k for k in missing_vars(t) if k in reg and t.var(k).required]
    if miss:
        c.append(Finding("warn", f"필수 입력값 {len(miss)}개가 비어 있어요", ", ".join(miss)))
    if text and len(text) < 40:
        c.append(Finding("warn", "프롬프트가 너무 짧아요", f"{len(text)}자 — 상황이나 조건을 조금 더 적어 보세요."))
    if len(text) > 8000:
        c.append(Finding("info", "프롬프트가 꽤 길어요", f"{len(text):,}자 — 핵심 지시가 묻히지 않도록 맨 앞에 두세요."))
    vague = list(dict.fromkeys(VAGUE_RE.findall(text)))
    if vague:
        c.append(Finding("info", "모호한 표현이 있어요",
                         f"{', '.join(vague)} → 분량·기준·예시처럼 구체적으로 바꾸면 결과가 일정해집니다."))
    return c


def check_security(text: str) -> tuple[list[Finding], list[str]]:
    groups: dict[str, list[str]] = {}
    for p, hit in sec_scan(text):
        groups.setdefault(p.key, []).append(hit)
    out = []
    for key, hits in groups.items():
        p = SEC_BY_KEY[key]
        shown = [p.mask(h) if p.mask else h for h in dict.fromkeys(hits)][:4]  # 원문 대신 마스킹 값만 표시
        detail = (p.note + " " if p.note else "") + "발견: " + ", ".join(shown)
        out.append(Finding("warn" if key == "conf" else "err", f"{p.name} {len(hits)}건", detail,
                           f"mask:{key}" if p.mask else None, "마스킹" if p.mask else ""))
    if not out:
        out.append(Finding("ok", "개인정보·비밀번호·키 등 민감 정보가 보이지 않아요",
                           "자동 검사는 형식으로만 찾습니다. 실명·사내 수치는 직접 한 번 더 확인하세요."))
    maskable = [k for k in groups if SEC_BY_KEY[k].mask]
    return out, maskable


def run_checks(t: Template) -> CheckResult:
    text = build_prompt(t)
    config = check_config(t, text)
    security, maskable = check_security(text)
    return CheckResult(config, security, score_of(config + security), maskable)


def apply_fix(t: Template, fix: str) -> None:
    """점검 결과의 원클릭 수정(마스킹 제외 — 그건 mask_template)."""
    action, _, arg = fix.partition(":")
    if action == "addblock":
        t.blocks.append(Block(arg))
    elif action == "mkvar":
        from .model import Variable, valid_var_name
        if valid_var_name(arg) and not t.var(arg):
            t.variables.append(Variable(arg))
            t.values.setdefault(arg, "")
    elif action == "delvar":
        t.variables = [v for v in t.variables if v.name != arg]
        t.values.pop(arg, None)
    elif action == "mask":
        mask_template(t, [arg])


__all__ = ["Finding", "CheckResult", "SEC_PATTERNS", "sec_scan", "mask_text", "mask_template",
           "run_checks", "check_config", "check_security", "score_of", "apply_fix", "is_filled"]
