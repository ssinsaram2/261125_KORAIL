"""Text 위젯 속 {{변수}} 를 괄호 없이 '칸(칩)' 모양으로 보여 준다.

저장되는 글은 그대로 {{이름}} (웹판 호환·복사 결과 동일). 화면에서만
- 괄호와 안쪽 공백은 elide(숨김) 태그로 가리고
- 이름 부분에 색 칸 태그를 입힌다.
편집 중에는 칸 하나를 한 덩어리처럼 다룬다(칸 안에 글자가 끼어들지 않고, 지우면 통째로 지움).
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from .. import theme
from ..builder import VAR_RE

CHIP_BG = "#cfe3ff"      # 변수 칸 (파랑)
CHIP_FG = theme.NAVY

TAG_HIDE = "var_hide"
TAG_OK = "var_ok"
TAG_BAD = "var_bad"

Span = tuple[int, int, int, int, str]  # (전체 시작, 전체 끝, 이름 시작, 이름 끝, 이름) — 문자 오프셋


def spans(content: str) -> list[Span]:
    out = []
    for m in VAR_RE.finditer(content):
        out.append((m.start(), m.end(), m.start(1), m.end(1), m.group(1).strip()))
    return out


TAG_PAD_OK = "var_pad_ok"
TAG_PAD_BAD = "var_pad_bad"


def setup_tags(text: tk.Text, missing_bg: str = theme.MISS_BG, missing_fg: str = theme.MISS_FG) -> None:
    """괄호 자리는 아주 작은 글씨 + 칸과 같은 색 → 글자는 안 보이고 칸 양옆 여백처럼 보인다."""
    pad_font = (theme.Fonts.family, -max(4, theme.Metrics.font_unit // 4))
    text.tag_configure(TAG_HIDE, elide=True)
    text.tag_configure(TAG_PAD_OK, background=CHIP_BG, foreground=CHIP_BG, font=pad_font)
    text.tag_configure(TAG_PAD_BAD, background=missing_bg, foreground=missing_bg, font=pad_font)
    text.tag_configure(TAG_OK, background=CHIP_BG, foreground=CHIP_FG)
    text.tag_configure(TAG_BAD, background=missing_bg, foreground=missing_fg)
    text.tag_raise("sel")


def _ix(n: int) -> str:
    return f"1.0+{n}c"


def decorate(text: tk.Text, known: set[str] | None = None) -> None:
    """known 에 없는 이름은 빨간 칸(등록 안 된 변수)으로 표시."""
    for t in (TAG_HIDE, TAG_OK, TAG_BAD, TAG_PAD_OK, TAG_PAD_BAD):
        text.tag_remove(t, "1.0", "end")
    content = text.get("1.0", "end-1c")
    for s, e, ns, ne, name in spans(content):
        ok = known is None or name in known
        pad = TAG_PAD_OK if ok else TAG_PAD_BAD
        text.tag_add(pad, _ix(s), _ix(ns))
        text.tag_add(pad, _ix(ne), _ix(e))
        text.tag_add(TAG_OK if ok else TAG_BAD, _ix(ns), _ix(ne))


def _offset(text: tk.Text, index: str = "insert") -> int:
    return len(text.get("1.0", index))


def _span_at(text: tk.Text, off: int, inclusive_start=False, inclusive_end=False):
    for sp in spans(text.get("1.0", "end-1c")):
        s, e = sp[0], sp[1]
        if s < off < e or (inclusive_start and off == s) or (inclusive_end and off == e):
            return sp
    return None


def install_atomic(text: tk.Text, enabled: Callable[[], bool] = lambda: True) -> None:
    """칸을 한 덩어리처럼: 칸 안에 입력하면 칸 뒤로, BackSpace/Delete 는 칸 전체를 지운다."""

    def has_sel() -> bool:
        return bool(text.tag_ranges("sel"))

    def on_key(e):
        if not enabled() or has_sel() or (e.state & 0x4):
            return None
        if e.char and (e.char.isprintable() or e.char in "\r\t"):
            sp = _span_at(text, _offset(text))
            if sp:
                text.mark_set("insert", _ix(sp[1]))
        return None

    def on_backspace(_e):
        if not enabled() or has_sel():
            return None
        sp = _span_at(text, _offset(text), inclusive_end=True)
        if sp:
            text.delete(_ix(sp[0]), _ix(sp[1]))
            return "break"
        return None

    def on_delete(_e):
        if not enabled() or has_sel():
            return None
        sp = _span_at(text, _offset(text), inclusive_start=True)
        if sp:
            text.delete(_ix(sp[0]), _ix(sp[1]))
            return "break"
        return None

    def on_click(_e):
        # 칸 한가운데를 누르면 커서를 칸 뒤로 보낸다
        if not enabled() or has_sel():
            return
        sp = _span_at(text, _offset(text))
        if sp:
            text.mark_set("insert", _ix(sp[1]))

    text.bind("<Key>", on_key, add="+")
    text.bind("<BackSpace>", on_backspace, add="+")
    text.bind("<Delete>", on_delete, add="+")
    text.bind("<ButtonRelease-1>", on_click, add="+")
