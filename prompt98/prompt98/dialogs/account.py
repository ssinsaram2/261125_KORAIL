"""[1.2] 회원가입·비밀번호 바꾸기 대화상자."""
from __future__ import annotations

import tkinter as tk

from .. import auth, theme
from ..repository import AuthError, User, UserRepo
from ..theme import Fonts, Metrics
from ..widgets import icons
from .base import Dialog, msgbox, text_label


def _field(parent, label, show="", hint=""):
    text_label(parent, label).pack(fill="x")
    var = tk.StringVar()
    e = tk.Entry(parent, textvariable=var, show=show)
    e.pack(fill="x", pady=(Metrics.px(2), 0))
    if hint:
        text_label(parent, hint, font=Fonts.small, fg=theme.HINT_FG).pack(fill="x")
    tk.Frame(parent, height=Metrics.px(6)).pack()
    return var, e


class SignupDialog(Dialog):
    """새 계정을 만든다. 결과: 만든 User (취소면 None)."""

    def __init__(self, parent, users: UserRepo, username: str = ""):
        super().__init__(parent, "회원가입", min_width=440)
        self.users, self.user = users, None
        top = tk.Frame(self.body)
        top.pack(fill="x", pady=(0, Metrics.px(8)))
        tk.Label(top, image=icons.get("app", 32)).pack(side="left", padx=(0, Metrics.px(10)))
        tk.Label(top, text="이 PC에서 쓸 계정을 만듭니다.\n내 템플릿과 설정은 계정마다 따로 저장돼요.",
                 justify="left", anchor="w").pack(side="left", fill="x")
        self.uid, e1 = _field(self.body, "아이디", hint="영문·숫자·밑줄(_) 4~20자")
        self.uid.set(username)
        self.name, _ = _field(self.body, "이름 (선택)", hint="화면에 보일 이름, 예) 홍길동")
        self.pw, _ = _field(self.body, "비밀번호", show="●", hint="8자 이상, 영문과 숫자를 함께")
        self.pw2, e4 = _field(self.body, "비밀번호 확인", show="●")
        text_label(self.body, "비밀번호는 원래 글자로 저장하지 않고 암호화한 값만 저장합니다. 잊으면 되찾을 수 없으니 "
                              "꼭 기억해 두세요.", font=Fonts.small, fg=theme.HINT_FG,
                   wraplength=Metrics.px(400)).pack(fill="x")
        self.first = e1
        self.add_buttons([("가입하기", True, True), ("취소", None)], self._handle)

    def _handle(self, v):
        if v is None:
            return True
        try:
            self.user = self.users.create(self.uid.get(), self.pw.get(), self.name.get(), confirm=self.pw2.get())
        except AuthError as err:
            msgbox(self, str(err), "회원가입", "warn")
            return False
        return True

    def show(self, focus=None) -> User | None:
        super().show(focus=self.first)
        return self.user


class ChangePasswordDialog(Dialog):
    def __init__(self, parent, users: UserRepo, user: User):
        super().__init__(parent, "비밀번호 바꾸기", min_width=420)
        self.users, self.u, self.done = users, user, False
        text_label(self.body, f"계정: {user.username}", font=Fonts.bold).pack(fill="x", pady=(0, Metrics.px(6)))
        self.old, e1 = _field(self.body, "지금 비밀번호", show="●")
        self.new, _ = _field(self.body, "새 비밀번호", show="●", hint="8자 이상, 영문과 숫자를 함께")
        self.new2, _ = _field(self.body, "새 비밀번호 확인", show="●")
        self.first = e1
        self.add_buttons([("바꾸기", True, True), ("취소", None)], self._handle)

    def _handle(self, v):
        if v is None:
            return True
        try:
            self.users.change_password(self.u.id, self.old.get(), self.new.get(), self.new2.get())
        except AuthError as err:
            msgbox(self, str(err), "비밀번호 바꾸기", "warn")
            return False
        self.done = True
        return True

    def show(self, focus=None) -> bool:
        super().show(focus=self.first)
        return self.done


__all__ = ["SignupDialog", "ChangePasswordDialog", "auth"]
