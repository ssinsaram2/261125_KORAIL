"""설정: 부팅음·자동 저장·자주 쓰는 기능·데이터 위치 (시작 화면은 [1.2]부터 항상 로그인 화면)."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from .. import ai, theme
from ..paths import res
from ..platform_win import Sound, open_folder
from ..repository import SettingsRepo
from ..theme import Fonts, Metrics
from ..widgets import icons
from ..widgets.win98 import GroupBox, Win98Button
from .base import Dialog, msgbox
from .wizard import QuickListDialog, load_quick_features, save_quick_features

DEFAULT_LABEL = "기본 효과음 (이 프로그램용 자체 제작)"


def boot_sound_file(settings: SettingsRepo) -> Path:
    p = settings.get("boot_sound_path") or ""
    if p and Path(p).exists():
        return Path(p)
    return res("sounds", "boot_default.wav")


class SettingsDialog(Dialog):
    def __init__(self, parent, settings: SettingsRepo, sound: Sound, data_dir: Path):
        super().__init__(parent, "설정", min_width=500)
        self.settings, self.sound, self.data_dir = settings, sound, data_dir
        self.path = settings.get("boot_sound_path") or ""

        g = GroupBox(self.body, "부팅음")
        g.pack(fill="x")
        row = tk.Frame(g)
        row.pack(fill="x")
        tk.Label(row, image=icons.get("spk", 32)).pack(side="left", anchor="n", padx=(0, Metrics.px(10)))
        col = tk.Frame(row)
        col.pack(side="left", fill="x", expand=True)
        tk.Label(col, text="프로그램을 시작할 때 들을 소리를 고르세요. 고른 파일은 복사하지 않고 경로만 기억합니다.",
                 justify="left", anchor="w", wraplength=Metrics.px(380), font=Fonts.small).pack(fill="x")
        self.cur = tk.Label(col, anchor="w", font=Fonts.bold, wraplength=Metrics.px(380), justify="left")
        self.cur.pack(fill="x", pady=Metrics.px(4))
        btns = tk.Frame(col)
        btns.pack(fill="x")
        Win98Button(btns, "파일 고르기…", self.pick, small=True).pack(side="left")
        Win98Button(btns, "기본 효과음으로", self.reset, small=True).pack(side="left", padx=Metrics.px(4))
        Win98Button(btns, "미리 듣기", self.preview, small=True).pack(side="left")
        self.enabled = tk.BooleanVar(value=settings.get_bool("boot_sound_enabled", True))
        tk.Checkbutton(col, text="시작할 때 소리 내기", variable=self.enabled).pack(anchor="w", pady=(Metrics.px(4), 0))

        g2 = GroupBox(self.body, "자동 저장")
        g2.pack(fill="x", pady=(Metrics.px(10), 0))
        r2 = tk.Frame(g2)
        r2.pack(fill="x")
        tk.Label(r2, text="자동 저장 대기 시간").pack(side="left")
        self.secs = tk.Spinbox(r2, from_=1, to=60, width=4)
        self.secs.delete(0, "end")
        self.secs.insert(0, str(settings.get_int("autosave_seconds", 2)))
        self.secs.pack(side="left", padx=Metrics.px(4))
        tk.Label(r2, text="초 (입력이 멈춘 뒤 현재 작업을 보관)").pack(side="left")

        gw = GroupBox(self.body, "아티팩트 마법사")
        gw.pack(fill="x", pady=(Metrics.px(10), 0))
        self.quick_label = tk.Label(gw, anchor="w", font=Fonts.small, justify="left", wraplength=Metrics.px(440))
        self.quick_label.pack(fill="x")
        Win98Button(gw, "자주 쓰는 기능 편집…", self.edit_quick, small=True).pack(anchor="w", pady=(Metrics.px(4), 0))
        self._paint_quick()

        ga = GroupBox(self.body, "AI 추천 (Ollama)")
        ga.pack(fill="x", pady=(Metrics.px(10), 0))
        self.ai_on = tk.BooleanVar(value=settings.get_bool("ai_enabled", True))
        tk.Checkbutton(ga, text="블록 편집기에 [AI 추천] 단추 보이기", variable=self.ai_on).pack(anchor="w")
        ra = tk.Frame(ga)
        ra.pack(fill="x", pady=(Metrics.px(4), 0))
        tk.Label(ra, text="주소").grid(row=0, column=0, sticky="w")
        self.ai_url = tk.Entry(ra, width=28)
        self.ai_url.insert(0, settings.get("ai_url") or ai.DEFAULT_URL)
        self.ai_url.grid(row=0, column=1, sticky="we", padx=Metrics.px(4))
        tk.Label(ra, text="모델").grid(row=0, column=2, sticky="w", padx=(Metrics.px(6), 0))
        self.ai_model = tk.Entry(ra, width=12)
        self.ai_model.insert(0, settings.get("ai_model") or ai.DEFAULT_MODEL)
        self.ai_model.grid(row=0, column=3, sticky="we", padx=Metrics.px(4))
        ra.columnconfigure(1, weight=1)
        rb = tk.Frame(ga)
        rb.pack(fill="x", pady=(Metrics.px(4), 0))
        Win98Button(rb, "연결 확인", self.check_ai, small=True).pack(side="left")
        tk.Label(rb, text="이 PC 안에서만 동작하며, 쓰는 내용은 인터넷으로 보내지 않아요.", font=Fonts.small,
                 fg=theme.HINT_FG).pack(side="left", padx=Metrics.px(6))

        g3 = GroupBox(self.body, "데이터 위치")
        g3.pack(fill="x", pady=(Metrics.px(10), 0))
        tk.Label(g3, text=str(data_dir), anchor="w", font=Fonts.small, wraplength=Metrics.px(440),
                 justify="left").pack(fill="x")
        Win98Button(g3, "폴더 열기", lambda: open_folder(data_dir), small=True).pack(anchor="w", pady=(Metrics.px(4), 0))
        self._paint()
        self.add_buttons([("확인", True, True), ("취소", None)], self._handle)

    def _paint(self):
        self.cur.config(text="현재: " + (Path(self.path).name if self.path else DEFAULT_LABEL))

    def _paint_quick(self):
        n = len(load_quick_features(self.settings))
        self.quick_label.config(text=f"기능 입력 단계에서 눌러 넣는 \"자주 쓰는 기능\" {n}개")

    def edit_quick(self):
        # 이 목록은 [확인]/[취소]와 상관없이 편집 창에서 확인을 누르는 즉시 저장된다
        items = QuickListDialog(self, load_quick_features(self.settings)).show()
        if items is not None:
            save_quick_features(self.settings, items)
            self._paint_quick()

    def pick(self):
        p = filedialog.askopenfilename(parent=self, title="부팅음 파일 고르기",
                                       filetypes=[("소리 파일", "*.mp3 *.wav"), ("모든 파일", "*.*")])
        if not p:
            return
        if Path(p).suffix.lower() not in (".mp3", ".wav"):
            msgbox(self, "mp3 또는 wav 파일만 고를 수 있어요.", "알림", "warn")
            return
        self.path = p
        self._paint()
        self.preview()

    def reset(self):
        self.path = ""
        self._paint()

    def preview(self):
        target = Path(self.path) if self.path else res("sounds", "boot_default.wav")
        if not self.sound.play(target):
            msgbox(self, "이 파일을 재생하지 못했어요.\n" + str(target), "부팅음", "warn")

    def _handle(self, v):
        if v is None:
            self.sound.stop()
            return True
        try:
            secs = max(1, min(60, int(self.secs.get())))
        except ValueError:
            secs = 2
        s = self.settings
        s.set("boot_sound_path", self.path)
        s.set("boot_sound_enabled", self.enabled.get())
        s.set("autosave_seconds", secs)
        cfg = self._ai_cfg()
        s.set("ai_enabled", self.ai_on.get())
        s.set("ai_url", cfg.url)
        s.set("ai_model", cfg.model)
        return True

    def _ai_cfg(self) -> ai.AIConfig:
        url = self.ai_url.get().strip().rstrip("/") or ai.DEFAULT_URL
        if "://" not in url:
            url = "http://" + url
        return ai.AIConfig(url=url, model=self.ai_model.get().strip() or ai.DEFAULT_MODEL)

    def check_ai(self):
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            msgbox(self, ai.check(self._ai_cfg()), "AI 추천", "ok")
        except ai.AIError as e:
            msgbox(self, str(e), "AI 추천", "warn", width=460)
        finally:
            self.config(cursor="")
