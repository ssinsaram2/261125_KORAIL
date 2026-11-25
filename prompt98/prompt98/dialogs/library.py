"""업무별 프롬프트 라이브러리."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import theme
from ..builder import build_segments
from ..repository import TemplateRepo
from ..theme import Fonts, Metrics
from ..widgets.preview_panel import configure_preview_tags, fill_preview
from .base import Dialog


class LibraryDialog(Dialog):
    """결과: 고른 라이브러리 템플릿 id."""

    def __init__(self, parent, repo: TemplateRepo):
        super().__init__(parent, "업무별 프롬프트 라이브러리", min_width=920, resizable=True)
        self.repo = repo
        self.all = repo.list(library=True)
        self.cat = "전체"
        self.shown = []
        self.q = tk.StringVar()
        qe = tk.Entry(self.body, textvariable=self.q)
        qe.pack(fill="x")
        qe.insert(0, "")
        tk.Label(self.body, text="검색 (예: 보고서, 민원, 번역)", font=Fonts.small, fg=theme.HINT_FG,
                 anchor="w").pack(fill="x")
        self.q.trace_add("write", lambda *_: self.draw_templates())
        self.qe = qe

        grid = tk.Frame(self.body)
        grid.pack(fill="both", expand=True, pady=(Metrics.px(6), 0))
        grid.columnconfigure(1, weight=2)
        grid.columnconfigure(2, weight=3)
        grid.rowconfigure(0, weight=1)
        self.cats = tk.Listbox(grid, exportselection=False, width=16, activestyle="none")
        self.cats.grid(row=0, column=0, sticky="nsew")
        self.temps = tk.Listbox(grid, exportselection=False, activestyle="none", width=28)
        self.temps.grid(row=0, column=1, sticky="nsew", padx=Metrics.px(8))
        right = tk.Frame(grid)
        right.grid(row=0, column=2, sticky="nsew")
        self.name = tk.Label(right, font=Fonts.bold, anchor="w")
        self.name.pack(fill="x")
        self.desc = tk.Label(right, font=Fonts.small, fg=theme.HINT_FG, anchor="w", justify="left")
        self.desc.pack(fill="x")
        self.desc.bind("<Configure>", lambda e: self.desc.config(wraplength=max(100, e.width - 4)))
        self.pv = tk.Text(right, wrap="word", height=18, width=46, font=Fonts.small, state="disabled",
                          padx=Metrics.px(8), pady=Metrics.px(6))
        self.pv.pack(fill="both", expand=True, pady=(Metrics.px(4), 0))
        configure_preview_tags(self.pv)
        self.pv.tag_configure("heading", font=Fonts.small_bold)

        names = ["전체"] + [c for c in repo.categories() if any(s.category == c for s in self.all)]
        self.cat_names = names
        for c in names:
            n = len(self.all) if c == "전체" else sum(1 for s in self.all if s.category == c)
            self.cats.insert("end", f"{c} ({n})")
        self.cats.selection_set(0)
        self.cats.bind("<<ListboxSelect>>", self._cat_selected)
        self.temps.bind("<<ListboxSelect>>", lambda e: self.draw_preview())
        self.temps.bind("<Double-1>", lambda e: self._default_btn.invoke())
        self.add_buttons([("이 템플릿 불러오기", "load", True), ("닫기", None)], self._handle)
        self.draw_templates()

    def _cat_selected(self, _e):
        sel = self.cats.curselection()
        if sel:
            self.cat = self.cat_names[sel[0]]
            self.draw_templates()

    def draw_templates(self):
        q = self.q.get().strip()
        self.shown = [s for s in self.all if (self.cat == "전체" or s.category == self.cat)
                      and (not q or q in (s.name + s.description + s.category))]
        self.temps.delete(0, "end")
        for s in self.shown:
            self.temps.insert("end", f"{s.name}  · 변수 {s.n_vars}개")
        if self.shown:
            self.temps.selection_set(0)
        else:
            self.temps.insert("end", "찾는 템플릿이 없어요.")
            self.temps.itemconfig(0, fg=theme.SHADOW)
        self.draw_preview()

    def _current(self):
        sel = self.temps.curselection()
        if not sel or not self.shown or sel[0] >= len(self.shown):
            return None
        return self.shown[sel[0]]

    def draw_preview(self):
        s = self._current()
        if not s:
            self.name.config(text="")
            self.desc.config(text="")
            fill_preview(self.pv, [], "")
            return
        self.name.config(text=s.name)
        self.desc.config(text=s.description)
        t = self.repo.get(s.id)
        fill_preview(self.pv, build_segments(t))

    def _handle(self, v):
        if v is None:
            return True
        s = self._current()
        if not s:
            return False
        self.close(s.id)
        return False

    def show(self, focus=None):
        return super().show(focus=self.qe)
