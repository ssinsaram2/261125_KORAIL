"""구성 및 보안 점검."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from .. import theme
from ..checks import CheckResult, Finding, run_checks
from ..theme import Fonts, Metrics
from ..widgets import icons
from ..widgets.win98 import ProgressBlocks, ScrollFrame, Win98Button
from .base import Dialog

if TYPE_CHECKING:
    from ..app import App


class CheckDialog(Dialog):
    def __init__(self, app: "App", tab: str = "config"):
        super().__init__(app.root, "구성 및 보안 점검", min_width=640, resizable=True)
        self.app, self.tab = app, tab
        top = tk.Frame(self.body)
        top.pack(fill="x")
        self.score = tk.Label(top, font=Fonts.huge, width=4, anchor="w")
        self.score.pack(side="left")
        right = tk.Frame(top)
        right.pack(side="left", fill="x", expand=True)
        tk.Label(right, text="점검 점수 (100점 만점)", anchor="w").pack(fill="x")
        self.prog = ProgressBlocks(right)
        self.prog.pack(fill="x")

        tabs = tk.Frame(self.body)
        tabs.pack(fill="x", pady=(Metrics.px(10), 0))
        self.tab_btns = {}
        for key in ("config", "security"):
            b = tk.Label(tabs, relief="raised", bd=2, padx=Metrics.px(12), pady=Metrics.px(3), cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self.switch(k))
            self.tab_btns[key] = b
        panel = tk.Frame(self.body, relief="raised", bd=2, padx=Metrics.px(6), pady=Metrics.px(6))
        panel.pack(fill="both", expand=True)
        self.rows = ScrollFrame(panel, bg=theme.FACE, sunken=False, height=Metrics.px(330))
        self.rows.pack(fill="both", expand=True)
        self.mask_all = Win98Button(panel, "민감 정보 모두 마스킹", self._mask_all)
        self.add_buttons([("닫기", None, True)])
        self.bind("<Control-Tab>", lambda e: self.switch("security" if self.tab == "config" else "config"))
        self.result_data: CheckResult | None = None
        self.draw(record=True)

    def switch(self, key):
        self.tab = key
        self.draw()

    def draw(self, record=False):
        r = run_checks(self.app.t)
        self.result_data = r
        if record:
            self.app.record_check(r)
        self.score.config(text=str(r.score), fg="#006000" if r.score >= 80 else "#806000" if r.score >= 50 else "#a00000")
        self.prog.set(r.score)
        for key, label in (("config", "구성 점검"), ("security", "보안 점검")):
            on = key == self.tab
            self.tab_btns[key].config(text=f"{label} ({r.problems(key)})", relief="raised" if on else "groove",
                                      font=Fonts.bold if on else Fonts.body)
        for w in self.rows.inner.winfo_children():
            w.destroy()
        for f in (r.config if self.tab == "config" else r.security):
            self._row(f)
        if self.tab == "security" and r.maskable:
            self.mask_all.pack(side="bottom", anchor="e", pady=(Metrics.px(6), 0), before=self.rows)
        else:
            self.mask_all.pack_forget()
        self.rows.canvas.yview_moveto(0)

    def _row(self, f: Finding):
        row = tk.Frame(self.rows.inner, pady=Metrics.px(5))
        row.pack(fill="x")
        tk.Label(row, image=icons.get(f.level if f.level != "info" else "info", 16)).pack(side="left", anchor="n",
                                                                                         padx=(0, Metrics.px(8)))
        if f.fix:
            Win98Button(row, f.fix_label, lambda fx=f.fix: self._fix(fx), small=True).pack(side="right", anchor="n")
        mid = tk.Frame(row)
        mid.pack(side="left", fill="x", expand=True)
        tk.Label(mid, text=f.title, font=Fonts.bold, anchor="w", justify="left").pack(fill="x")
        if f.detail:
            d = tk.Label(mid, text=f.detail, font=Fonts.small, fg="#333", anchor="w", justify="left",
                         wraplength=Metrics.px(460))
            d.pack(fill="x")
        tk.Frame(self.rows.inner, height=1, bg=theme.SHADOW).pack(fill="x")

    def _fix(self, fix: str):
        self.app.apply_check_fix(fix)
        self.draw()

    def _mask_all(self):
        if self.result_data and self.result_data.maskable:
            self.app.mask_sensitive(self.result_data.maskable)
        self.draw()
