"""시작 화면 = [1.2] 로그인 화면.

진행 막대는 없앴다. 하늘 배경과 로고 아래에 Win98 모양의 로그인 창(아이디·비밀번호, [로그인] [회원가입])을 둔다.
로그인에 성공하면 on_login(user) 를 부르고 스스로 사라진다.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from . import theme
from .auth import LoginThrottle
from .repository import SettingsRepo, User, UserRepo
from .theme import Fonts, Metrics
from .widgets.win98 import Gradient, Win98Button

SKY = [(0.0, "#000000"), (0.35, "#0b2a6b"), (0.7, "#1e5fb3"), (1.0, "#5aa9e6")]


def sky_color(t: float) -> str:
    for (a, ca), (b, cb) in zip(SKY, SKY[1:]):
        if t <= b:
            return Gradient.mix(ca, cb, (t - a) / (b - a))
    return SKY[-1][1]


class LoginScreen(tk.Canvas):
    throttle = LoginThrottle()   # 프로그램이 켜져 있는 동안 공유(로그아웃 후 다시 떠도 유지)

    def __init__(self, root: tk.Tk, users: UserRepo, settings: SettingsRepo, on_login: Callable[[User], None],
                 on_signup: Callable[[str], User | None]):
        super().__init__(root, bg="#000", highlightthickness=0, bd=0)
        self.users, self.settings, self.on_login, self.on_signup = users, settings, on_login, on_signup
        self.done = False
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.tk.call("raise", self._w)  # Canvas.lift 는 항목용이라 위젯 raise 를 직접 호출
        self._build_form()
        self.bind("<Configure>", lambda e: self.redraw())

    # ------------------------------------------------------------------ 로그인 창
    def _build_form(self):
        win = tk.Frame(self, bg=theme.FACE, relief="raised", bd=2)
        bar = Gradient(win, text="로그인", height=Metrics.px(24))
        bar.pack(fill="x", padx=Metrics.px(2), pady=Metrics.px(2))
        body = tk.Frame(win, bg=theme.FACE, padx=Metrics.px(14), pady=Metrics.px(10))
        body.pack(fill="both")
        grid = tk.Frame(body, bg=theme.FACE)
        grid.pack(fill="x")
        tk.Label(grid, text="아이디", bg=theme.FACE, anchor="w").grid(row=0, column=0, sticky="w",
                                                                     pady=Metrics.px(3))
        tk.Label(grid, text="비밀번호", bg=theme.FACE, anchor="w").grid(row=1, column=0, sticky="w",
                                                                      pady=Metrics.px(3))
        self.uid = tk.StringVar(value=self.settings.get("last_username") or "")
        self.pw = tk.StringVar()
        self.e_uid = tk.Entry(grid, textvariable=self.uid, width=22)
        self.e_pw = tk.Entry(grid, textvariable=self.pw, show="●", width=22)
        self.e_uid.grid(row=0, column=1, sticky="ew", padx=(Metrics.px(10), 0))
        self.e_pw.grid(row=1, column=1, sticky="ew", padx=(Metrics.px(10), 0))
        grid.columnconfigure(1, weight=1)
        self.remember = tk.BooleanVar(value=bool(self.uid.get()))
        tk.Checkbutton(body, text="아이디 기억하기", variable=self.remember, bg=theme.FACE,
                       activebackground=theme.FACE).pack(anchor="w", pady=(Metrics.px(4), 0))
        self.err = tk.Label(body, text="", fg="#a00000", bg=theme.FACE, anchor="w", justify="left",
                            font=Fonts.small, wraplength=Metrics.px(300))
        self.err.pack(fill="x", pady=(Metrics.px(2), 0))
        btns = tk.Frame(body, bg=theme.FACE)
        btns.pack(fill="x", pady=(Metrics.px(6), 0))
        self.btn_signup = Win98Button(btns, "회원가입", self.signup, width=8)
        self.btn_signup.pack(side="right")
        self.btn_login = Win98Button(btns, "로그인", self.login, default=True, width=8)
        self.btn_login.pack(side="right", padx=(0, Metrics.px(6)))
        for e in (self.e_uid, self.e_pw):
            e.bind("<Return>", lambda ev: self.login())
        self.form = win
        if self.users.count() == 0:
            self.err.config(text="처음 쓰시나요? [회원가입]으로 계정을 먼저 만들어 주세요.", fg=theme.NAVY)
            self.after(50, self.btn_signup.focus_set)
        else:
            self.after(50, lambda: (self.e_pw if self.uid.get() else self.e_uid).focus_set())

    # ------------------------------------------------------------------ 그리기
    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2:
            return
        band = 4
        for y in range(0, h, band):
            col = sky_color(y / h)
            self.create_rectangle(0, y, w, y + band, fill=col, outline=col)
        cx, cy = w // 2, int(h * 0.30)
        s = Metrics.scale * 1.4
        ox, oy = cx - 165 * s, cy - 60 * s

        def R(x, y, ww, hh, col):
            self.create_rectangle(ox + x * s, oy + y * s, ox + (x + ww) * s, oy + (y + hh) * s, fill=col, outline="")
        R(0, 0, 86, 64, "#c0c0c0"); R(2, 2, 84, 62, "#ffffff"); R(4, 4, 80, 58, "#808080"); R(6, 6, 76, 54, "#000080")
        R(12, 13, 40, 4, "#ffff80"); R(12, 22, 58, 4, "#fff"); R(12, 31, 50, 4, "#fff"); R(12, 40, 30, 4, "#ffff80")
        R(46, 40, 22, 4, "#fff"); R(30, 64, 26, 8, "#808080"); R(16, 72, 54, 8, "#c0c0c0")
        fam, u = Fonts.family, Metrics.font_unit  # 픽셀 글꼴은 16px 배수로
        self.create_text(ox + 104 * s, oy + 26 * s, text="프롬프트", anchor="w", fill="#fff", font=(fam, -u * 2))
        self.create_text(ox + 104 * s, oy + 64 * s, text="98", anchor="w", fill="#ffff80", font=(fam, -u * 3))
        self.create_text(ox + 104 * s + u * 4, oy + 68 * s, text="템플릿 생성기", anchor="w", fill="#99ccff",
                         font=(fam, -u))
        # 예전 진행 막대 자리에 로그인 창
        self.create_window(cx, oy + 100 * s + Metrics.px(20), window=self.form, anchor="n")

    # ------------------------------------------------------------------ 동작
    def _error(self, text: str, focus: tk.Widget | None = None):
        self.err.config(text=text, fg="#a00000")
        self.bell()
        if focus is not None:
            focus.focus_set()
            if isinstance(focus, tk.Entry):
                focus.select_range(0, "end")

    def login(self):
        if self.done:
            return
        uid, pw = self.uid.get().strip(), self.pw.get()
        if not uid:
            return self._error("아이디를 입력해 주세요.", self.e_uid)
        if not pw:
            return self._error("비밀번호를 입력해 주세요.", self.e_pw)
        wait = self.throttle.wait_seconds(uid)
        if wait:
            return self._error(f"비밀번호를 여러 번 틀렸어요. {wait}초 뒤에 다시 시도해 주세요.", self.e_pw)
        self.config(cursor="watch")
        self.update_idletasks()
        user = self.users.authenticate(uid, pw)
        self.config(cursor="")
        if user is None:
            self.throttle.failed(uid)
            self.pw.set("")
            return self._error("아이디 또는 비밀번호가 맞지 않아요.", self.e_pw)
        self.throttle.succeeded(uid)
        self.settings.set("last_username", user.username if self.remember.get() else "")
        self.finish(user)

    def signup(self):
        user = self.on_signup(self.uid.get().strip())
        if user is not None:
            self.settings.set("last_username", user.username if self.remember.get() else "")
            self.finish(user)

    def finish(self, user: User):
        if self.done:
            return
        self.done = True
        self.pw.set("")
        self.destroy()
        self.on_login(user)
