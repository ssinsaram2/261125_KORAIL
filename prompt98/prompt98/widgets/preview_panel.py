"""④ 미리보기 + 복사."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from .. import theme
from ..builder import INTRO_TEXT, TAG_FILLED, TAG_HEADING, TAG_MISSING, VAR_RE, build_segments
from ..model import TITLE_STYLES
from ..theme import Fonts, Metrics
from . import varchips
from .win98 import GroupBox, Tooltip, Win98Button

if TYPE_CHECKING:
    from ..app import App

STYLE_LABELS = list(TITLE_STYLES.values())
LABEL_TO_STYLE = {v: k for k, v in TITLE_STYLES.items()}


def configure_preview_tags(text: tk.Text):
    text.tag_configure(TAG_FILLED, background=theme.FILLED_BG)
    text.tag_configure(TAG_MISSING, background=theme.MISS_BG, foreground=theme.MISS_FG)
    text.tag_configure(TAG_HEADING, foreground=theme.NAVY, font=Fonts.bold)
    text.tag_configure("ghost", foreground=theme.SHADOW)
    varchips.setup_tags(text)


def fill_preview(text: tk.Text, segments, empty_msg="블록에 내용을 쓰면 완성된 프롬프트가 여기에 나타납니다."):
    text.config(state="normal")
    text.delete("1.0", "end")
    if not segments:
        text.insert("1.0", empty_msg, "ghost")
    for s, tag in segments:
        if tag == TAG_MISSING:
            # 빈 변수는 괄호를 숨기고 이름만 빨간 칸으로 (복사하면 {{이름}} 그대로 들어감)
            m = VAR_RE.fullmatch(s)
            if m:
                text.insert("end", s[:m.start(1)], varchips.TAG_PAD_BAD)
                text.insert("end", m.group(1), TAG_MISSING)
                text.insert("end", s[m.end(1):], varchips.TAG_PAD_BAD)
                continue
        text.insert("end", s, tag or ())
    text.config(state="disabled")


class PreviewPanel(GroupBox):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, "④ 미리보기")
        self.app = app
        bar = tk.Frame(self)
        bar.pack(fill="x", pady=(0, Metrics.px(4)))
        tk.Label(bar, text="블록 제목").pack(side="left")
        self.style_box = ttk.Combobox(bar, values=STYLE_LABELS, state="readonly", width=13)
        self.style_box.pack(side="left", padx=Metrics.px(4))
        self.style_box.bind("<<ComboboxSelected>>", self._style_changed)
        self.intro_var = tk.BooleanVar(value=True)
        cb = tk.Checkbutton(bar, text="첫 문장 넣기", variable=self.intro_var, command=self._intro_changed)
        cb.pack(side="left", padx=(Metrics.px(8), 0))
        Tooltip(cb, f"맨 앞에 \"{INTRO_TEXT}\"를 붙입니다")
        Win98Button(bar, "복사", app.copy_flow, icon="copy", default=True).pack(side="right")
        Win98Button(bar, "점검", app.open_check, icon="shield").pack(side="right", padx=Metrics.px(4))
        wrap = tk.Frame(self, bd=2, relief="sunken")
        wrap.pack(fill="both", expand=True)
        self.text = tk.Text(wrap, wrap="word", font=Fonts.mono, bd=0, padx=Metrics.px(10), pady=Metrics.px(8),
                            state="disabled", cursor="arrow", spacing1=1, spacing3=1)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        configure_preview_tags(self.text)
        # 읽기 전용이지만 선택·복사(Ctrl+C)는 되도록
        self.text.bind("<1>", lambda e: self.text.focus_set())

    def refresh(self):
        self.style_box.set(TITLE_STYLES.get(self.app.t.title_style, "[제목]"))
        self.intro_var.set(self.app.t.intro)
        y = self.text.yview()[0]
        fill_preview(self.text, build_segments(self.app.t))
        self.text.yview_moveto(y)

    def _intro_changed(self):
        on = self.intro_var.get()
        if on != self.app.t.intro:
            self.app.snap()
            self.app.t.intro = on
            self.app.changed(now=True)

    def _style_changed(self, _e):
        st = LABEL_TO_STYLE.get(self.style_box.get(), "bracket")
        if st != self.app.t.title_style:
            self.app.snap()
            self.app.t.title_style = st
            self.app.changed(now=True)
