"""픽셀 아이콘 — 외부 이미지 없이 PhotoImage 에 직접 그린다(16×16, 32×32)."""
from __future__ import annotations

import math
import tkinter as tk

from .. import theme

_cache: dict[tuple, tk.PhotoImage] = {}

# 5×7 글리프
GLYPHS = {
    "?": ["01110", "10001", "00001", "00110", "00100", "00000", "00100"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    "i": ["00100", "00000", "01100", "00100", "00100", "00100", "01110"],
}


class Px:
    def __init__(self, w: int, h: int):
        self.img = tk.PhotoImage(width=w, height=h)
        self.w, self.h = w, h

    def rect(self, x, y, w, h, c):
        x, y, w, h = int(x), int(y), int(w), int(h)
        x2, y2 = min(self.w, x + w), min(self.h, y + h)
        x, y = max(0, x), max(0, y)
        if x2 > x and y2 > y:
            self.img.put(c, to=(x, y, x2, y2))

    def box(self, x, y, w, h, fill, border="#000000"):
        self.rect(x, y, w, h, border)
        self.rect(x + 1, y + 1, w - 2, h - 2, fill)

    def line(self, x0, y0, x1, y1, c, t=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) or 1
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            y = y0 + (y1 - y0) * i / n
            self.rect(round(x - (t - 1) / 2), round(y - (t - 1) / 2), t, t, c)

    def disc(self, cx, cy, r, c):
        for yy in range(int(cy - r), int(cy + r) + 1):
            dy = yy + 0.5 - cy
            if abs(dy) > r:
                continue
            half = math.sqrt(r * r - dy * dy)
            self.rect(round(cx - half), yy, round(2 * half), 1, c)

    def poly(self, pts, c):
        ys = [p[1] for p in pts]
        for yy in range(int(min(ys)), int(math.ceil(max(ys)))):
            sy = yy + 0.5
            xs = []
            for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
                if (y0 <= sy < y1) or (y1 <= sy < y0):
                    xs.append(x0 + (sy - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                self.rect(round(a), yy, round(b) - round(a), 1, c)

    def glyph(self, ch, x, y, scale, c):
        for r, row in enumerate(GLYPHS[ch]):
            for col, bit in enumerate(row):
                if bit == "1":
                    self.rect(x + col * scale, y + r * scale, scale, scale, c)


# ------------------------------------------------------------------ 16px
def _app(p: Px):
    p.box(1, 1, 14, 11, theme.FACE)
    p.rect(3, 3, 10, 7, theme.NAVY)
    p.rect(4, 4, 5, 1, "#ffff88")
    p.rect(4, 6, 7, 1, "#ffffff")
    p.rect(4, 8, 4, 1, "#ffffff")
    p.rect(5, 12, 6, 2, theme.SHADOW)
    p.rect(3, 14, 10, 1, "#000000")


def _new(p: Px):
    p.poly([(3, 1), (11, 1), (14, 4), (14, 15), (3, 15)], "#000000")
    p.poly([(4, 2), (10, 2), (13, 5), (13, 14), (4, 14)], "#ffffff")
    p.rect(10, 2, 1, 3, "#000000")
    p.rect(10, 4, 4, 1, "#000000")
    for y in (7, 9, 11):
        p.rect(5, y, 6 if y < 11 else 4, 1, theme.SHADOW)


def _open(p: Px):
    p.box(1, 3, 13, 11, "#cccc00")
    p.rect(1, 3, 6, 1, "#000000")
    p.poly([(3, 7), (16, 7), (14, 14), (1, 14)], "#000000")
    p.poly([(4, 8), (14.5, 8), (13, 13), (2, 13)], "#ffff88")


def _save(p: Px):
    p.box(1, 1, 14, 14, theme.NAVY)
    p.rect(4, 2, 8, 5, "#ffffff")
    p.rect(9, 3, 2, 3, theme.NAVY)
    p.rect(4, 9, 8, 5, theme.FACE)


def _arrow(p: Px, mirror=False):
    def X(x):
        return 15 - x if mirror else x
    pts = [(5, 4), (1.5, 7.5), (5, 11)]
    for (a, b), (c, d) in zip(pts, pts[1:]):
        p.line(X(a), b, X(c), d, theme.NAVY, 2)
    p.line(X(2), 7.5, X(9), 7.5, theme.NAVY, 2)
    for i in range(0, 7):
        ang = -math.pi / 2 + math.pi * i / 6
        p.rect(round(X(9 + 4 * math.cos(ang))) - (1 if mirror else 0), round(11.5 + 4 * math.sin(ang)) - 1, 2, 2,
               theme.NAVY)
    p.line(X(9), 15, X(7), 15, theme.NAVY, 2)


def _undo(p):
    _arrow(p)


def _redo(p):
    _arrow(p, mirror=True)


def _wand(p: Px):
    p.line(2, 14, 10, 6, "#000000", 2)
    p.line(3, 13, 6, 10, "#ffffff", 1)
    p.rect(11, 3, 2, 2, "#ffff00")
    for x0, y0, x1, y1 in ((12, 0, 12, 1), (12, 7, 12, 8), (8, 4, 9, 4), (14, 4, 15, 4)):
        p.line(x0, y0, x1, y1, "#cc8800")
    p.rect(14, 1, 1, 1, "#cc8800")
    p.rect(10, 1, 1, 1, "#cc8800")


def _lib(p: Px):
    p.box(1, 3, 4, 12, "#800000")
    p.box(4, 1, 4, 14, theme.NAVY)
    p.box(7, 4, 4, 11, "#008000")
    p.poly([(10, 5), (13, 4), (16, 14), (13, 15)], "#000000")
    p.poly([(11, 6), (12.6, 5.3), (15, 13.6), (13.4, 14.2)], "#808000")


def _shield(p: Px):
    pts = [(8, 1), (2, 3), (2, 8), (4, 12), (8, 15), (12, 12), (14, 8), (14, 3)]
    p.poly(pts, "#000000")
    p.poly([(8, 2), (3, 3.8), (3, 8), (5, 11.5), (8, 14), (11, 11.5), (13, 8), (13, 3.8)], theme.TEAL)
    p.poly([(8, 2), (3, 3.8), (3, 8), (5, 11.5), (8, 14)], "#00b0b0")
    p.line(5, 8, 7, 10, "#ffffff", 2)
    p.line(7, 10, 11, 6, "#ffffff", 2)


def _copy(p: Px):
    p.box(1, 1, 9, 11, "#ffffff")
    p.box(6, 4, 9, 11, theme.INFO_BG)
    for y, w in ((7, 5), (9, 5), (11, 3)):
        p.rect(8, y, w, 1, theme.SHADOW)


def _help(p: Px):
    p.disc(8, 8, 7.5, "#000000")
    p.disc(8, 8, 6.5, "#ffff88")
    p.glyph("?", 6, 4, 1, "#000000")


def _start(p: Px):
    p.rect(1, 2, 6, 5, "#dd0000")
    p.rect(8, 2, 6, 5, "#00aa00")
    p.rect(1, 8, 6, 5, "#0000dd")
    p.rect(8, 8, 6, 5, "#eecc00")


def _speaker_body(p: Px):
    p.poly([(1, 5), (5, 5), (9, 2), (9, 14), (5, 11), (1, 11)], "#000000")
    p.poly([(2, 6), (5.3, 6), (8, 4), (8, 12), (5.3, 10), (2, 10)], "#ffff88")


def _spk(p: Px):
    _speaker_body(p)
    p.line(11, 5, 11, 11, "#000000")
    p.line(13, 3, 14, 5, "#000000")
    p.line(14, 6, 14, 10, "#000000")
    p.line(14, 11, 13, 13, "#000000")


def _mute(p: Px):
    _speaker_body(p)
    p.line(10, 5, 15, 11, "#cc0000", 2)
    p.line(15, 5, 10, 11, "#cc0000", 2)


def _gear(p: Px):
    p.disc(8, 8, 7, "#000000")
    p.disc(8, 8, 6, theme.FACE)
    for a in range(0, 360, 45):
        r = math.radians(a)
        p.rect(round(8 + 6 * math.cos(r)) - 1, round(8 + 6 * math.sin(r)) - 1, 3, 3, "#000000")
    p.disc(8, 8, 2.5, "#000000")
    p.disc(8, 8, 1.5, "#ffffff")


def _folder(p: Px):
    _open(p)


def _txt(p: Px):
    _new(p)
    p.rect(5, 5, 4, 1, theme.NAVY)


def _cal(p: Px):
    """[1.3] 달력: 빨간 머리띠 + 날짜 칸."""
    p.box(1, 2, 14, 13, "#ffffff")
    p.rect(2, 3, 12, 3, "#cc0000")
    p.rect(4, 1, 1, 3, "#000000")
    p.rect(11, 1, 1, 3, "#000000")
    for y in (8, 11):
        for x in (3, 6, 9, 12):
            p.rect(x, y, 2, 2, theme.SHADOW)
    p.rect(9, 11, 2, 2, theme.NAVY)


def _user(p: Px):
    """[1.2] 로그인한 사용자: 남색 옷의 사람."""
    p.disc(8, 5, 3.6, "#000000")
    p.disc(8, 5, 2.6, "#ffd8a8")
    p.poly([(2, 15), (3, 10), (6, 9), (10, 9), (13, 10), (14, 15)], "#000000")
    p.poly([(3, 14), (4, 10.8), (6.3, 10), (9.7, 10), (12, 10.8), (13, 14)], theme.NAVY)
    p.rect(7, 10, 2, 2, "#ffffff")


# ------------------------------------------------------------------ 상태 아이콘 (크기 가변)
def _status(kind: str, s: int):
    def draw(p: Px):
        k = s / 32
        if kind == "warn":
            p.poly([(16 * k, 1 * k), (31 * k, 29 * k), (1 * k, 29 * k)], "#000000")
            p.poly([(16 * k, 4 * k), (28.5 * k, 27.5 * k), (3.5 * k, 27.5 * k)], "#ffff00")
            if s >= 32:
                p.rect(14, 10, 4, 11, "#000000")
                p.rect(14, 23, 4, 3, "#000000")
            else:
                p.rect(7, 5, 2, 5, "#000000")
                p.rect(7, 11, 2, 2, "#000000")
            return
        bg, ring, fg = {"info": ("#ffffff", theme.NAVY, theme.NAVY), "q": ("#ffffff", theme.NAVY, theme.NAVY),
                        "err": ("#ee0000", "#660000", "#ffffff"), "ok": ("#00aa00", "#005500", "#ffffff")}[kind]
        p.disc(16 * k, 16 * k, 15 * k, ring)
        p.disc(16 * k, 16 * k, 13 * k, bg)
        t = max(2, round(3.2 * k))
        if kind == "err":
            p.line(10 * k, 10 * k, 22 * k, 22 * k, fg, t)
            p.line(22 * k, 10 * k, 10 * k, 22 * k, fg, t)
        elif kind == "ok":
            p.line(9 * k, 16 * k, 14 * k, 21 * k, fg, t)
            p.line(14 * k, 21 * k, 23 * k, 11 * k, fg, t)
        else:
            g = "i" if kind == "info" else "?"
            sc = max(1, s // 12)
            p.glyph(g, round(16 * k - 2.5 * sc), round(16 * k - 3.5 * sc), sc, fg)
    return draw


DRAW16 = {"app": _app, "new": _new, "open": _open, "save": _save, "undo": _undo, "redo": _redo,
          "wand": _wand, "lib": _lib, "shield": _shield, "copy": _copy, "help": _help, "start": _start,
          "spk": _spk, "mute": _mute, "gear": _gear, "folder": _folder, "txt": _txt, "user": _user, "cal": _cal}


def get(name: str, size: int = 16) -> tk.PhotoImage:
    """아이콘을 돌려준다. size 는 논리 크기(16/32)이며 화면 배율만큼 정수배 확대한다."""
    zoom = theme.Metrics.icon_zoom
    key = (name, size, zoom)
    if key in _cache:
        return _cache[key]
    if name in ("info", "warn", "err", "ok", "q"):
        p = Px(size, size)
        _status(name, size)(p)
    else:
        p = Px(16, 16)
        DRAW16[name](p)
        if size != 16:
            p.img = p.img.zoom(size // 16)
    img = p.img.zoom(zoom) if zoom > 1 else p.img
    _cache[key] = img
    return img


def swatch(color: str, size: int = 10) -> tk.PhotoImage:
    zoom = theme.Metrics.icon_zoom
    key = ("swatch", color, size, zoom)
    if key not in _cache:
        p = Px(size, size)
        p.box(0, 0, size, size, color)
        _cache[key] = p.img.zoom(zoom) if zoom > 1 else p.img
    return _cache[key]
