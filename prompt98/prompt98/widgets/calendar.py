"""[1.3] Win98 모양 달력 팝업 — 날짜 칸 옆 📅 버튼을 누르면 뜨고, 날짜를 누르면 고른 값을 돌려준다."""
from __future__ import annotations

import calendar
import datetime as dt
import tkinter as tk
from typing import Callable

from .. import theme
from ..model import valid_date
from ..theme import Fonts, Metrics
from .win98 import Gradient, Win98Button

WEEK = ["일", "월", "화", "수", "목", "금", "토"]


class CalendarPopup(tk.Toplevel):
    def __init__(self, anchor: tk.Widget, value: str, on_pick: Callable[[str], None], title: str = "날짜 고르기"):
        super().__init__(anchor)
        self.withdraw()
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.on_pick = on_pick
        self.today = dt.date.today()
        self.selected = dt.date.fromisoformat(value) if valid_date(value) else None
        base = self.selected or self.today
        self.year, self.month = base.year, base.month

        outer = tk.Frame(self, relief="raised", bd=2, bg=theme.FACE)
        outer.pack(fill="both", expand=True)
        Gradient(outer, text=title, height=Metrics.px(22)).pack(fill="x", padx=2, pady=2)
        nav = tk.Frame(outer, bg=theme.FACE)
        nav.pack(fill="x", padx=Metrics.px(6), pady=(Metrics.px(4), 0))
        Win98Button(nav, "◀", lambda: self.move(-1), small=True).pack(side="left")
        self.head = tk.Label(nav, font=Fonts.bold, bg=theme.FACE)
        self.head.pack(side="left", expand=True)
        Win98Button(nav, "▶", lambda: self.move(1), small=True).pack(side="right")
        self.grid_frame = tk.Frame(outer, bg=theme.WHITE, relief="sunken", bd=2)
        self.grid_frame.pack(padx=Metrics.px(6), pady=Metrics.px(4))
        foot = tk.Frame(outer, bg=theme.FACE)
        foot.pack(fill="x", padx=Metrics.px(6), pady=(0, Metrics.px(6)))
        Win98Button(foot, "오늘", lambda: self.pick(self.today), small=True).pack(side="left")
        Win98Button(foot, "지우기", lambda: self.pick(None), small=True).pack(side="left", padx=Metrics.px(4))
        Win98Button(foot, "닫기", self.close, small=True).pack(side="right")
        self.draw()

        self.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 2
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        if y + h > sh - Metrics.px(48):
            y = anchor.winfo_rooty() - h - 2
        self.geometry(f"+{max(0, min(x, sw - w))}+{max(0, y)}")
        self.deiconify()
        self.bind("<Escape>", lambda e: self.close())
        self.bind("<FocusOut>", lambda e: self.after(150, self._close_if_unfocused))
        self.focus_force()

    def move(self, d: int):
        m = self.month + d
        self.year += (m - 1) // 12
        self.month = (m - 1) % 12 + 1
        self.draw()

    def draw(self):
        self.head.config(text=f"{self.year}년 {self.month}월")
        for w in self.grid_frame.winfo_children():
            w.destroy()
        for c, name in enumerate(WEEK):
            tk.Label(self.grid_frame, text=name, bg=theme.WHITE, font=Fonts.small,
                     fg="#c00000" if c == 0 else theme.NAVY if c == 6 else "#000").grid(row=0, column=c, padx=1, pady=1)
        cal = calendar.Calendar(firstweekday=6)   # 일요일부터
        for r, week in enumerate(cal.monthdatescalendar(self.year, self.month), 1):
            for c, day in enumerate(week):
                other = day.month != self.month
                sel = day == self.selected
                bg = theme.NAVY if sel else ("#ffffe1" if day == self.today else theme.WHITE)
                fg = "#fff" if sel else (theme.SHADOW if other else "#c00000" if c == 0 else "#000")
                b = tk.Label(self.grid_frame, text=str(day.day), width=3, bg=bg, fg=fg, font=Fonts.small,
                             cursor="hand2", relief="flat", bd=1)
                b.grid(row=r, column=c, padx=1, pady=1)
                b.bind("<Button-1>", lambda e, d=day: self.pick(d))
                b.bind("<Enter>", lambda e, w=b, s=sel: s or w.config(relief="raised"))
                b.bind("<Leave>", lambda e, w=b: w.config(relief="flat"))

    def pick(self, day: dt.date | None):
        self.on_pick(day.isoformat() if day else "")
        self.close()

    def _close_if_unfocused(self):
        if not self.winfo_exists():
            return
        f = self.focus_get()
        if f is None or f.winfo_toplevel() is not self:
            self.close()

    def close(self):
        if self.winfo_exists():
            self.destroy()
