"""③ 입력 양식 — 변수 목록에서 자동 생성."""
from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from .. import theme
from ..model import Variable, join_period, period_days, split_period, valid_date
from ..theme import Fonts, Metrics
from . import icons
from .calendar import CalendarPopup
from .win98 import GroupBox, ScrollFrame, Tooltip

if TYPE_CHECKING:
    from ..app import App

NO_CHOICE = "(선택하세요)"


class FormPanel(GroupBox):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, "③ 입력 양식", "변수에서 자동 생성")
        self.app = app
        self.list = ScrollFrame(self, bg=theme.FACE, sunken=False)
        self.list.pack(fill="both", expand=True)
        self.inputs: dict[str, tk.Widget] = {}

    def render(self):
        y = self.list.canvas.yview()[0]
        for w in self.list.inner.winfo_children():
            w.destroy()
        self.inputs = {}
        t = self.app.t
        if not t.variables:
            tk.Label(self.list.inner, text="변수를 만들면 여기에 입력 칸이 자동으로 생겨요.", fg=theme.SHADOW,
                     pady=Metrics.px(16)).pack(fill="x")
            return
        for v in t.variables:
            self._field(v)
        self.list.update_idletasks()
        self.list.canvas.yview_moveto(y)

    def _field(self, v: Variable):
        t = self.app.t
        box = tk.Frame(self.list.inner, padx=Metrics.px(2), pady=Metrics.px(3))
        box.pack(fill="x")
        lab = tk.Frame(box)
        lab.pack(fill="x")
        tk.Label(lab, text=v.name, anchor="w").pack(side="left")
        if v.required:
            tk.Label(lab, text="*", fg="#cc0000").pack(side="left")
        val = t.value(v.name)

        def on_focus(_e=None):
            self.app.begin_edit()

        if v.type == "area":
            w = tk.Text(box, height=3, wrap="word", font=Fonts.mono, padx=Metrics.px(4), pady=Metrics.px(2))
            w.insert("1.0", val)
            w.edit_modified(False)
            w.bindtags(("AppKeys",) + w.bindtags())

            def mod(_e, name=v.name, widget=w):
                if not widget.edit_modified():
                    return
                widget.edit_modified(False)
                self._set(name, widget.get("1.0", "end-1c"))
                lines = int(widget.index("end-1c").split(".")[0])
                widget.config(height=max(3, min(10, lines)))
            w.bind("<<Modified>>", mod)
            w.bind("<Tab>", lambda e, widget=w: (widget.tk_focusNext().focus_set(), "break")[1])
            w.config(height=max(3, min(10, val.count("\n") + 1)))
        elif v.type == "select":
            opts = v.options()
            w = ttk.Combobox(box, values=[NO_CHOICE] + opts, state="readonly")
            w.set(val if val in opts else NO_CHOICE)
            w.bind("<<ComboboxSelected>>",
                   lambda e, name=v.name, widget=w: self._set(name, "" if widget.get() == NO_CHOICE else widget.get(),
                                                              snap=True))
        elif v.type == "period":
            w = self._period_field(box, v, val)
        else:
            sv = tk.StringVar(value=val)
            if v.type == "number":
                w = tk.Spinbox(box, from_=-999999999, to=999999999, increment=1, textvariable=sv)
                sv.set(val)
            else:
                w = tk.Entry(box, textvariable=sv)
            err = None
            if v.type == "date":
                row = tk.Frame(box)
                w.destroy()
                w = tk.Entry(row, textvariable=sv, width=12)
                w.pack(side="left")
                self._cal_button(row, sv, w, f"{v.name} — 날짜").pack(side="left", padx=(Metrics.px(2), 0))
                tk.Button(row, text="오늘", font=Fonts.small, padx=Metrics.px(4), pady=0,
                          command=lambda s=sv: self._pick(s, dt.date.today().isoformat())).pack(
                    side="left", padx=(Metrics.px(4), 0))
                err = tk.Label(row, text="YYYY-MM-DD", font=Fonts.small, fg=theme.HINT_FG)
                err.pack(side="left", padx=Metrics.px(6))
                row.pack(fill="x", pady=(Metrics.px(2), 0))

            def changed(*_a, name=v.name, s=sv, widget=w, typ=v.type, e=err):
                text = s.get()
                if typ == "date" and e is not None:
                    bad = bool(text) and not valid_date(text)
                    widget.config(bg=theme.MISS_BG if bad else theme.WHITE)
                    e.config(text="날짜 형식: 2026-12-01" if bad else "YYYY-MM-DD",
                             fg=theme.MISS_FG if bad else theme.HINT_FG)
                if typ == "number" and text and not _is_number(text):
                    widget.config(bg=theme.MISS_BG)
                elif typ == "number":
                    widget.config(bg=theme.WHITE)
                self._set(name, text)
            sv.trace_add("write", changed)
            changed()
            w._sv = sv  # 참조 유지
        if v.type not in ("date", "period"):
            w.pack(fill="x", pady=(Metrics.px(2), 0))
        w.bind("<FocusIn>", on_focus, add="+")
        self.inputs[v.name] = w

    # ------------------------------------------------------------------ [1.3] 날짜 고르기·기간
    def _cal_button(self, parent, sv: tk.StringVar, entry: tk.Widget, title: str) -> tk.Button:
        """달력 버튼: 누르면 달력이 뜨고, 고른 날짜가 칸에 들어간다."""
        b = tk.Button(parent, image=icons.get("cal"), padx=Metrics.px(2), pady=Metrics.px(1))
        b.config(command=lambda: CalendarPopup(b, sv.get(), lambda d: self._pick(sv, d), title))
        Tooltip(b, "달력에서 고르기")
        return b

    def _pick(self, sv: tk.StringVar, value: str):
        if sv.get() != value:
            self.app.snap()          # 달력·[오늘]로 고른 값은 실행 취소 한 단계
            sv.set(value)

    def _period_field(self, box, v: Variable, val: str) -> tk.Widget:
        """시작일 [📅] ~ 종료일 [📅] (N일간). 값은 '시작 ~ 종료' 한 줄로 저장한다."""
        s0, e0 = split_period(val)
        ss, es = tk.StringVar(value=s0), tk.StringVar(value=e0)
        row = tk.Frame(box)
        row.pack(fill="x", pady=(Metrics.px(2), 0))
        e_start = tk.Entry(row, textvariable=ss, width=11)
        e_start.pack(side="left")
        self._cal_button(row, ss, e_start, f"{v.name} — 시작일").pack(side="left", padx=(Metrics.px(2), 0))
        tk.Label(row, text="~").pack(side="left", padx=Metrics.px(5))
        e_end = tk.Entry(row, textvariable=es, width=11)
        e_end.pack(side="left")
        self._cal_button(row, es, e_end, f"{v.name} — 종료일").pack(side="left", padx=(Metrics.px(2), 0))
        row2 = tk.Frame(box)
        row2.pack(fill="x")
        info = tk.Label(row2, font=Fonts.small, fg=theme.HINT_FG, anchor="w")
        info.pack(side="left")
        quick = tk.Frame(row2)
        quick.pack(side="right")

        def span(days: int):
            start = ss.get() if valid_date(ss.get()) else dt.date.today().isoformat()
            end = (dt.date.fromisoformat(start) + dt.timedelta(days=days - 1)).isoformat()
            self.app.snap()
            ss.set(start)
            es.set(end)
        for text, days in (("1일", 1), ("1주", 7), ("2주", 14), ("한 달", 30)):
            b = tk.Button(quick, text=text, font=Fonts.small, padx=Metrics.px(3), pady=0,
                          command=lambda d=days: span(d))
            b.pack(side="left", padx=(Metrics.px(2), 0))
            Tooltip(b, f"시작일부터 {text} 기간으로 (시작일이 없으면 오늘부터)")

        def changed(*_a, name=v.name):
            s, e = ss.get().strip(), es.get().strip()
            bad_s, bad_e = bool(s) and not valid_date(s), bool(e) and not valid_date(e)
            e_start.config(bg=theme.MISS_BG if bad_s else theme.WHITE)
            e_end.config(bg=theme.MISS_BG if bad_e else theme.WHITE)
            days = period_days(s, e)
            if bad_s or bad_e:
                info.config(text="날짜 형식: 2026-12-01", fg=theme.MISS_FG)
            elif s and e and days is None:
                info.config(text="종료일이 시작일보다 빨라요", fg=theme.MISS_FG)
                e_end.config(bg=theme.MISS_BG)
            elif days:
                info.config(text=f"{days}일간", fg=theme.NAVY)
            else:
                info.config(text="시작일 ~ 종료일 (YYYY-MM-DD)", fg=theme.HINT_FG)
            self._set(name, join_period(s, e))
        ss.trace_add("write", changed)
        es.trace_add("write", changed)
        changed()
        e_end.bind("<FocusIn>", lambda e: self.app.begin_edit(), add="+")
        e_start._sv, e_start._ev, e_start._end = ss, es, e_end   # 참조 유지·테스트용
        return e_start

    def _set(self, name: str, value: str, snap: bool = False):
        t = self.app.t
        if t.values.get(name, "") == value:
            return
        if snap:
            self.app.snap()
        else:
            self.app.note_typing()
        t.values[name] = value
        self.app.changed()

    def focus_var(self, name: str):
        w = self.inputs.get(name)
        if w:
            w.focus_set()
            self.list.scroll_to_widget(w)


def _is_number(s: str) -> bool:
    try:
        float(s.replace(",", ""))
        return True
    except ValueError:
        return False
