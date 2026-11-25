"""Windows 98 모양의 기본 위젯 모음."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import theme
from ..theme import Fonts, Metrics
from . import icons


class Win98Button(tk.Button):
    def __init__(self, parent, text="", command=None, icon: str | None = None, default=False, small=False, **kw):
        opts = dict(text=text, command=command, relief="raised", bd=2, bg=theme.FACE,
                    activebackground=theme.FACE, font=Fonts.small if small else Fonts.body,
                    padx=Metrics.px(4 if small else 10), pady=0 if small else Metrics.px(1), cursor="arrow")
        if icon:
            opts.update(image=icons.get(icon), compound="left")
        if default:
            opts.update(highlightthickness=1, highlightbackground="#000", highlightcolor="#000")
        opts.update(kw)
        super().__init__(parent, **opts)


class ToolButton(tk.Label):
    """툴바 버튼: 평소엔 평평하고, 마우스를 올리면 살짝 튀어나온다."""

    def __init__(self, parent, text, icon_name, command):
        super().__init__(parent, text=text, image=icons.get(icon_name), compound="top", font=Fonts.small,
                         relief="flat", bd=1, padx=Metrics.px(6), pady=Metrics.px(2), bg=theme.FACE)
        self.command = command
        self._pressed = False
        self.bind("<Enter>", lambda e: self.config(relief="raised"))
        self.bind("<Leave>", lambda e: self.config(relief="flat"))
        self.bind("<ButtonPress-1>", self._down)
        self.bind("<ButtonRelease-1>", self._up)

    def _down(self, _e):
        self._pressed = True
        self.config(relief="sunken")

    def _up(self, e):
        inside = 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()
        self.config(relief="raised" if inside else "flat")
        if self._pressed and inside and self.command:
            self.after_idle(self.command)
        self._pressed = False


def separator(parent, orient="vertical") -> tk.Frame:
    if orient == "vertical":
        f = tk.Frame(parent, width=2, bd=1, relief="sunken")
    else:
        f = tk.Frame(parent, height=2, bd=1, relief="sunken")
    return f


class GroupBox(tk.LabelFrame):
    def __init__(self, parent, text, sub: str = "", **kw):
        lab = tk.Frame(parent, bg=theme.FACE)
        tk.Label(lab, text=text, font=Fonts.bold, bg=theme.FACE).pack(side="left")
        if sub:
            tk.Label(lab, text=" " + sub, font=Fonts.small, fg=theme.HINT_FG, bg=theme.FACE).pack(side="left")
        super().__init__(parent, labelwidget=lab, relief="groove", bd=2, bg=theme.FACE,
                         padx=Metrics.px(6), pady=Metrics.px(4), **kw)


class Hint(tk.Label):
    def __init__(self, parent, text, wrap=0, **kw):
        kw.setdefault("bg", parent.cget("bg") if "bg" in parent.keys() else theme.FACE)
        super().__init__(parent, text=text, font=Fonts.small, fg=theme.HINT_FG, justify="left", anchor="w",
                         wraplength=wrap, **kw)


def bind_wrap(label: tk.Label, pad: int = 8):
    """라벨 너비에 맞춰 줄바꿈 폭을 따라가게 한다."""
    label.bind("<Configure>", lambda e: label.config(wraplength=max(50, e.width - pad)))


class Gradient(tk.Canvas):
    """남색 → 하늘색 그라데이션 띠(제목줄·시작 메뉴 띠에 사용)."""

    def __init__(self, parent, c1=theme.NAVY, c2=theme.NAVY2, vertical=False, text="", **kw):
        super().__init__(parent, highlightthickness=0, bd=0, bg=c1, **kw)
        self.c1, self.c2, self.vertical, self.text = c1, c2, vertical, text
        self.bind("<Configure>", lambda e: self.redraw())

    @staticmethod
    def mix(c1, c2, t):
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        n = h if self.vertical else w
        step = 2
        for i in range(0, max(1, n), step):
            col = self.mix(self.c1, self.c2, i / max(1, n))
            if self.vertical:
                y = h - i  # 아래가 c1
                self.create_rectangle(0, y - step, w, y, fill=col, outline=col)
            else:
                self.create_rectangle(i, 0, i + step, h, fill=col, outline=col)
        if self.text:
            if self.vertical:
                self.create_text(w // 2, h - Metrics.px(8), text=self.text, angle=90, anchor="w",
                                 fill=theme.WHITE, font=Fonts.big)
            else:
                self.create_text(Metrics.px(6), h // 2, text=self.text, anchor="w", fill=theme.WHITE, font=Fonts.bold)


class ProgressBlocks(tk.Canvas):
    """Win98 진행 막대(남색 블록)."""

    def __init__(self, parent, **kw):
        super().__init__(parent, height=Metrics.px(22), bg=theme.WHITE, highlightthickness=0, bd=2,
                         relief="sunken", **kw)
        self.value = 0
        self.bind("<Configure>", lambda e: self.redraw())

    def set(self, v: int):
        self.value = max(0, min(100, v))
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width() - 6, self.winfo_height() - 6
        fill = int(w * self.value / 100)
        bw, gap = Metrics.px(9), Metrics.px(2)
        x = 3
        while x < 3 + fill:
            self.create_rectangle(x, 3, min(x + bw, 3 + fill), 3 + h, fill=theme.NAVY, outline="")
            x += bw + gap


class ScrollFrame(tk.Frame):
    """세로 스크롤이 되는 영역. self.inner 에 자식을 넣는다."""

    registry: list["ScrollFrame"] = []

    def __init__(self, parent, bg=theme.WHITE, sunken=True, **kw):
        super().__init__(parent, bd=2 if sunken else 0, relief="sunken" if sunken else "flat", bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self._vsb_shown = False
        self.inner.bind("<Configure>", self._sync)
        self.canvas.bind("<Configure>", self._sync)
        ScrollFrame.registry.append(self)
        self.bind("<Destroy>", lambda e: e.widget is self and self in ScrollFrame.registry
                  and ScrollFrame.registry.remove(self), add="+")

    def _on_scroll(self, lo, hi):
        self.vsb.set(lo, hi)
        need = not (float(lo) <= 0.0 and float(hi) >= 1.0)
        if need != self._vsb_shown:
            self._vsb_shown = need
            if need:
                self.vsb.pack(side="right", fill="y", before=self.canvas)
            else:
                self.vsb.pack_forget()

    def _sync(self, _e=None):
        self.canvas.itemconfigure(self._win, width=self.canvas.winfo_width())
        self.canvas.configure(scrollregion=(0, 0, self.inner.winfo_reqwidth(), self.inner.winfo_reqheight()))

    def scroll_units(self, n: int):
        lo, hi = self.canvas.yview()
        if lo <= 0 and hi >= 1:
            return
        self.canvas.yview_scroll(n, "units")

    def scroll_to_widget(self, w: tk.Widget):
        self.update_idletasks()
        total = max(1, self.inner.winfo_height())
        y = w.winfo_rooty() - self.inner.winfo_rooty()
        h = w.winfo_height()
        top = self.canvas.canvasy(0)
        view = self.canvas.winfo_height()
        if y < top:
            self.canvas.yview_moveto(y / total)
        elif y + h > top + view:
            self.canvas.yview_moveto(max(0, (y + h - view)) / total)


def install_mousewheel(root: tk.Tk):
    """마우스 휠: 포인터 아래의 스크롤 가능한 위젯(Text 우선, 아니면 ScrollFrame)을 굴린다."""
    def on_wheel(e):
        w = root.winfo_containing(e.x_root, e.y_root)
        n = -1 if e.delta > 0 else 1
        n *= max(1, abs(e.delta) // 120) * 3
        while w is not None:
            if isinstance(w, (tk.Text, tk.Listbox, ttk.Treeview)):
                lo, hi = w.yview()
                if not (lo <= 0 and hi >= 1):
                    return  # 위젯 자체 바인딩이 처리
            if isinstance(w, tk.Canvas):
                for sf in ScrollFrame.registry:
                    if sf.canvas is w:
                        sf.scroll_units(n)
                        return
            w = w.master
    root.bind_all("<MouseWheel>", on_wheel, add="+")


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tip, self._job = widget, text, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _e):
        self._job = self.widget.after(600, self._show)

    def _show(self):
        if self.tip or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg=theme.INFO_BG, relief="solid", bd=1, font=Fonts.small,
                 padx=4, pady=1).pack()

    def _hide(self, _e=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class StatusCell(tk.Label):
    def __init__(self, parent, **kw):
        super().__init__(parent, relief="sunken", bd=1, anchor="w", padx=Metrics.px(6), font=Fonts.small, **kw)


class Placeholder:
    """Text 위젯용 회색 안내 문구(비어 있고 포커스가 없을 때만 보임)."""

    def __init__(self, text: tk.Text, hint: str):
        self.text, self.hint, self.showing = text, hint, False
        text.tag_configure("placeholder", foreground="#909090")
        text.bind("<FocusIn>", self._in, add="+")
        text.bind("<FocusOut>", self._out, add="+")
        self._out()

    def _in(self, _e=None):
        if self.showing:
            self.showing = False
            self.text.delete("1.0", "end")

    def _out(self, _e=None):
        if not self.showing and not self.text.get("1.0", "end-1c"):
            self.showing = True
            self.text.insert("1.0", self.hint, "placeholder")
            self.text.edit_modified(False)

    def value(self) -> str:
        return "" if self.showing else self.text.get("1.0", "end-1c")
