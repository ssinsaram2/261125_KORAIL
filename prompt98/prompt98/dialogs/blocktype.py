"""[1.2] 블록 종류 추가: 이름·색·입력 안내를 정해 새 블록 종류를 만든다."""
from __future__ import annotations

import tkinter as tk

from .. import theme
from ..model import BLOCK_NAME_MAX, BLOCK_TYPES, CUSTOM_COLORS, new_custom_type_key
from ..theme import Fonts, Metrics
from ..widgets import icons
from .base import Dialog, msgbox, text_label


class BlockTypeDialog(Dialog):
    """결과: {key, name, color, hint} (취소면 None)."""

    def __init__(self, parent):
        super().__init__(parent, "블록 종류 추가", min_width=460)
        self.out = None
        text_label(self.body, "새로 만들 블록 종류의 이름").pack(fill="x")
        self.name = tk.StringVar()
        e = tk.Entry(self.body, textvariable=self.name)
        e.pack(fill="x", pady=(Metrics.px(2), 0))
        self.name.trace_add("write", self._name_changed)
        text_label(self.body, f"예) 참고 자료, 금지 사항, 말투, 대상 독자 · {BLOCK_NAME_MAX}자 이내", font=Fonts.small,
                   fg=theme.HINT_FG).pack(fill="x", pady=(0, Metrics.px(8)))
        self.entry = e

        text_label(self.body, "색").pack(fill="x")
        row = tk.Frame(self.body)
        row.pack(fill="x", pady=(Metrics.px(2), Metrics.px(8)))
        used = {v[1].lower() for v in BLOCK_TYPES.values()}
        first_free = next((c for c in CUSTOM_COLORS if c.lower() not in used), CUSTOM_COLORS[0])
        self.color = tk.StringVar(value=first_free)
        for c in CUSTOM_COLORS:
            tk.Radiobutton(row, image=icons.swatch(c, 14), variable=self.color, value=c, indicatoron=False,
                           relief="raised", bd=2, offrelief="flat", selectcolor=theme.LIGHT, padx=2, pady=2,
                           command=self._preview).pack(side="left", padx=(0, Metrics.px(3)))

        text_label(self.body, "입력 안내 (선택) — 빈 블록에 회색으로 보이는 예시 문구").pack(fill="x")
        self.hint = tk.Entry(self.body)
        self.hint.pack(fill="x", pady=(Metrics.px(2), Metrics.px(8)))

        text_label(self.body, "미리 보기", font=Fonts.small, fg=theme.HINT_FG).pack(fill="x")
        self.sample = tk.Label(self.body, anchor="w", fg="#fff", font=Fonts.small_bold, padx=Metrics.px(6),
                               pady=Metrics.px(2))
        self.sample.pack(fill="x")
        self._preview()
        self.add_buttons([("만들기", True, True), ("취소", None)], self._handle)

    def _name_changed(self, *_):
        v = self.name.get()
        if len(v) > BLOCK_NAME_MAX:
            self.name.set(v[:BLOCK_NAME_MAX])
            return
        self._preview()

    def _preview(self):
        name = " ".join(self.name.get().split()) or "새 블록 종류"
        self.sample.config(text=f"  ▒ {name}", bg=self.color.get())

    def _handle(self, v):
        if v is None:
            return True
        name = " ".join(self.name.get().split())
        if not name:
            msgbox(self, "블록 종류 이름을 입력해 주세요.", "알림", "warn")
            return False
        if any(n == name for n, _c, _h in BLOCK_TYPES.values()):
            msgbox(self, f"\"{name}\" 블록 종류는 이미 있어요.", "알림", "warn")
            return False
        self.out = {"key": new_custom_type_key(), "name": name, "color": self.color.get(),
                    "hint": self.hint.get().strip()[:60]}
        return True

    def show(self, focus=None):
        super().show(focus=self.entry)
        return self.out
