"""Win98 대화상자 공통: 모달, 확인·취소 버튼, Esc 닫기, 부모 창 가운데 배치."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from .. import theme
from ..theme import Fonts, Metrics
from ..widgets import icons
from ..widgets.win98 import Win98Button

ButtonSpec = tuple  # (글자, 값, 기본버튼 여부)


class Dialog(tk.Toplevel):
    """사용법: d = Dialog(parent, '제목'); d.body 에 위젯 추가; d.add_buttons([...]); d.show() → 결과값."""

    def __init__(self, parent: tk.Misc, title: str, min_width: int = 360, resizable: bool = False):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=theme.FACE)
        top = parent.winfo_toplevel()
        self.transient(top)
        self.resizable(resizable, resizable)
        try:
            self.iconphoto(False, icons.get("app"))
        except tk.TclError:
            pass
        self.result = None
        self._min_width = Metrics.px(min_width)
        # 버튼 줄을 먼저 배치해야 본문이 커져도 버튼이 밀려나지 않는다
        self.buttons = tk.Frame(self, bg=theme.FACE, padx=Metrics.px(12), pady=Metrics.px(8))
        self.buttons.pack(fill="x", side="bottom")
        self.body = tk.Frame(self, bg=theme.FACE, padx=Metrics.px(12), pady=Metrics.px(10))
        self.body.pack(fill="both", expand=True)
        self._default_value = None
        self._has_default = False
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda e: self.cancel())

    def add_buttons(self, specs: list[ButtonSpec], handler: Callable | None = None):
        """specs: [(글자, 값, 기본?)] — 누르면 handler(값)이 False 를 돌려주지 않는 한 그 값으로 닫힌다."""
        for spec in reversed(specs):
            text, value = spec[0], spec[1]
            is_def = len(spec) > 2 and spec[2]
            def cb(v=value):
                if handler is not None and handler(v) is False:
                    return
                self.close(v)
            b = Win98Button(self.buttons, text=text, command=cb, default=is_def, width=max(8, len(text) * 2))
            b.pack(side="right", padx=(Metrics.px(6), 0))
            if is_def:
                self._default_btn = b
                self._has_default = True
                self.bind("<Return>", self._on_return)
        return self

    def _on_return(self, e):
        if isinstance(e.widget, tk.Text):
            return
        self._default_btn.invoke()

    def close(self, value=None):
        self.result = value
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def cancel(self):
        self.close(None)

    def place_center(self):
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        w = max(self.winfo_reqwidth(), self._min_width)
        h = self.winfo_reqheight()
        if parent.winfo_viewable():
            x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
        else:
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 3
        x = max(0, min(x, self.winfo_screenwidth() - w))
        y = max(0, min(y, self.winfo_screenheight() - h - 40))
        self.geometry(f"{w}x{h}+{x}+{y}")

    def show(self, focus: tk.Widget | None = None):
        self.place_center()
        self.deiconify()
        self.lift()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        (focus or getattr(self, "_default_btn", None) or self).focus_set()
        self.wait_window()
        return self.result


def msgbox(parent, text: str, title: str = "알림", icon: str = "info",
           buttons: list[ButtonSpec] | None = None, width: int = 400):
    """Win98 메시지 상자. 누른 버튼의 값을 돌려준다(닫기/Esc → None)."""
    d = Dialog(parent, title, min_width=width)
    row = tk.Frame(d.body, bg=theme.FACE)
    row.pack(fill="both", expand=True)
    tk.Label(row, image=icons.get(icon, 32), bg=theme.FACE).pack(side="left", anchor="n", padx=(0, Metrics.px(14)))
    tk.Label(row, text=text, justify="left", anchor="w", bg=theme.FACE, wraplength=Metrics.px(width - 90)
             ).pack(side="left", fill="both", expand=True)
    d.add_buttons(buttons or [("확인", True, True)])
    return d.show()


def ask_yes_no(parent, text, title="확인", icon="q", yes="예", no="아니요", default_yes=True) -> bool:
    return bool(msgbox(parent, text, title, icon, [(yes, True, default_yes), (no, False, not default_yes)]))


def ask_string(parent, title: str, label: str, initial: str = "", maxlen: int = 60,
               validate: Callable[[str], str | None] | None = None) -> str | None:
    """한 줄 입력 상자. validate 가 오류 문구를 돌려주면 닫지 않고 안내한다."""
    d = Dialog(parent, title, min_width=380)
    tk.Label(d.body, text=label, bg=theme.FACE, anchor="w", justify="left").pack(fill="x")
    var = tk.StringVar(value=initial)
    e = tk.Entry(d.body, textvariable=var)
    e.pack(fill="x", pady=(Metrics.px(4), 0))
    e.select_range(0, "end")

    def limit(*_):
        if len(var.get()) > maxlen:
            var.set(var.get()[:maxlen])
    var.trace_add("write", limit)

    def handler(v):
        if v is None:
            return True
        s = var.get().strip()
        if validate:
            err = validate(s)
            if err:
                msgbox(d, err, "알림", "warn")
                e.focus_set()
                return False
        d.result_text = s
        return True
    d.result_text = None
    d.add_buttons([("확인", True, True), ("취소", None)], handler)
    r = d.show(focus=e)
    return d.result_text if r else None


class ErrorReporter:
    """tkinter 콜백 예외를 로그에 남기고 Win98 오류 상자로 알린다(프로그램은 계속)."""

    def __init__(self, root: tk.Tk, log, log_path):
        self.root, self.log, self.log_path = root, log, log_path
        self._showing = False

    def __call__(self, exc, val, tb):
        self.log.error("처리되지 않은 오류", exc_info=(exc, val, tb))
        if self._showing:
            return
        self._showing = True
        try:
            msgbox(self.root, f"예기치 않은 오류가 생겼어요.\n{exc.__name__}: {val}\n\n"
                              f"작업은 계속할 수 있어요. 자세한 내용은 로그 파일에 남겼습니다.\n{self.log_path}",
                   "오류", "err", width=460)
        finally:
            self._showing = False


def text_label(parent, text, **kw) -> tk.Label:
    kw.setdefault("bg", theme.FACE)
    return tk.Label(parent, text=text, justify="left", anchor="w", **kw)


def bold_label(parent, text, **kw) -> tk.Label:
    return text_label(parent, text, font=Fonts.bold, **kw)
