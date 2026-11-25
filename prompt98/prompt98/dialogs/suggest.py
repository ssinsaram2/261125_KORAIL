"""[1.5] AI 추천 대화상자 — 블록 하나에 쓸 내용을 gemma4(Ollama)에게 받아 골라 넣는다.

추천은 백그라운드 스레드에서 받고, 화면은 after() 로만 고친다(tkinter 는 스레드에 안전하지 않다).
"""
from __future__ import annotations

import queue
import threading
import time
import tkinter as tk

from .. import ai, theme
from ..model import Block, Template, block_name
from ..theme import Fonts, Metrics
from ..widgets import icons
from ..widgets.win98 import Win98Button
from .base import Dialog


class SuggestDialog(Dialog):
    """결과: None(닫기) 또는 ("replace" | "append", 추천 글)."""

    def __init__(self, parent, cfg: ai.AIConfig, t: Template, block: Block):
        name = block.title or block_name(block.type)
        super().__init__(parent, f"AI 추천 - {name}", min_width=560)
        self.cfg, self.t, self.block = cfg, t, block
        self.has_content = bool(block.content.strip())
        self.items: list[str] = []
        self.pick = tk.IntVar(value=0)
        self._q: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self._chars = 0
        self._t0 = 0.0
        self.loading = False

        head = tk.Frame(self.body, bg=theme.FACE)
        head.pack(fill="x")
        tk.Label(head, image=icons.get("wand", 32), bg=theme.FACE).pack(side="left", anchor="n",
                                                                       padx=(0, Metrics.px(10)))
        what = ("지금 내용 뒤에 이어 붙일 내용" if self.has_content else "이 블록에 넣을 내용")
        tk.Label(head, text=f"「{name}」 블록에 {what}을 {cfg.model} 가 추천합니다.\n"
                            "마음에 드는 것을 고르고 아래 단추를 누르세요. 넣은 뒤에도 고칠 수 있고 Ctrl+Z 로 되돌릴 수 있어요.",
                 justify="left", anchor="w", bg=theme.FACE, wraplength=Metrics.px(470), font=Fonts.small
                 ).pack(side="left", fill="x", expand=True)
        self.status = tk.Label(self.body, anchor="w", justify="left", bg=theme.FACE, font=Fonts.bold,
                               wraplength=Metrics.px(530))
        self.status.pack(fill="x", pady=(Metrics.px(8), Metrics.px(4)))
        self.box = tk.Frame(self.body, bg=theme.WHITE, relief="sunken", bd=2, padx=Metrics.px(6),
                            pady=Metrics.px(6))
        self.box.pack(fill="both", expand=True)

        specs = []
        if self.has_content:
            specs += [("뒤에 붙이기", "append", True), ("바꾸기", "replace")]
        else:
            specs += [("넣기", "replace", True)]
        specs += [("다시 추천", "again"), ("닫기", None)]
        self.add_buttons(specs, self._handle)
        self.btn = {b.cget("text"): b for b in self.buttons.winfo_children() if isinstance(b, Win98Button)}
        self.action_btns = [self.btn[s[0]] for s in specs if s[1] in ("append", "replace")]
        self.again_btn = self.btn["다시 추천"]
        self.after(10, self.start)

    # ------------------------------------------------------------------
    def start(self):
        if self.loading:
            return
        self.loading = True
        self._cancel = threading.Event()
        self._chars = 0
        self._t0 = time.monotonic()
        self._q = queue.Queue()
        self._set_buttons(False)
        self._show_items([])
        self._tick()
        cancel, q = self._cancel, self._q

        def work():
            try:
                q.put(("ok", ai.suggest(self.cfg, self.t, self.block, cancel, self._progress)))
            except ai.AIError as e:
                q.put(("err", str(e)))
            except Exception as e:      # 예상 못 한 오류도 화면에는 한국어로
                q.put(("err", f"추천 중 오류가 생겼어요: {e}"))
        threading.Thread(target=work, daemon=True, name="ai-suggest").start()
        self.after(150, self._poll)

    def _progress(self, n: int):
        self._chars = n

    def _tick(self):
        if not self.loading or not self.winfo_exists():
            return
        secs = int(time.monotonic() - self._t0)
        got = f" · 받은 글자 {self._chars}" if self._chars else " · 모델을 깨우는 중"
        self.status.config(text=f"추천을 만드는 중… {secs}초{got}", fg=theme.NAVY)
        self.after(500, self._tick)

    def _poll(self):
        if not self.winfo_exists():
            return
        try:
            kind, val = self._q.get_nowait()
        except queue.Empty:
            self.after(150, self._poll)
            return
        self.loading = False
        secs = time.monotonic() - self._t0
        self.again_btn.config(state="normal")
        if kind == "ok":
            self._show_items(val)
            self.status.config(text=f"추천 {len(val)}개 ({secs:.0f}초)", fg="#000")
            self._set_buttons(True)
        else:
            self.status.config(text=val, fg="#a00000")

    def _set_buttons(self, on: bool):
        for b in self.action_btns:
            b.config(state="normal" if on else "disabled")
        self.again_btn.config(state="disabled" if self.loading else "normal")

    def _show_items(self, items: list[str]):
        for w in self.box.winfo_children():
            w.destroy()
        self.items = items
        self.pick.set(0)
        if not items:
            tk.Label(self.box, text="…", bg=theme.WHITE, fg=theme.HINT_FG, anchor="w").pack(fill="x")
            return
        for i, s in enumerate(items):
            tk.Radiobutton(self.box, text=s, variable=self.pick, value=i, anchor="nw", justify="left",
                           wraplength=Metrics.px(500), bg=theme.WHITE, activebackground=theme.WHITE,
                           font=Fonts.small, padx=Metrics.px(2), pady=Metrics.px(4)
                           ).pack(fill="x", anchor="w")
            if i < len(items) - 1:
                tk.Frame(self.box, height=1, bg=theme.LIGHT).pack(fill="x", pady=Metrics.px(2))
        self.place_center()

    def _handle(self, v):
        if v is None:
            self._cancel.set()
            return True
        if v == "again":
            self.start()
            return False
        if self.loading or not self.items:
            return False
        self.choice = (v, self.items[self.pick.get()])
        return True

    def cancel(self):
        self._cancel.set()
        super().cancel()

    def show(self, focus=None):
        r = super().show(focus)
        return getattr(self, "choice", None) if r else None


def merge(current: str, suggestion: str, mode: str) -> str:
    """바꾸기면 추천으로, 뒤에 붙이기면 지금 내용 다음 줄에 덧붙인다."""
    if mode == "replace" or not current.strip():
        return suggestion
    return current.rstrip() + "\n" + suggestion
