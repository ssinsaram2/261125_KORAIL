"""② 블록 편집기 — 팔레트, 블록 목록, 드래그 앤 드롭."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Callable

from .. import theme
from ..model import BLOCK_TYPES, Block, block_color, block_name, is_custom_type
from ..theme import Fonts, Metrics
from . import icons, varchips
from .win98 import GroupBox, Hint, Placeholder, ScrollFrame, Tooltip, Win98Button, bind_wrap

if TYPE_CHECKING:
    from ..app import App

DRAG_THRESHOLD = 6
EDGE = 30


class DragController:
    """팔레트 → 블록 삽입, 블록 순서 바꾸기, 변수 칩 → 블록 Text 삽입을 담당한다."""

    def __init__(self, app: "App"):
        self.app = app
        self.d: dict | None = None
        self._scroll_job = None

    def attach(self, widget: tk.Widget, kind: str, payload: Callable[[], object], label: Callable[[], str]):
        widget.bind("<ButtonPress-1>", lambda e: self.press(e, kind, payload(), label()), add="+")
        widget.bind("<B1-Motion>", self.motion, add="+")
        widget.bind("<ButtonRelease-1>", self.release, add="+")

    # ------------------------------------------------------------------
    def press(self, e, kind, payload, label):
        self.d = {"kind": kind, "payload": payload, "label": label, "x0": e.x_root, "y0": e.y_root,
                  "moved": False, "idx": None, "ghost": None, "line": None, "src": e.widget}
        if kind == "pal":
            e.widget.config(relief="sunken")

    def motion(self, e):
        d = self.d
        if not d:
            return
        if not d["moved"]:
            if abs(e.x_root - d["x0"]) + abs(e.y_root - d["y0"]) < DRAG_THRESHOLD:
                return
            d["moved"] = True
            g = tk.Toplevel(self.app.root)
            g.wm_overrideredirect(True)
            try:
                g.attributes("-alpha", 0.85)
                g.attributes("-topmost", True)
            except tk.TclError:
                pass
            tk.Label(g, text=d["label"], font=Fonts.bold, bg=theme.FACE, relief="raised", bd=2,
                     padx=Metrics.px(10), pady=Metrics.px(3)).pack()
            d["ghost"] = g
            if d["kind"] == "block":
                self.app.blocks_panel.set_dragging(d["payload"], True)
            self.app.root.config(cursor="fleur")
        d["ghost"].wm_geometry(f"+{e.x_root + 12}+{e.y_root + 8}")
        d["last"] = (e.x_root, e.y_root)
        if d["kind"] in ("block", "pal"):
            self._update_block_target(e.x_root, e.y_root)
        else:
            self._update_text_target(e.x_root, e.y_root)

    def release(self, e):
        d, self.d = self.d, None
        if not d:
            return
        self.app.root.config(cursor="")
        if self._scroll_job:
            self.app.root.after_cancel(self._scroll_job)
            self._scroll_job = None
        if d["kind"] == "pal":
            try:
                d["src"].config(relief="raised")
            except tk.TclError:
                pass
        if d["ghost"]:
            d["ghost"].destroy()
        bp = self.app.blocks_panel
        bp.hide_line()
        if d["kind"] == "block":
            bp.set_dragging(d["payload"], False)
        if not d["moved"]:
            if d["kind"] == "pal":
                bp.add_block(d["payload"])
            elif d["kind"] == "var":
                self.app.insert_var(d["payload"])
            return
        if d["kind"] == "var":
            w = self.app.root.winfo_containing(e.x_root, e.y_root)
            if isinstance(w, tk.Text) and getattr(w, "block", None) is not None:
                idx = w.index(f"@{e.x_root - w.winfo_rootx()},{e.y_root - w.winfo_rooty()}")
                self.app.insert_var(d["payload"], w, idx)
            return
        if d["idx"] is None:
            return
        if d["kind"] == "pal":
            bp.add_block(d["payload"], d["idx"])
            self.app.flash("블록을 넣었어요")
        else:
            bp.move_block(d["payload"], d["idx"])

    # ------------------------------------------------------------------
    def _update_block_target(self, x, y):
        bp = self.app.blocks_panel
        c = bp.list.canvas
        cx, cy, cw, ch = c.winfo_rootx(), c.winfo_rooty(), c.winfo_width(), c.winfo_height()
        inside = cx - EDGE < x < cx + cw + EDGE and cy - EDGE < y < cy + ch + EDGE
        if not inside and self.d["kind"] == "pal":
            self.d["idx"] = None
            bp.hide_line()
            return
        self._autoscroll(y, cy, ch)
        frames = bp.block_frames()
        idx = len(frames)
        for i, f in enumerate(frames):
            if y < f.winfo_rooty() + f.winfo_height() / 2:
                idx = i
                break
        self.d["idx"] = idx
        bp.show_line(idx)

    def _autoscroll(self, y, cy, ch):
        n = -1 if y < cy + EDGE else 1 if y > cy + ch - EDGE else 0
        if self._scroll_job:
            self.app.root.after_cancel(self._scroll_job)
            self._scroll_job = None
        if n and self.d:
            self.app.blocks_panel.list.scroll_units(n)

            def again():
                self._scroll_job = None
                if self.d and self.d.get("last"):
                    self._update_block_target(*self.d["last"])
            self._scroll_job = self.app.root.after(60, again)

    def _update_text_target(self, x, y):
        w = self.app.root.winfo_containing(x, y)
        if isinstance(w, tk.Text) and getattr(w, "block", None) is not None:
            w.focus_set()
            w.mark_set("insert", f"@{x - w.winfo_rootx()},{y - w.winfo_rooty()}")


class BlockWidget(tk.Frame):
    def __init__(self, parent, editor: "BlockEditor", b: Block, index: int, count: int):
        super().__init__(parent, bg=theme.FACE, relief="raised", bd=2, padx=Metrics.px(2), pady=Metrics.px(2))
        self.editor, self.app, self.b = editor, editor.app, b
        color = block_color(b.type)
        head = tk.Frame(self, bg=color, padx=Metrics.px(2), pady=Metrics.px(2))
        head.pack(fill="x")
        grip = tk.Canvas(head, width=Metrics.px(14), height=Metrics.px(20), bg=color, highlightthickness=0,
                         cursor="fleur")
        for gx in range(2, Metrics.px(14), Metrics.px(4)):
            for gy in range(2, Metrics.px(20), Metrics.px(4)):
                grip.create_rectangle(gx, gy, gx + 1, gy + 1, fill="#fff", outline="")
        grip.pack(side="left", padx=(0, Metrics.px(3)))
        Tooltip(grip, "끌어서 순서 바꾸기")
        # [1.2] 블록 제목 입력칸은 없앴다: 머리줄에는 블록 종류 이름만 보인다(지워진 사용자 종류는 저장된 제목)
        name = block_name(b.type) if b.type in BLOCK_TYPES else (b.title or "블록")
        self.app.drag.attach(grip, "block", lambda: b.key, lambda n=name: n)
        tk.Label(head, text=name, fg="#fff", bg=color, font=Fonts.small_bold, anchor="w").pack(
            side="left", fill="x", expand=True)
        for sym, act, tip, ok in reversed((("▲", "up", "위로", index > 0), ("▼", "down", "아래로", index < count - 1),
                                           ("⧉", "dup", "복제", True), ("×", "del", "블록 삭제", True))):
            btn = Win98Button(head, sym, lambda a=act: editor.block_action(b, a), small=True,
                              state="normal" if ok else "disabled")
            btn.pack(side="right", padx=(Metrics.px(1), 0))
            Tooltip(btn, tip)
            setattr(self, f"btn_{act}", btn)

        self.text = tk.Text(self, height=3, wrap="word", undo=False, font=Fonts.mono,
                            padx=Metrics.px(4), pady=Metrics.px(3))
        self.text.block = b
        self.text.pack(fill="x", pady=(Metrics.px(3), 0))
        self.text.insert("1.0", b.content)
        self.text.edit_modified(False)
        self.placeholder = Placeholder(self.text, BLOCK_TYPES.get(b.type, BLOCK_TYPES["text"])[2])
        self.text.bindtags(("AppKeys",) + self.text.bindtags())
        self.text.bind("<<Modified>>", self._text_changed)
        self.text.bind("<FocusIn>", self._focus_in, add="+")
        self.text.bind("<Configure>", lambda e: self.fit())
        self.text.bind("<Tab>", self._tab)
        varchips.setup_tags(self.text)
        varchips.install_atomic(self.text, enabled=lambda: not self.placeholder.showing)
        self.decorate()

        foot = tk.Frame(self, bg=theme.FACE)
        foot.pack(fill="x", pady=(Metrics.px(3), 0))
        names = [v.name for v in self.app.t.variables]
        self.ins = ttk.Combobox(foot, values=names, state="readonly", width=12, font=Fonts.small)
        self.ins.set("변수 삽입…")
        self.ins.bind("<<ComboboxSelected>>", self._insert_selected)
        self.ins.pack(side="left")
        self.on_var = tk.BooleanVar(value=b.enabled)
        tk.Checkbutton(foot, text="프롬프트에 포함", variable=self.on_var, font=Fonts.small,
                       command=self._toggle).pack(side="left", padx=Metrics.px(6))
        self.count = tk.Label(foot, text=f"{len(b.content)}자", font=Fonts.small, fg=theme.HINT_FG)
        self.count.pack(side="right")
        # [1.5] gemma4(Ollama) 추천 — 설정에서 끄면 단추가 보이지 않는다
        self.ai_btn = None
        if self.app.ai_enabled():
            self.ai_btn = Win98Button(foot, "AI 추천", lambda: self.app.suggest_block(self.b), icon="wand", small=True)
            self.ai_btn.pack(side="right", padx=(0, Metrics.px(6)))
            Tooltip(self.ai_btn, "이 블록에 쓸 내용을 gemma4 가 추천해요 (블록 안에서 Ctrl+Space)")
            self.text.bind("<Control-space>", lambda e: (self.app.suggest_block(self.b), "break")[1])
        self._style_enabled()

    # ------------------------------------------------------------------
    def _tab(self, _e):
        self.text.tk_focusNext().focus_set()
        return "break"

    def _focus_in(self, _e):
        self.app.last_text = self.text
        self.app.last_block_key = self.b.key
        self.app.begin_edit()

    def _text_changed(self, _e=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        val = self.placeholder.value()
        if val == self.b.content:
            return
        self.app.note_typing()
        self.b.content = val
        self.count.config(text=f"{len(val)}자")
        self.decorate()
        self.fit()
        self.app.changed()

    def decorate(self):
        """글 속 {{변수}} 를 괄호 없는 색 칸으로 보이게(등록 안 된 이름은 빨간 칸)."""
        if self.placeholder.showing:
            return
        varchips.decorate(self.text, {v.name for v in self.app.t.variables})

    def set_content(self, s: str):
        """외부(변수 삽입)에서 내용을 바꿀 때."""
        self.placeholder._in()
        self.text.delete("1.0", "end")
        self.text.insert("1.0", s)

    def fit(self):
        try:
            n = self.text.count("1.0", "end", "displaylines")
            n = n[0] if isinstance(n, tuple) else n
        except tk.TclError:
            return
        n = max(3, min(18, int(n or 1)))
        if int(self.text.cget("height")) != n:
            self.text.config(height=n)

    def _toggle(self):
        self.app.snap()
        self.b.enabled = self.on_var.get()
        self._style_enabled()
        self.app.changed()

    def _style_enabled(self):
        if self.b.enabled:
            self.text.config(bg=theme.WHITE, fg="#000")
        else:
            self.text.config(bg=theme.OFF_BG, fg=theme.SHADOW)

    def _insert_selected(self, _e):
        val = self.ins.get()
        self.ins.set("변수 삽입…")
        if self.app.t.var(val):
            self.app.insert_var(val, self.text)


class BlockEditor(GroupBox):
    def __init__(self, parent, app: "App"):
        super().__init__(parent, "② 블록 편집기", "엑셀의 수식 영역")
        self.app = app
        pal = tk.Frame(self, bg=theme.FACE)
        pal.pack(fill="x")
        self._pal_items: list[tk.Label] = []
        self._pal_parent = pal
        pal.bind("<Configure>", lambda e: self._relayout_palette())
        self.render_palette()
        h = Hint(self, "블록 종류를 누르거나 아래로 끌어 넣으세요. 블록 왼쪽 점무늬를 잡고 끌면 순서가 바뀝니다. "
                       "[+ 종류 추가]로 새 블록 종류를 만들고, 직접 만든 종류는 오른쪽 클릭으로 지울 수 있어요.")
        h.pack(fill="x", pady=(Metrics.px(3), 0))
        bind_wrap(h)
        self.list = ScrollFrame(self, bg=theme.SHADOW)
        self.list.pack(fill="both", expand=True, pady=(Metrics.px(4), 0))
        self.widgets: list[BlockWidget] = []
        self.line = tk.Frame(self.list.inner, bg=theme.NAVY, height=Metrics.px(4), bd=0)
        self.list.inner.bind("<Configure>", lambda e: self._relayout_palette(), add="+")

    def render_palette(self):
        """블록 종류 팔레트(기본 7종 + 사용자 종류) 끝에 [+ 종류 추가] 버튼을 둔다."""
        for lab in self._pal_items:
            lab.destroy()
        self._pal_items = []
        parent = self._pal_parent
        for typ, (name, color, _hint) in BLOCK_TYPES.items():
            lab = tk.Label(parent, text=name, image=icons.swatch(color), compound="left", font=Fonts.small,
                           relief="raised", bd=2, padx=Metrics.px(6), pady=Metrics.px(1), bg=theme.FACE,
                           cursor="hand2")
            self.app.drag.attach(lab, "pal", lambda t=typ: t, lambda n=name: "+ " + n)
            if is_custom_type(typ):
                Tooltip(lab, "직접 만든 블록 종류 · 오른쪽 클릭: 지우기")
                lab.bind("<Button-3>", lambda e, t=typ, n=name: self._custom_menu(e, t, n))
            self._pal_items.append(lab)
        add = tk.Label(parent, text="+ 종류 추가", font=Fonts.small, relief="raised", bd=2, padx=Metrics.px(6),
                       pady=Metrics.px(1), bg=theme.FACE, fg=theme.NAVY, cursor="hand2")
        add.bind("<ButtonPress-1>", lambda e: add.config(relief="sunken"))
        add.bind("<ButtonRelease-1>", lambda e: (add.config(relief="raised"), self.app.add_block_type()))
        Tooltip(add, "새 블록 종류 만들기 (이름·색·입력 안내)")
        self.add_type_btn = add
        self._pal_items.append(add)
        self._relayout_palette()

    def _custom_menu(self, e, typ: str, name: str):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label=f"「{name}」 블록 종류 지우기…", command=lambda: self.app.delete_block_type(typ))
        m.tk_popup(e.x_root, e.y_root)

    def _relayout_palette(self):
        """창 폭에 맞춰 팔레트 버튼을 여러 줄로 배치."""
        width = self._pal_parent.winfo_width()
        if width <= 1:
            return
        x = y = 0
        row_h = 0
        gap = Metrics.px(3)
        for lab in self._pal_items:
            w, h = lab.winfo_reqwidth(), lab.winfo_reqheight()
            if x and x + w > width:
                x, y = 0, y + row_h + gap
                row_h = 0
            lab.place(x=x, y=y)
            x += w + gap
            row_h = max(row_h, h)
        total = y + row_h
        if int(self._pal_parent.cget("height")) != total:
            self._pal_parent.config(height=total)

    # ------------------------------------------------------------------ 그리기
    def render(self, focus: tuple[str, str] | None = None):
        y = self.list.canvas.yview()[0]
        for w in self.list.inner.winfo_children():
            if w is not self.line:
                w.destroy()
        self.widgets = []
        t = self.app.t
        if self.app.last_text is not None and not self.app.last_text.winfo_exists():
            self.app.last_text = None
        if not t.blocks:
            tk.Label(self.list.inner, text="블록이 없어요. 위의 블록 종류를 누르거나 이곳으로 끌어 오세요.",
                     fg="#fff", bg=theme.SHADOW, pady=Metrics.px(20)).pack(fill="x")
        for i, b in enumerate(t.blocks):
            w = BlockWidget(self.list.inner, self, b, i, len(t.blocks))
            w.pack(fill="x", padx=Metrics.px(6), pady=(Metrics.px(6), 0))
            self.widgets.append(w)
        tk.Frame(self.list.inner, height=Metrics.px(6), bg=theme.SHADOW).pack(fill="x")
        self.line.lift()
        self.list.update_idletasks()
        self.list.canvas.yview_moveto(y)
        for w in self.widgets:
            w.fit()
        if focus:
            key, what = focus
            w = self.widget_for(key)
            if w:
                target = {"text": w.text, "up": w.btn_up, "down": w.btn_down}.get(what, w.text)
                if str(target.cget("state")) == "disabled":
                    target = w.text
                target.focus_set()
                self.list.scroll_to_widget(w)

    def widget_for(self, key: str) -> BlockWidget | None:
        return next((w for w in self.widgets if w.b.key == key), None)

    def block_frames(self) -> list[BlockWidget]:
        return self.widgets

    def set_dragging(self, key: str, on: bool):
        w = self.widget_for(key)
        if w:
            w.config(relief="sunken" if on else "raised", bg=theme.LIGHT if on else theme.FACE)

    def show_line(self, idx: int):
        if not self.widgets:
            self.line.place(x=0, y=Metrics.px(2), relwidth=1)
        elif idx < len(self.widgets):
            f = self.widgets[idx]
            self.line.place(x=0, y=max(0, f.winfo_y() - Metrics.px(5)), relwidth=1)
        else:
            f = self.widgets[-1]
            self.line.place(x=0, y=f.winfo_y() + f.winfo_height() + Metrics.px(1), relwidth=1)
        self.line.lift()

    def hide_line(self):
        self.line.place_forget()

    # ------------------------------------------------------------------ 동작
    def add_block(self, typ: str, at: int | None = None):
        self.app.snap()
        b = Block(typ)
        if at is None:
            self.app.t.blocks.append(b)
        else:
            self.app.t.blocks.insert(at, b)
        self.app.refresh(blocks=True, focus=(b.key, "text"))

    def move_block(self, key: str, to: int):
        blocks = self.app.t.blocks
        frm = next((i for i, b in enumerate(blocks) if b.key == key), None)
        if frm is None:
            return
        if to > frm:
            to -= 1
        if to == frm:
            return
        self.app.snap()
        b = blocks.pop(frm)
        blocks.insert(to, b)
        self.app.refresh(blocks=True)
        self.app.flash("블록 순서를 바꿨어요")

    def block_action(self, b: Block, act: str):
        blocks = self.app.t.blocks
        i = next((k for k, x in enumerate(blocks) if x is b), None)
        if i is None:
            return
        self.app.snap()
        focus = None
        if act == "up" and i > 0:
            blocks[i - 1], blocks[i] = blocks[i], blocks[i - 1]
            focus = (b.key, "up")
        elif act == "down" and i < len(blocks) - 1:
            blocks[i + 1], blocks[i] = blocks[i], blocks[i + 1]
            focus = (b.key, "down")
        elif act == "dup":
            nb = Block(b.type, b.title, b.content, b.enabled)   # 제목은 블록 종류 이름 그대로
            blocks.insert(i + 1, nb)
            focus = (nb.key, "text")
        elif act == "del":
            blocks.pop(i)
            self.app.flash("블록을 지웠어요 (실행 취소: Ctrl+Z)")
        self.app.refresh(blocks=True, focus=focus)


def add_block_button(parent, text, command):
    return Win98Button(parent, text, command, small=True)
