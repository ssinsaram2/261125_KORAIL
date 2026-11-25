"""자체 제작 리소스 생성기 (표준 라이브러리만 사용).

    python tools/make_assets.py

- resources/sounds/boot_default.wav : 웹판의 오리지널 부팅 화음을 합성한 효과음 (타사 저작물 아님)
- resources/icons/app.ico, app.png : 앱 픽셀 아이콘 (16/32/48px)
"""
from __future__ import annotations

import math
import random
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RES = ROOT / "resources"
RATE = 22050


# ---------------------------------------------------------------- 소리
def midi(n: int) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def make_chime(path: Path, seconds: float = 5.0):
    n = int(RATE * seconds)
    buf = [0.0] * n

    def pad(notes, start, dur, vol=0.05):
        for note in notes:
            for det in (-6, 6):
                f = midi(note) * 2 ** (det / 1200)
                s0, s1 = int(start * RATE), min(n, int((start + dur) * RATE))
                for i in range(s0, s1):
                    t = (i - s0) / RATE
                    env = min(1.0, t / 0.6) * (1.0 if t < dur - 1.2 else max(0.0, (dur - t) / 1.2))
                    # 톱니파 대신 배음 3개로 부드럽게
                    ph = 2 * math.pi * f * t
                    buf[i] += vol * env * (math.sin(ph) + 0.35 * math.sin(2 * ph) + 0.15 * math.sin(3 * ph))

    def bell(note, start, vol=0.12):
        f = midi(note)
        s0 = int(start * RATE)
        for i in range(s0, min(n, s0 + int(2.4 * RATE))):
            t = (i - s0) / RATE
            env = min(1.0, t / 0.015) * math.exp(-t * 2.6)
            buf[i] += vol * env * (math.sin(2 * math.pi * f * t) + 0.4 * math.sin(2 * math.pi * 2 * f * t))

    pad([50, 57, 64, 66], 0.0, 3.2)
    pad([55, 62, 66, 69], 1.6, 3.0)
    pad([52, 59, 64, 68, 71], 3.0, 2.0, 0.045)
    for i, m in enumerate([74, 78, 81, 86]):
        bell(m, 0.35 + i * 0.22)
    for i, m in enumerate([83, 79, 76]):
        bell(m, 2.1 + i * 0.26, 0.09)
    for i, m in enumerate([80, 83, 88]):
        bell(m, 3.3 + i * 0.3, 0.1)

    # 메아리(지연 0.27초, 되먹임 0.38)
    d = int(0.27 * RATE)
    out = buf[:]
    for i in range(d, n):
        out[i] += 0.38 * out[i - d]
    # 마무리 페이드 + 정규화
    fade = int(0.6 * RATE)
    for i in range(fade):
        out[n - fade + i] *= 1 - i / fade
    peak = max(abs(x) for x in out) or 1.0
    rnd = random.Random(98)
    frames = b"".join(struct.pack("<h", int(max(-1, min(1, x / peak * 0.8)) * 32767 + rnd.uniform(-0.5, 0.5)))
                      for x in out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)
    print("wrote", path, path.stat().st_size, "bytes")


# ---------------------------------------------------------------- 아이콘
def render_icon_pixels(size: int) -> list[list[tuple[int, int, int, int]]]:
    import tkinter as tk
    from prompt98 import theme
    from prompt98.widgets import icons
    root = tk.Tk()
    root.withdraw()
    theme.Metrics.icon_zoom = 1
    icons._cache.clear()
    img = icons.get("app", 16)
    z = size // 16
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            sx, sy = x // z, y // z
            if img.transparency_get(sx, sy):
                row.append((0, 0, 0, 0))
            else:
                r, g, b = img.get(sx, sy)
                row.append((r, g, b, 255))
        rows.append(row)
    root.destroy()
    return rows


def bmp_entry(px) -> bytes:
    size = len(px)
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, size * size * 4, 0, 0, 0, 0)
    data = b"".join(struct.pack("<BBBB", b, g, r, a) for row in reversed(px) for (r, g, b, a) in row)
    mask_row = ((size + 31) // 32) * 4
    mask = bytearray()
    for row in reversed(px):
        bits = bytearray(mask_row)
        for x, (_r, _g, _b, a) in enumerate(row):
            if a == 0:
                bits[x // 8] |= 0x80 >> (x % 8)
        mask += bits
    return header + data + bytes(mask)


def png_bytes(px) -> bytes:
    import zlib
    size = len(px)
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in px)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def make_icons():
    sizes = [16, 32, 48]
    entries = [bmp_entry(render_icon_pixels(s)) for s in sizes]
    out = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    for s, e in zip(sizes, entries):
        out += struct.pack("<BBBBHHII", s, s, 0, 0, 1, 32, len(e), offset)
        offset += len(e)
    out += b"".join(entries)
    ico = RES / "icons" / "app.ico"
    ico.parent.mkdir(parents=True, exist_ok=True)
    ico.write_bytes(out)
    (RES / "icons" / "app.png").write_bytes(png_bytes(render_icon_pixels(32)))
    print("wrote", ico, len(out), "bytes")


if __name__ == "__main__":
    make_chime(RES / "sounds" / "boot_default.wav")
    make_icons()
