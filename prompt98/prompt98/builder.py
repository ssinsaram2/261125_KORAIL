"""프롬프트 조립·변수 치환 (GUI와 무관한 순수 함수)."""
from __future__ import annotations

import re

from .model import Template

VAR_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

TAG_HEADING = "heading"
TAG_FILLED = "filled"
TAG_MISSING = "missing"
TAG_INTRO = "intro"

# 템플릿의 intro 가 켜져 있으면 프롬프트 맨 앞에 붙는 첫 문장
INTRO_TEXT = "아래의 지시사항에 따라 결과물을 생성해줘."

Segment = tuple[str, "str | None"]


def is_filled(values: dict, name: str) -> bool:
    v = values.get(name)
    return v is not None and str(v).strip() != ""


def heading(style: str, title: str, n: int) -> str:
    return {"none": "", "bracket": f"[{title}]", "md": f"## {title}", "num": f"{n}. {title}"}.get(style, "")


def substitute(text: str, values: dict) -> str:
    """{{이름}} 을 값으로 바꾼다. 값이 비어 있으면 그대로 둔다."""
    def rep(m: re.Match) -> str:
        k = m.group(1).strip()
        return str(values[k]) if is_filled(values, k) else m.group(0)
    return VAR_RE.sub(rep, text)


def _included(t: Template):
    return [b for b in t.blocks if b.enabled and b.content.strip()]


def build_prompt(t: Template) -> str:
    parts = []
    for n, b in enumerate(_included(t), 1):
        h = heading(t.title_style, b.title, n)
        body = substitute(b.content.rstrip(), t.values)
        parts.append(f"{h}\n{body}" if h else body)
    if parts and t.intro:          # 블록 내용이 하나도 없으면 첫 문장도 붙이지 않는다
        parts.insert(0, INTRO_TEXT)
    return "\n\n".join(parts)


def build_segments(t: Template) -> list[Segment]:
    """미리보기용 (텍스트, 태그) 조각 목록. 이어 붙이면 build_prompt()와 같다."""
    out: list[Segment] = []
    if t.intro and _included(t):
        out.append((INTRO_TEXT, TAG_INTRO))
    for n, b in enumerate(_included(t), 1):
        if out:
            out.append(("\n\n", None))
        h = heading(t.title_style, b.title, n)
        if h:
            out.append((h, TAG_HEADING))
            out.append(("\n", None))
        s, last = b.content.rstrip(), 0
        for m in VAR_RE.finditer(s):
            if m.start() > last:
                out.append((s[last:m.start()], None))
            k = m.group(1).strip()
            if is_filled(t.values, k):
                out.append((str(t.values[k]), TAG_FILLED))
            else:
                out.append((m.group(0), TAG_MISSING))
            last = m.end()
        if last < len(s):
            out.append((s[last:], None))
    return out


def used_vars(t: Template, only_enabled: bool = True) -> list[str]:
    seen: dict[str, None] = {}
    for b in t.blocks:
        if only_enabled and not b.enabled:
            continue
        for m in VAR_RE.finditer(b.content):
            seen.setdefault(m.group(1).strip(), None)
    return list(seen)


def missing_vars(t: Template) -> list[str]:
    return [k for k in used_vars(t) if not is_filled(t.values, k)]


def rename_in_text(text: str, old: str, new: str) -> str:
    return VAR_RE.sub(lambda m: "{{" + new + "}}" if m.group(1).strip() == old else m.group(0), text)


def rename_variable(t: Template, old: str, new: str) -> None:
    """변수 이름을 바꾸고 블록 속 {{old}} 도 모두 바꾼다."""
    v = t.var(old)
    if v is None:
        return
    v.name = new
    t.values[new] = t.values.pop(old, "")
    for b in t.blocks:
        b.content = rename_in_text(b.content, old, new)
