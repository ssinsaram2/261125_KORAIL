"""Windows 98 색상·글꼴 상수와 tk/ttk 스타일 설정."""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

DESKTOP = "#008080"
FACE = "#c0c0c0"
LIGHT = "#dfdfdf"
WHITE = "#ffffff"
SHADOW = "#808080"
DARK = "#0a0a0a"
NAVY = "#000080"
NAVY2 = "#1084d0"
TEAL = "#008080"
INFO_BG = "#ffffe1"
FILLED_BG = "#ffff80"
MISS_BG = "#ffd0d0"
MISS_FG = "#a00000"
HINT_FG = "#404040"
OFF_BG = "#ececec"

# 한국어 Windows 는 둥근모꼴을 이름표의 한국어 이름("둥근모꼴")으로만 목록에 올린다.
# 영문 이름만 찾으면 못 찾고 굴림으로 넘어가므로 두 이름을 모두 확인한다.
DUNGGEUNMO_NAMES = ("둥근모꼴", "DungGeunMo")
PREFERRED_FAMILIES = DUNGGEUNMO_NAMES + ("굴림", "Gulim", "돋움", "Dotum")


class Fonts:
    family = "TkDefaultFont"
    body: tkfont.Font
    small: tkfont.Font
    bold: tkfont.Font
    small_bold: tkfont.Font
    title: tkfont.Font
    mono: tkfont.Font
    big: tkfont.Font
    huge: tkfont.Font


class Metrics:
    scale = 1.0       # 화면 배율 (96dpi = 1.0)
    icon_zoom = 1     # 16px 아이콘 확대 배수
    font_unit = 16    # 글꼴 기본 픽셀 크기 (16의 배수)

    @classmethod
    def px(cls, n: float) -> int:
        return int(round(n * cls.scale))


def pick_family(root: tk.Misc) -> str:
    fams = set(tkfont.families(root))
    for f in PREFERRED_FAMILIES:
        if f in fams:
            return f
    return tkfont.nametofont("TkDefaultFont").actual("family")


def init_scaling(root: tk.Tk) -> None:
    dpi = root.winfo_fpixels("1i")
    root.tk.call("tk", "scaling", dpi / 72.0)
    Metrics.scale = max(1.0, dpi / 96.0)
    Metrics.icon_zoom = max(1, int(Metrics.scale + 0.25))


def init_fonts(root: tk.Tk) -> str:
    fam = pick_family(root)
    Fonts.family = fam
    # 둥근모꼴은 16px 격자 픽셀 글꼴이라 16px의 정수배에서만 획이 고르게 나온다.
    # pt 단위(화면 배율을 따라 20px, 24px…)로 주면 획 굵기가 들쭉날쭉해지므로
    # 음수(=픽셀) 크기로 16·32·48px 에 맞춘다. 대체 글꼴(굴림 등)도 같은 크기를 쓴다.
    Metrics.font_unit = unit = 16 * max(1, int(Metrics.scale + 0.25))  # 100~150% → 16px, 175% 이상 → 32px
    Fonts.body = tkfont.Font(root, family=fam, size=-unit)
    Fonts.small = tkfont.Font(root, family=fam, size=-unit)
    Fonts.bold = tkfont.Font(root, family=fam, size=-unit, weight="bold")
    Fonts.small_bold = tkfont.Font(root, family=fam, size=-unit, weight="bold")
    Fonts.title = tkfont.Font(root, family=fam, size=-unit, weight="bold")
    Fonts.mono = tkfont.Font(root, family=fam, size=-unit)
    Fonts.big = tkfont.Font(root, family=fam, size=-unit * 2)
    Fonts.huge = tkfont.Font(root, family=fam, size=-unit * 3)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkFixedFont"):
        try:
            tkfont.nametofont(name).configure(family=fam, size=-unit)
        except tk.TclError:
            pass
    return fam


def apply_theme(root: tk.Tk) -> None:
    o = root.option_add
    o("*Font", Fonts.body)
    o("*Background", FACE)
    o("*Foreground", "#000000")
    o("*highlightThickness", 0)
    o("*selectBackground", NAVY)
    o("*selectForeground", WHITE)
    o("*inactiveSelectBackground", NAVY)
    o("*activeBackground", FACE)
    o("*disabledForeground", SHADOW)
    o("*Button.relief", "raised")
    o("*Button.borderWidth", 2)
    o("*Button.padX", 8)
    o("*Button.padY", 1)
    o("*Entry.Background", WHITE)
    o("*Entry.relief", "sunken")
    o("*Entry.borderWidth", 2)
    o("*Entry.disabledBackground", FACE)
    o("*Entry.readonlyBackground", FACE)
    o("*Spinbox.Background", WHITE)
    o("*Spinbox.relief", "sunken")
    o("*Spinbox.borderWidth", 2)
    o("*Spinbox.buttonBackground", FACE)
    o("*Text.Background", WHITE)
    o("*Text.relief", "sunken")
    o("*Text.borderWidth", 2)
    o("*Text.Font", Fonts.mono)
    o("*Listbox.Background", WHITE)
    o("*Listbox.relief", "sunken")
    o("*Listbox.borderWidth", 2)
    o("*Checkbutton.selectColor", WHITE)
    o("*Radiobutton.selectColor", WHITE)
    o("*Menu.activeBackground", NAVY)
    o("*Menu.activeForeground", WHITE)
    o("*Menu.relief", "raised")
    o("*TCombobox*Listbox.font", Fonts.body)
    o("*TCombobox*Listbox.background", WHITE)
    o("*TCombobox*Listbox.selectBackground", NAVY)
    o("*TCombobox*Listbox.selectForeground", WHITE)
    root.configure(background=FACE)

    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=FACE, foreground="#000", font=Fonts.body, bordercolor=DARK,
                lightcolor=WHITE, darkcolor=SHADOW, troughcolor=LIGHT, focuscolor=FACE,
                selectbackground=NAVY, selectforeground=WHITE)
    s.configure("TCombobox", fieldbackground=WHITE, background=FACE, arrowcolor="#000",
                padding=(4, 2), arrowsize=Metrics.px(13), bordercolor=SHADOW, lightcolor=LIGHT, darkcolor=SHADOW)
    s.map("TCombobox", fieldbackground=[("readonly", WHITE), ("disabled", FACE)],
          selectbackground=[("readonly focus", NAVY), ("readonly", WHITE)],
          selectforeground=[("readonly focus", WHITE), ("readonly", "#000")],
          background=[("active", FACE), ("pressed", LIGHT)])
    for orient in ("Vertical", "Horizontal"):
        s.configure(f"{orient}.TScrollbar", background=FACE, troughcolor=LIGHT, arrowcolor="#000",
                    bordercolor=DARK, lightcolor=WHITE, darkcolor=SHADOW, gripcount=0,
                    arrowsize=Metrics.px(16))
        s.map(f"{orient}.TScrollbar", background=[("active", FACE), ("pressed", LIGHT)])
    s.configure("Treeview", background=WHITE, fieldbackground=WHITE, rowheight=Metrics.px(22),
                font=Fonts.body, bordercolor=SHADOW)
    s.map("Treeview", background=[("selected", NAVY)], foreground=[("selected", WHITE)])
    s.configure("Treeview.Heading", background=FACE, font=Fonts.body, relief="raised", borderwidth=2)
    s.map("Treeview.Heading", background=[("active", FACE)])
