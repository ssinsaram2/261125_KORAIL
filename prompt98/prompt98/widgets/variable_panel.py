"""① 변수 영역."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from .. import theme
from ..builder import rename_variable, used_vars
from ..dialogs.base import ask_string, ask_yes_no, msgbox
from ..model import VAR_TYPES, Variable, valid_var_name
from ..theme import Fonts, Metrics
from .varchips import CHIP_BG, CHIP_FG
from .win98 import GroupBox, Hint, ScrollFrame, Tooltip, Win98Button, bind_wrap

if TYPE_CHECKING:
    from ..app import App

TYPE_LABELS = list(VAR_TYPES.values())
LABEL_TO_TYPE = {v: k for k, v in VAR_TYPES.items()}
NAME_RULE = "변수 이름은 한글·영문·숫자·밑줄(_)로 20자 이내, 띄어쓰기 없이 지어 주세요.\n예) 부서명, 보고_기간"


class VariablePanel(GroupBox):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, "① 변수 영역", "엑셀의 변수 셀")
        self.app = app
        h = Hint(self, "파란 칸을 누르면 블록의 커서 위치에, 끌어다 놓으면 원하는 곳에 들어갑니다.")
        h.pack(fill="x")
        bind_wrap(h)
        self.list = ScrollFrame(self, bg=theme.WHITE)
        self.list.pack(fill="both", expand=True, pady=Metrics.px(4))

        add = tk.Frame(self, bg=theme.FACE)
        add.pack(fill="x")
        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(add, textvariable=self.name_var, width=10)
        self.name_entry.pack(side="left", fill="x", expand=True)
        self.name_entry.bind("<Return>", lambda e: self.add_from_entry())
        self.type_box = ttk.Combobox(add, values=TYPE_LABELS, state="readonly", width=11, font=Fonts.small)
        self.type_box.set(TYPE_LABELS[0])
        self.type_box.pack(side="left", padx=Metrics.px(3))
        Win98Button(add, "추가", self.add_from_entry).pack(side="left")
        Tooltip(self.name_entry, "새 변수 이름")
        Win98Button(self, "블록에서 변수 찾기", app.scan_vars).pack(fill="x", pady=(Metrics.px(4), 0))

    # ------------------------------------------------------------------ 그리기
    def render(self):
        for w in self.list.inner.winfo_children():
            w.destroy()
        t = self.app.t
        if not t.variables:
            tk.Label(self.list.inner, text="아직 변수가 없어요.\n아래에서 이름을 넣고 추가하세요.", fg=theme.SHADOW,
                     bg=theme.WHITE, pady=Metrics.px(16)).pack(fill="x")
            return
        for v in t.variables:
            self._row(v)

    def _row(self, v: Variable):
        row = tk.Frame(self.list.inner, bg=theme.WHITE, padx=Metrics.px(3), pady=Metrics.px(3))
        row.pack(fill="x")
        top = tk.Frame(row, bg=theme.WHITE)
        top.pack(fill="x")
        chip = tk.Label(top, text=v.name, bg=CHIP_BG, fg=CHIP_FG, relief="raised", bd=2, font=Fonts.small,
                        anchor="w", padx=Metrics.px(6), pady=Metrics.px(1), cursor="hand2")
        chip.pack(side="left", fill="x", expand=True)
        Tooltip(chip, "누르면 블록에 넣기, 끌어서 원하는 위치에 놓기")
        self.app.drag.attach(chip, "var", lambda n=v.name: n, lambda n=v.name: n)
        Win98Button(top, "이름", lambda var=v: self.rename(var), small=True).pack(side="left", padx=(Metrics.px(3), 0))
        Win98Button(top, "×", lambda var=v: self.delete(var), small=True).pack(side="left", padx=(Metrics.px(2), 0))

        bot = tk.Frame(row, bg=theme.WHITE)
        bot.pack(fill="x", pady=(Metrics.px(2), 0))
        tb = ttk.Combobox(bot, values=TYPE_LABELS, state="readonly", width=12, font=Fonts.small)
        tb.set(VAR_TYPES.get(v.type, "한 줄 글"))
        tb.pack(side="left")
        tb.bind("<<ComboboxSelected>>", lambda e, var=v, box=tb: self.set_type(var, LABEL_TO_TYPE[box.get()]))
        req = tk.BooleanVar(value=v.required)
        cb = tk.Checkbutton(bot, text="필수 입력", variable=req, bg=theme.WHITE, activebackground=theme.WHITE,
                            font=Fonts.small, command=lambda var=v, bv=req: self.set_required(var, bv.get()))
        cb.pack(side="left")
        Tooltip(cb, "입력 양식에서 꼭 채워야 하는 값")
        if v.type == "select":
            ov = tk.StringVar(value=v.opts)
            oe = tk.Entry(row, textvariable=ov, font=Fonts.small)
            oe.pack(fill="x", pady=(Metrics.px(2), 0))
            Tooltip(oe, "선택지를 쉼표로 구분 (예: 공식적,친근한)")
            oe.bind("<FocusIn>", lambda e: self.app.begin_edit())
            ov.trace_add("write", lambda *_a, var=v, sv=ov: self.set_opts(var, sv.get()))
        tk.Frame(self.list.inner, height=1, bg=theme.SHADOW).pack(fill="x")

    # ------------------------------------------------------------------ 동작
    def add_from_entry(self):
        name = self.name_var.get().strip()
        if self.app.add_variable(name, LABEL_TO_TYPE.get(self.type_box.get(), "text")):
            self.name_var.set("")
            self.app.flash("변수를 추가했어요")

    def set_type(self, v: Variable, typ: str):
        if v.type == typ:
            return
        self.app.snap()
        v.type = typ
        if typ == "select" and not v.opts:
            v.opts = "예,아니오"
        self.app.refresh(vars=True, form=True)

    def set_required(self, v: Variable, on: bool):
        self.app.snap()
        v.required = on
        self.app.refresh(form=True)

    def set_opts(self, v: Variable, text: str):
        if v.opts == text:
            return
        self.app.note_typing()
        v.opts = text
        self.app.refresh(form=True, delay=400)

    def rename(self, v: Variable):
        t = self.app.t

        def check(n):
            if n == v.name:
                return None
            if not valid_var_name(n):
                return "한글·영문·숫자·밑줄로 20자 이내, 띄어쓰기 없이 지어 주세요."
            if t.var(n):
                return "같은 이름의 변수가 이미 있어요."
            return None
        new = ask_string(self.app.root, "변수 이름 바꾸기", f"새 이름 (블록에 들어간 「{v.name}」 칸도 함께 바뀝니다)",
                         v.name, 20, check)
        if not new or new == v.name:
            return
        self.app.snap()
        rename_variable(t, v.name, new)
        self.app.refresh(vars=True, blocks=True, form=True)
        self.app.flash("이름을 바꿨어요")

    def delete(self, v: Variable):
        t = self.app.t
        if v.name in used_vars(t, only_enabled=False):
            if not ask_yes_no(self.app.root, f"\"{v.name}\" 변수가 블록에서 쓰이고 있어요.\n지워도 블록에 들어간 "
                              f"「{v.name}」 칸은 남고, 빨간 칸으로 표시됩니다. 지울까요?", "변수 삭제"):
                return
        self.app.snap()
        t.variables = [x for x in t.variables if x is not v]
        t.values.pop(v.name, None)
        self.app.refresh(vars=True, blocks=True, form=True)
        self.app.flash(f"\"{v.name}\" 변수를 지웠어요 (실행 취소 가능)")


def warn_name(root, name: str, exists: bool):
    msgbox(root, f"\"{name}\" 변수는 이미 있어요." if exists else NAME_RULE, "알림", "warn")
