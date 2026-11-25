"""메인 창: 메뉴, 툴바, 3단 화면, 상태 표시줄, 작업 표시줄, 단축키, 자동 저장."""
from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import APP_TITLE, __version__, ai, theme
from .boot import LoginScreen
from .builder import build_prompt, missing_vars, used_vars
from .checks import CheckResult, apply_fix, mask_template, sec_scan
from .dialogs.account import ChangePasswordDialog, SignupDialog
from .dialogs.base import ErrorReporter, ask_yes_no, msgbox
from .dialogs.blocktype import BlockTypeDialog
from .dialogs.check import CheckDialog
from .dialogs.library import LibraryDialog
from .dialogs.open_save import (OpenDialog, export_to_file, import_from_file, save_as_dialog,
                                save_text_file)
from .dialogs.settings import SettingsDialog, boot_sound_file
from .dialogs.suggest import SuggestDialog
from .dialogs.suggest import merge as suggest_merge
from .dialogs.wizard import WizardDialog
from .history import History
from .model import (BLOCK_TYPES, CATEGORIES, Template, Variable, block_name, custom_block_types, new_uuid,
                    set_custom_block_types, valid_var_name)
from .paths import res
from .platform_win import Sound, open_folder, work_area
from .repository import (AutosaveRepo, CheckRunRepo, ReadOnlyError, SettingsRepo, TemplateRepo, User, UserRepo,
                         sample_uuid)
from .theme import Fonts, Metrics
from .widgets import icons
from .widgets.block_editor import BlockEditor, DragController
from .widgets.form_panel import FormPanel
from .widgets.preview_panel import PreviewPanel
from .widgets.variable_panel import NAME_RULE, VariablePanel
from .widgets.win98 import (StatusCell, ToolButton, Tooltip, Win98Button, install_mousewheel, separator)

log = logging.getLogger(__name__)

NARROW_AT = 960
EXAMPLE_NAME = "주간 업무 보고서"     # 예시가 하나도 없을 때 여는 라이브러리 템플릿
START_SAMPLE = "열차 지연 안내문"     # 처음 실행 때 여는 코레일 예시 (resources/samples.json)


def clock_text(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now()
    h = now.hour
    return f"{'오전' if h < 12 else '오후'} {h % 12 or 12}:{now.minute:02d}"


class App:
    def __init__(self, root: tk.Tk, conn: sqlite3.Connection, data_dir: Path, log_path: Path,
                 user: User | None = None, samples: dict | None = None):
        """user 를 주면 로그인 화면 없이 그 사용자로 시작한다(테스트용). 아니면 로그인 화면부터."""
        self.root, self.conn, self.data_dir = root, conn, data_dir
        self.user: User | None = None
        self.users = UserRepo(conn)
        self.repo = TemplateRepo(conn)
        self.settings = SettingsRepo(conn)      # USER_KEYS 는 로그인한 사용자별로 저장된다
        if samples is None:
            try:
                samples = json.loads(res("samples.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                samples = {}
        self.samples = samples
        self.autosave = AutosaveRepo(conn)
        self.check_runs = CheckRunRepo(conn)
        self.sound = Sound()
        self.history = History(100)
        self.t = Template.blank()
        self.saved_json: str | None = None
        self._pending: str | None = None
        self.last_text: tk.Text | None = None
        self.last_block_key: str | None = None
        self._jobs: dict[str, str] = {}
        self.flash_msg = ""
        self.hint_msg = ""
        self.narrow = False
        self.drag = DragController(self)
        root.report_callback_exception = ErrorReporter(root, log, log_path)

        root.title(APP_TITLE)
        try:
            root.iconphoto(True, icons.get("app", 32), icons.get("app"))
        except tk.TclError:
            pass
        self._restore_geometry()
        install_mousewheel(root)
        self._build()
        self._bind_keys()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        if user is not None:
            self.root.after(50, lambda: self.login_as(user, play=False))
        else:
            self.show_login()

    # ================================================================== 화면 구성
    def _build(self):
        r = self.root
        self.menubar = self._build_menu()

        tb = tk.Frame(r)
        tb.pack(fill="x", padx=Metrics.px(2), pady=(Metrics.px(2), 0))
        items = [("새로 만들기", "new", self.new_template), ("열기", "open", self.open_dialog),
                 ("저장", "save", self.save), None, ("실행 취소", "undo", self.undo),
                 ("다시 실행", "redo", self.redo), None, ("아티팩트 마법사", "wand", self.wizard),
                 ("라이브러리", "lib", self.library), ("점검", "shield", self.open_check),
                 ("복사", "copy", self.copy_flow), None, ("사용법", "help", self.help)]
        for it in items:
            if it is None:
                separator(tb).pack(side="left", fill="y", padx=Metrics.px(3), pady=Metrics.px(3))
            else:
                ToolButton(tb, it[0], it[1], it[2]).pack(side="left")
        # [1.2] 툴바 오른쪽 빈 공간: 로그인한 사용자 정보 + [로그아웃]
        ub = tk.Frame(tb, relief="sunken", bd=1, padx=Metrics.px(6), pady=Metrics.px(2))
        ub.pack(side="right", padx=(Metrics.px(4), Metrics.px(2)), pady=Metrics.px(3))
        tk.Label(ub, image=icons.get("user", 32)).pack(side="left", padx=(0, Metrics.px(6)))
        info = tk.Frame(ub)
        info.pack(side="left")
        self.user_name = tk.Label(info, text="", font=Fonts.bold, fg=theme.NAVY, anchor="w")
        self.user_name.pack(fill="x")
        self.user_id = tk.Label(info, text="", font=Fonts.small, fg=theme.HINT_FG, anchor="w")
        self.user_id.pack(fill="x")
        out = Win98Button(ub, "로그아웃", lambda: self.logout(), small=True)
        out.pack(side="left", padx=(Metrics.px(10), 0))
        Tooltip(out, "지금 작업을 보관하고 로그인 화면으로")
        self.user_box = ub
        separator(r, "horizontal").pack(fill="x", pady=(Metrics.px(2), 0))

        nb = tk.Frame(r, padx=Metrics.px(6), pady=Metrics.px(5))
        nb.pack(fill="x")
        tk.Label(nb, text="템플릿 이름").pack(side="left")
        self.name_var = tk.StringVar()
        ne = tk.Entry(nb, textvariable=self.name_var, width=30)
        ne.pack(side="left", padx=Metrics.px(6))
        ne.bind("<FocusIn>", lambda e: self.begin_edit())
        self.name_var.trace_add("write", self._name_changed)
        tk.Label(nb, text="분류").pack(side="left", padx=(Metrics.px(10), 0))
        self.cat_box = ttk.Combobox(nb, values=CATEGORIES, state="readonly", width=16)
        self.cat_box.pack(side="left", padx=Metrics.px(6))
        self.cat_box.bind("<<ComboboxSelected>>", self._cat_changed)
        self.lib_note = tk.Label(nb, text="", font=Fonts.small, fg=theme.HINT_FG)
        self.lib_note.pack(side="left", padx=Metrics.px(6))

        # 작업 표시줄 / 상태 표시줄 (아래부터)
        self._build_taskbar()
        st = tk.Frame(r, padx=Metrics.px(2), pady=Metrics.px(2))
        st.pack(side="bottom", fill="x")
        self.st = [StatusCell(st) for _ in range(4)]
        self.st[0].pack(side="left", fill="x", expand=True)
        for c in self.st[1:]:
            c.pack(side="left", padx=(Metrics.px(2), 0))

        # 3단 화면
        self.center = tk.Frame(r, padx=Metrics.px(4), pady=Metrics.px(2))
        self.center.pack(fill="both", expand=True)
        pw_opts = dict(sashwidth=Metrics.px(6), sashrelief="flat", bd=0, opaqueresize=True, bg=theme.FACE)
        self.hpane = tk.PanedWindow(self.center, orient="horizontal", **pw_opts)
        self.tabbar = tk.Frame(self.center)
        self.vars_panel = VariablePanel(self.center, self)
        self.blocks_panel = BlockEditor(self.center, self)
        self.right = tk.PanedWindow(self.center, orient="vertical", **pw_opts)
        self.form_panel = FormPanel(self.right, self)
        self.preview_panel = PreviewPanel(self.right, self)
        self.right.add(self.form_panel, minsize=Metrics.px(120), height=Metrics.px(300), stretch="always")
        self.right.add(self.preview_panel, minsize=Metrics.px(160), stretch="always")
        self.panes = [self.vars_panel, self.blocks_panel, self.right]
        self.tab_labels = []
        for i, name in enumerate(("① 변수", "② 블록", "③ 양식 · ④ 미리보기")):
            lab = tk.Label(self.tabbar, text=name, relief="raised", bd=2, padx=Metrics.px(12), pady=Metrics.px(3),
                           cursor="hand2")
            lab.pack(side="left")
            lab.bind("<Button-1>", lambda e, k=i: self._show_tab(k))
            self.tab_labels.append(lab)
        self.cur_tab = 1
        self._wide_layout()
        r.bind("<Configure>", self._on_resize, add="+")

    def _build_menu(self) -> tk.Menu:
        m = tk.Menu(self.root, tearoff=0)

        def cascade(label, ul, entries):
            sub = tk.Menu(m, tearoff=0)
            for e in entries:
                if e is None:
                    sub.add_separator()
                else:
                    sub.add_command(label=e[0], command=e[1], accelerator=e[2] if len(e) > 2 else "")
            m.add_cascade(label=label, menu=sub, underline=ul)
            return sub
        cascade("파일(F)", 3, [("새로 만들기", self.new_template, "Ctrl+N"), ("열기…", self.open_dialog, "Ctrl+O"),
                             ("저장", self.save, "Ctrl+S"), ("다른 이름으로 저장…", self.save_as, "Ctrl+Shift+S"), None,
                             ("내보내기(JSON)…", self.export), ("가져오기…", self.import_), None,
                             ("프롬프트를 텍스트로 저장…", self.save_txt), None, ("로그아웃", self.logout),
                             ("끝내기", self.on_close, "Alt+F4")])
        self.edit_menu = cascade("편집(E)", 3, [
            ("실행 취소", self.undo, "Ctrl+Z"), ("다시 실행", self.redo, "Ctrl+Y"), None,
            ("변수 추가", lambda: self.vars_panel.name_entry.focus_set()),
            ("블록에서 변수 찾기", self.scan_vars), ("입력값 모두 지우기", self.clear_values), None,
            ("블록 종류 추가…", lambda: self.add_block_type()), None])
        self._block_menu_start = self.edit_menu.index("end") + 1
        self._rebuild_block_menu()
        cascade("도구(T)", 3, [("아티팩트 마법사…", self.wizard), ("프롬프트 라이브러리…", self.library),
                             ("구성·보안 점검…", self.open_check), None, ("프롬프트 복사", self.copy_flow, "Ctrl+Enter")])
        cascade("도움말(H)", 4, [("사용법", self.help, "F1"), ("설정(부팅음·자동 저장)…", self.settings_dialog),
                              ("비밀번호 바꾸기…", self.change_password),
                              ("데이터 폴더 열기", lambda: open_folder(self.data_dir)), None,
                              ("프로그램 정보", self.about)])
        return m

    def _rebuild_block_menu(self):
        """편집 메뉴 아래쪽의 '○○ 블록 추가' 항목을 지금 블록 종류(사용자 종류 포함)에 맞춰 다시 만든다."""
        menu = getattr(self, "edit_menu", None)
        if menu is None:
            return
        end = menu.index("end")
        if end is not None and end >= self._block_menu_start:
            menu.delete(self._block_menu_start, "end")
        for k, v in BLOCK_TYPES.items():
            menu.add_command(label=f"{v[0]} 블록 추가", command=lambda k=k: self.blocks_panel.add_block(k))

    def _build_taskbar(self):
        bar = tk.Frame(self.root, bd=0)
        bar.pack(side="bottom", fill="x")
        tk.Frame(bar, height=1, bg=theme.LIGHT).pack(fill="x")
        tk.Frame(bar, height=1, bg=theme.WHITE).pack(fill="x")
        inner = tk.Frame(bar, padx=Metrics.px(2), pady=Metrics.px(2))
        inner.pack(fill="x")
        self.start_btn = Win98Button(inner, "시작", self.toggle_start_menu, icon="start", font=Fonts.bold)
        self.start_btn.pack(side="left")
        self.task_lab = tk.Label(inner, image=icons.get("app"), compound="left", relief="sunken", bd=2,
                                 anchor="w", padx=Metrics.px(6), width=Metrics.px(230), bg=theme.LIGHT)
        self.task_lab.pack(side="left", padx=Metrics.px(4))
        tray = tk.Frame(inner, relief="sunken", bd=1, padx=Metrics.px(6))
        tray.pack(side="right", fill="y")
        self.spk = tk.Label(tray, cursor="hand2")
        self.spk.pack(side="left")
        self.spk.bind("<Button-1>", lambda e: self.settings_dialog())
        self.clock = tk.Label(tray, font=Fonts.small)
        self.clock.pack(side="left", padx=(Metrics.px(8), 0))
        self._paint_speaker()
        self._tick_clock()

    def _paint_speaker(self):
        on = self.settings.get_bool("boot_sound_enabled", True)
        self.spk.config(image=icons.get("spk" if on else "mute"))

    def _tick_clock(self):
        self.clock.config(text=clock_text())
        self.root.after(15000, self._tick_clock)

    # ---------------------------------------------------------------- 반응형 배치
    def _wide_layout(self):
        self.tabbar.pack_forget()
        for p in self.panes:
            p.pack_forget()
        self.hpane.pack(fill="both", expand=True)
        self.hpane.add(self.vars_panel, width=Metrics.px(270), minsize=Metrics.px(200), stretch="never")
        self.hpane.add(self.blocks_panel, minsize=Metrics.px(280), stretch="always")
        self.hpane.add(self.right, minsize=Metrics.px(280), stretch="always")
        self.root.after_idle(self._balance_panes)
        self.narrow = False

    def _balance_panes(self):
        w = self.hpane.winfo_width()
        if w > 10:
            left = Metrics.px(270)
            rest = w - left
            try:
                self.hpane.sash_place(0, left, 0)
                self.hpane.sash_place(1, left + int(rest * 0.48), 0)
            except tk.TclError:
                pass

    def _narrow_layout(self):
        for p in self.panes:
            self.hpane.forget(p)
        self.hpane.pack_forget()
        self.tabbar.pack(fill="x")
        self.narrow = True
        self._show_tab(self.cur_tab)

    def _show_tab(self, k: int):
        self.cur_tab = k
        if not self.narrow:
            return
        for i, p in enumerate(self.panes):
            p.pack_forget()
            self.tab_labels[i].config(relief="raised" if i == k else "groove", font=Fonts.bold if i == k else Fonts.body)
        self.panes[k].pack(fill="both", expand=True)
        self.panes[k].lift()

    def _on_resize(self, e):
        if e.widget is not self.root:
            return
        narrow = e.width < Metrics.px(NARROW_AT)
        if narrow != self.narrow:
            self._narrow_layout() if narrow else self._wide_layout()

    # ================================================================== 단축키
    def _bind_keys(self):
        keys = {"<Control-n>": self.new_template, "<Control-o>": self.open_dialog, "<Control-s>": self.save,
                "<Control-S>": self.save_as, "<Control-z>": self.undo, "<Control-y>": self.redo,
                "<Control-Return>": self.copy_flow, "<F1>": self.help}
        for seq, fn in keys.items():
            def h(e, f=fn):
                if self._modal_open() or self.user is None:   # 로그인 화면에서는 단축키를 막는다
                    return None
                f()
                return "break"
            self.root.bind_all(seq, h)
            self.root.bind_class("AppKeys", seq, h)

    def _modal_open(self) -> bool:
        return any(isinstance(w, tk.Toplevel) and w.winfo_viewable() and w.grab_status()
                   for w in self.root.winfo_children())

    # ================================================================== 시작
    def _restore_geometry(self):
        r = self.root
        wa = work_area() or (0, 0, r.winfo_screenwidth(), r.winfo_screenheight() - Metrics.px(48))
        left, top, right, bottom = wa
        aw = right - left
        ah = bottom - top - Metrics.px(40)  # 제목줄·창 테두리 높이를 뺀 쓸 수 있는 높이
        g = self.settings.get("window_geometry") or ""
        try:
            size, x, y = g.split("+")[0], int(g.split("+")[1]), int(g.split("+")[2])
            w, h = map(int, size.split("x"))
            if w < 600 or h < 400:
                raise ValueError
        except (ValueError, IndexError):
            w, h = Metrics.px(1400), Metrics.px(860)
            x = y = None
        # 작업 표시줄에 가리지 않게 작업 영역 안으로
        w, h = min(w, aw - 16), min(h, ah)
        if x is None:
            x, y = left + (aw - w) // 2, top + max(0, (ah - h) // 3)
        x = max(left, min(x, right - w))
        y = max(top, min(y, top + ah - h))
        self._work_bottom = bottom

        def fit_to_work_area():
            # 창이 뜬 뒤 실제 아래쪽 끝을 재서 작업 표시줄에 가리면 줄인다(제목줄 높이는 환경마다 다름)
            if r.state() != "normal":
                return
            over = r.winfo_rooty() + r.winfo_height() + Metrics.px(8) - bottom
            if over > 0:
                r.geometry(f"{r.winfo_width()}x{max(400, r.winfo_height() - over)}")
        r.after(300, fit_to_work_area)
        r.geometry(f"{w}x{h}+{x}+{y}")
        r.minsize(Metrics.px(640), Metrics.px(480))
        if self.settings.get_bool("window_zoomed"):
            r.after(10, lambda: r.state("zoomed"))

    # ================================================================== [1.2] 로그인·로그아웃
    def show_login(self):
        """로그인 화면(시작 화면)을 덮는다. 메뉴는 숨기고, 화면 뒤의 작업은 비워 둔다."""
        self.root.config(menu="")
        self.login_screen = LoginScreen(self.root, self.users, self.settings, self._on_login, self._signup)

    def _signup(self, prefill: str) -> User | None:
        return SignupDialog(self.root, self.users, prefill).show()

    def _on_login(self, user: User):
        self.login_screen = None
        self.login_as(user, play=True)

    def login_as(self, user: User, play: bool = True):
        """사용자 자료(블록 종류·예시·시작 템플릿·자동 저장)를 불러와 작업 화면을 연다."""
        self.user = user
        self.repo.owner_id = user.id
        self.settings.user_id = user.id
        self._load_custom_types()
        added = self.repo.seed_samples(self.samples, self.settings) if self.samples else []
        if added:
            log.info("%s: 코레일 예시 %d개 추가", user.username, len(added))
        self.history.clear()
        self._pending = None
        row = self.autosave.load()
        recover = (row["payload"] if row is not None and row["clean_exit"] == 0 and row["payload"]
                   and row["user_id"] == user.id else None)
        # 시작할 때 열 템플릿: 지난번 템플릿 → (첫 로그인이면) 코레일 예시 → 가장 최근 내 템플릿 → 라이브러리 예시 → 빈 템플릿
        first = self.settings.get("first_run_done") != "1"
        uid = self.settings.get("last_template_uuid") or ""
        t = self.repo.get_by_uuid(uid) if uid else None
        if t is not None and t.is_library:
            t = t.editable_copy()
        self.hint_msg = ""
        if t is None:
            t = self.repo.get_by_uuid(sample_uuid(user.id, START_SAMPLE)) if first else None
            mine = self.repo.list(library=False)
            if t is None and mine:
                t = self.repo.get(mine[0].id)
            if t is not None and first:
                self.hint_msg = (f"코레일 업무 예시 {len(mine)}개가 내 템플릿에 들어 있어요. "
                                 "파일 > 열기에서 골라 보세요.")
        if t is None:
            lib = self.repo.library_by_name(EXAMPLE_NAME)
            t = lib.editable_copy() if lib else None
        self.t = t or Template.blank()
        self.saved_json = self.cur_json()
        self.render_all()
        self.root.config(menu=self.menubar)
        self._paint_user()
        if play and self.settings.get_bool("boot_sound_enabled", True):
            self.sound.play(boot_sound_file(self.settings))
        self.settings.set("first_run_done", "1")
        log.info("로그인: %s", user.username)
        if not self.hint_msg:
            self.flash(f"{user.label}님, 반가워요")
        if recover:
            if ask_yes_no(self.root, "지난번 프로그램이 정상적으로 닫히지 않았어요.\n지난번 작업을 복구할까요?",
                          "작업 복구", "q", yes="복구", no="버리기"):
                payload = recover
                try:
                    t = Template.from_dict(json.loads(payload))
                    saved = self.repo.get(t.id) if t.id else None
                    self.t = t
                    self.saved_json = self.cur_json_of(saved) if saved else None
                    self.history.clear()
                    self.render_all()
                    self.flash("지난번 작업을 복구했어요")
                except (ValueError, KeyError, TypeError):
                    log.exception("자동 저장 복구 실패")
                    msgbox(self.root, "복구할 수 없는 자동 저장 자료예요.", "작업 복구", "warn")
        self._autosave()
        self.blocks_panel.widgets and self.blocks_panel.widgets[0].text.focus_set()

    def _finish_session(self) -> bool:
        """저장 안 한 변경을 물어보고 사용자 세션을 정리한다. 취소하면 False."""
        if self.dirty and self._has_content():
            r = msgbox(self.root, f"\"{self.t.name or '제목 없음'}\"의 변경 내용을 저장할까요?", "저장 확인", "q",
                       [("저장", "save", True), ("저장 안 함", "discard"), ("취소", None)])
            if r is None or (r == "save" and not self.save()):
                return False
        try:
            if self.t.id is not None:
                self.settings.set("last_template_uuid", self.t.uuid)
            self._autosave()
            self.autosave.set_clean_exit(True)
        except sqlite3.Error:
            log.exception("세션 정리 중 DB 오류")
        return True

    def logout(self):
        if self.user is None or self._modal_open() or not self._finish_session():
            return
        log.info("로그아웃: %s", self.user.username)
        self.user = None
        self.repo.owner_id = None
        self.settings.user_id = None
        self._load_custom_types()
        self.history.clear()
        self.t = Template.blank()
        self.saved_json = self.cur_json()
        self.render_all()
        self._paint_user()
        self.show_login()

    def _paint_user(self):
        """툴바 오른쪽 사용자 칸: 이름(없으면 아이디)과 아이디."""
        u = self.user
        if u is None:
            self.user_name.config(text="")
            self.user_id.config(text="")
            return
        self.user_name.config(text=f"{u.label} 님")
        self.user_id.config(text=f"아이디 {u.username}")

    def change_password(self):
        if self.user and ChangePasswordDialog(self.root, self.users, self.user).show():
            msgbox(self.root, "비밀번호를 바꿨어요. 다음 로그인부터 새 비밀번호를 쓰세요.", "비밀번호 바꾸기", "ok")

    # ================================================================== [1.2] 사용자 블록 종류
    def _load_custom_types(self):
        defs = []
        if self.user is not None:
            try:
                defs = json.loads(self.settings.get("custom_block_types") or "[]")
            except ValueError:
                defs = []
        set_custom_block_types(defs)
        self.blocks_panel.render_palette()
        self._rebuild_block_menu()

    def _save_custom_types(self, defs: list[dict]):
        defs = set_custom_block_types(defs)
        self.settings.set("custom_block_types", json.dumps(defs, ensure_ascii=False))
        self.blocks_panel.render_palette()
        self._rebuild_block_menu()
        self.refresh(blocks=True)

    def add_block_type(self):
        d = BlockTypeDialog(self.root).show()
        if d:
            self._save_custom_types(custom_block_types() + [d])
            self.flash(f"\"{d['name']}\" 블록 종류를 만들었어요. 팔레트에서 눌러 넣으세요.")

    def delete_block_type(self, key: str):
        name = block_name(key)
        used = sum(1 for b in self.t.blocks if b.type == key)
        extra = (f"\n지금 템플릿에 이 종류의 블록이 {used}개 있어요. 블록 내용은 그대로 남고 회색 블록으로 보여요."
                 if used else "")
        if not ask_yes_no(self.root, f"\"{name}\" 블록 종류를 지울까요?{extra}", "블록 종류 지우기", "warn",
                          yes="지우기", no="취소", default_yes=False):
            return
        self._save_custom_types([d for d in custom_block_types() if d["key"] != key])
        self.flash(f"\"{name}\" 블록 종류를 지웠어요")

    def register_block_types(self, defs: list[dict]):
        """가져오기 파일에 담긴 블록 종류 중 처음 보는 것만 내 목록에 더한다."""
        have = {d["key"] for d in custom_block_types()}
        new = [d for d in defs if d["key"] not in have]
        if new:
            self._save_custom_types(custom_block_types() + new)

    # ================================================================== 상태·스냅샷
    @staticmethod
    def cur_json_of(t: Template) -> str:
        return json.dumps(t.to_dict(), ensure_ascii=False, sort_keys=True)

    def cur_json(self) -> str:
        return self.cur_json_of(self.t)

    @property
    def dirty(self) -> bool:
        return self.saved_json != self.cur_json()

    def snap(self):
        self.history.push(self.cur_json())
        self._pending = None

    def begin_edit(self):
        self._pending = self.cur_json()

    def note_typing(self):
        if self._pending is not None:
            self.history.push(self._pending)
            self._pending = None

    def _after(self, name: str, ms: int, fn):
        job = self._jobs.pop(name, None)
        if job:
            self.root.after_cancel(job)
        self._jobs[name] = self.root.after(ms, lambda: (self._jobs.pop(name, None), fn()))

    def changed(self, now: bool = False):
        """모델이 바뀐 뒤 호출: 미리보기(150ms 디바운스)와 자동 저장 예약."""
        self.hint_msg = ""
        if now:
            self._refresh_preview()
        else:
            self._after("preview", 150, self._refresh_preview)
        secs = max(1, self.settings.get_int("autosave_seconds", 2))
        self._after("autosave", secs * 1000, self._autosave)

    def refresh(self, vars=False, blocks=False, form=False, focus=None, delay: int = 0):
        if vars:
            self.vars_panel.render()
        if blocks:
            self.blocks_panel.render(focus)
        elif vars:
            self._update_block_var_lists()
        if form:
            if delay:
                self._after("form", delay, self.form_panel.render)
            else:
                self.form_panel.render()
        self.changed(now=True)

    def _update_block_var_lists(self):
        vals = [v.name for v in self.t.variables]
        for w in self.blocks_panel.widgets:
            w.ins.config(values=vals)
            w.decorate()  # 변수 등록·삭제에 따라 칸 색(파랑/빨강)이 바뀜

    def render_all(self):
        self.name_var.set(self.t.name)
        self.cat_box.set(self.t.category if self.t.category in CATEGORIES else "기타")
        self.vars_panel.render()
        self.blocks_panel.render()
        self.form_panel.render()
        self._refresh_preview()

    def _refresh_preview(self):
        self.preview_panel.refresh()
        self._refresh_status()

    def _refresh_status(self):
        t = self.t
        text = build_prompt(t)
        miss = len(missing_vars(t))
        sec = len(sec_scan(text))
        self.st[0].config(text=self.flash_msg or self.hint_msg or "준비")
        self.st[1].config(text=f"블록 {len(t.blocks)} · 변수 {len(t.variables)}")
        self.st[2].config(text=f"미입력 {miss}개" if miss else "입력 완료")
        self.st[3].config(text=f"{len(text):,}자" + (f" · 보안 주의 {sec}" if sec else ""))
        dirty = self.dirty
        name = t.name or "제목 없음"
        self.root.title(f"{APP_TITLE} - {name}{' *' if dirty else ''}")
        self.task_lab.config(text=(name if len(name) <= 22 else name[:21] + "…"))
        self.lib_note.config(text="(저장 전 사본)" if t.id is None else "")

    def flash(self, msg: str):
        self.flash_msg = msg
        self._refresh_status()
        self._after("flash", 3500, self._clear_flash)

    def _clear_flash(self):
        self.flash_msg = ""
        self._refresh_status()

    def _autosave(self):
        try:
            if self.user is not None:
                self.autosave.save(json.dumps(self.t.to_dict(), ensure_ascii=False), self.t.id, self.user.id)
        except sqlite3.Error:
            log.exception("자동 저장 실패")

    def _name_changed(self, *_):
        v = self.name_var.get()
        if len(v) > 60:
            self.name_var.set(v[:60])
            return
        if v != self.t.name:
            self.note_typing()
            self.t.name = v
            self.changed()

    def _cat_changed(self, _e):
        c = self.cat_box.get()
        if c != self.t.category:
            self.snap()
            self.t.category = c
            self.changed(now=True)

    # ================================================================== 변수
    def add_variable(self, name: str, typ: str = "text", quiet: bool = False) -> bool:
        name = name.strip()
        if not valid_var_name(name) or self.t.var(name):
            if not quiet:
                msgbox(self.root, f"\"{name}\" 변수는 이미 있어요." if self.t.var(name) else NAME_RULE, "알림", "warn")
            return False
        self.snap()
        self.t.variables.append(Variable(name, typ, "예,아니오" if typ == "select" else ""))
        self.t.values.setdefault(name, "")
        self.refresh(vars=True, form=True)
        return True

    def scan_vars(self):
        miss = [k for k in used_vars(self.t, only_enabled=False) if not self.t.var(k)]
        if not miss:
            msgbox(self.root, "블록에 쓰인 변수가 모두 등록되어 있어요.", "변수 찾기", "ok")
            return
        self.snap()
        bad = []
        for k in miss:
            if valid_var_name(k):
                self.t.variables.append(Variable(k))
                self.t.values.setdefault(k, "")
            else:
                bad.append(k)
        self.refresh(vars=True, form=True)
        msgbox(self.root, f"변수 {len(miss) - len(bad)}개를 찾아 추가했어요."
               + (f"\n이름 규칙에 맞지 않아 건너뜀: {', '.join(bad)}" if bad else ""), "변수 찾기", "ok")

    def insert_var(self, name: str, text: tk.Text | None = None, index: str | None = None):
        if text is None:
            text = self.last_text if self.last_text is not None and self.last_text.winfo_exists() else None
            if text is None and self.last_block_key:
                w = self.blocks_panel.widget_for(self.last_block_key)
                text = w.text if w else None
            if text is None and self.blocks_panel.widgets:
                text = self.blocks_panel.widgets[-1].text
        if text is None:
            msgbox(self.root, "먼저 블록을 하나 추가해 주세요.", "알림", "info")
            return
        bw = text.master
        self.snap()
        if bw.placeholder.showing:
            bw.placeholder._in()
        tok = "{{" + name + "}}"
        if index is None:
            try:
                text.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            index = text.index("insert")
        text.insert(index, tok)
        text.mark_set("insert", f"{index}+{len(tok)}c")
        text.focus_set()
        bw._text_changed()
        self.last_text = text

    def clear_values(self):
        self.snap()
        for k in list(self.t.values):
            self.t.values[k] = ""
        self.refresh(form=True)
        self.flash("입력값을 모두 지웠어요")

    # ================================================================== 실행 취소
    def undo(self):
        s = self.history.undo(self.cur_json())
        if s is None:
            self.flash("되돌릴 작업이 없어요")
            return
        self._restore(s)
        self.flash("실행 취소했어요")

    def redo(self):
        s = self.history.redo(self.cur_json())
        if s is None:
            self.flash("다시 실행할 작업이 없어요")
            return
        self._restore(s)
        self.flash("다시 실행했어요")

    def _restore(self, s: str):
        self._pending = None
        self.t = Template.from_dict(json.loads(s))
        self.render_all()
        self.changed(now=True)

    # ================================================================== 파일
    def _has_content(self) -> bool:
        return any(b.content.strip() for b in self.t.blocks)

    def load_template(self, t: Template, label: str, confirm: bool = True):
        if confirm and self._has_content() and self.dirty:
            if not ask_yes_no(self.root, f"지금 작업 중인 내용을 \"{label}\"(으)로 바꿀까요?\n"
                                         "(편집 > 실행 취소로 되돌릴 수 있어요)", "불러오기"):
                return
        self.snap()
        self.t = t
        self.saved_json = self.cur_json() if t.id is not None else self.cur_json()
        self.render_all()
        self.changed(now=True)
        self.flash(f"\"{label}\"을(를) 불러왔어요")

    def new_template(self):
        if self._has_content() and not ask_yes_no(
                self.root, "새로 만들까요? 지금 작업은 사라지지만 실행 취소로 되돌릴 수 있어요.", "새로 만들기"):
            return
        self.snap()
        self.t = Template.blank()
        self.saved_json = self.cur_json()
        self.render_all()
        self.changed(now=True)
        self.flash("새 템플릿을 시작했어요")

    def open_dialog(self):
        d = OpenDialog(self.root, self.repo, self.t.id)
        r = d.show()
        if d.deleted_current:
            self.t.id = None
            self.saved_json = None
            self.changed(now=True)
        if r and r[0] == "open":
            t = self.repo.get(r[1])
            if t:
                self.load_template(t, t.name)
                self.settings.set("last_template_uuid", t.uuid)

    def save(self) -> bool:
        if self.t.id is None or not self.repo.exists_uuid(self.t.uuid):
            return self.save_as()
        try:
            self.repo.save(self.t)
        except ReadOnlyError as e:
            msgbox(self.root, str(e), "저장", "warn")
            return self.save_as()
        self._after_save()
        self.flash(f"\"{self.t.name}\" 저장 완료 · {clock_text()}")
        return True

    def save_as(self) -> bool:
        r = save_as_dialog(self.root, self.t.name, self.t.category)
        if not r:
            return False
        self.snap()
        self.t.name, self.t.category = r
        self.t.uuid, self.t.id, self.t.is_library = new_uuid(), None, False
        self.repo.save(self.t)
        self._after_save()
        self.name_var.set(self.t.name)
        self.cat_box.set(self.t.category)
        self.flash(f"\"{self.t.name}\" 저장 완료")
        return True

    def _after_save(self):
        self.saved_json = self.cur_json()
        self.settings.set("last_template_uuid", self.t.uuid)
        self._autosave()
        self._refresh_status()

    def export(self):
        p = export_to_file(self.root, self.repo, self.t)
        if p:
            msgbox(self.root, f"저장된 템플릿 {self.repo.count()}개와 현재 작업을 내보냈어요.\n{p}", "내보내기", "ok")

    def import_(self):
        r = import_from_file(self.root, self.repo, self.register_block_types)
        if r:
            n, dropped = r
            msgbox(self.root, f"템플릿 {n}개를 가져왔어요. 파일 > 열기에서 확인하세요."
                   + (f"\n알 수 없는 형식의 블록·변수 {dropped}개는 버렸어요." if dropped else ""), "가져오기 완료", "ok")

    def save_txt(self):
        text = build_prompt(self.t)
        if not text.strip():
            msgbox(self.root, "저장할 내용이 없어요. 블록에 내용을 먼저 써 주세요.")
            return
        p = save_text_file(self.root, text, self.t.name)
        if p:
            self.flash(f"텍스트 파일로 저장했어요: {p.name}")

    # ================================================================== 도구
    def copy_flow(self):
        text = build_prompt(self.t)
        if not text.strip():
            msgbox(self.root, "복사할 내용이 없어요. 블록에 내용을 먼저 써 주세요.")
            return
        miss, sec = missing_vars(self.t), sec_scan(text)
        if not miss and not sec:
            self._copy(text)
            return
        lines = []
        if miss:
            lines.append(f"아직 입력하지 않은 변수 {len(miss)}개: {', '.join(miss)}\n"
                         f"(빈 칸은 {{{{{miss[0]}}}}}처럼 괄호 모양 그대로 복사됩니다)")
        if sec:
            lines.append(f"민감 정보로 보이는 항목 {len(sec)}건이 있어요.")
        r = msgbox(self.root, "\n\n".join(lines) + "\n\n그래도 복사할까요?", "복사 전 확인", "warn",
                   [("그래도 복사", "copy"), ("점검 열기", "check", True), ("취소", None)], width=460)
        if r == "copy":
            self._copy(text)
        elif r == "check":
            self.open_check("security" if sec else "config")

    def _copy(self, text: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        msgbox(self.root, f"프롬프트를 클립보드에 복사했어요. ({len(text):,}자)\n\n"
                          "AI 채팅창에 붙여 넣으세요. (Ctrl+V)", "복사 완료", "ok")

    def open_check(self, tab: str = "config"):
        CheckDialog(self, tab).show()

    def record_check(self, r: CheckResult):
        try:
            self.check_runs.add(self.t.id, r.score, [f.to_dict() for f in r.all])
        except sqlite3.Error:
            log.exception("점검 기록 실패")

    def apply_check_fix(self, fix: str):
        self.snap()
        before = len(self.t.blocks)
        apply_fix(self.t, fix)
        focus = (self.t.blocks[-1].key, "text") if len(self.t.blocks) > before else None
        self.refresh(vars=True, blocks=True, form=True, focus=focus)
        self.flash("점검 항목을 고쳤어요")

    def mask_sensitive(self, keys: list[str]):
        self.snap()
        mask_template(self.t, keys)
        self.refresh(blocks=True, form=True)
        self.flash("민감 정보를 가렸어요 (실행 취소 가능)")

    def wizard(self):
        t = WizardDialog(self.root, self.settings).show()
        if not t:
            return
        self.load_template(t, t.name, confirm=False)
        self.saved_json = None
        self.changed(now=True)
        self.flash("아티팩트 마법사로 템플릿을 만들었어요. 미리보기를 확인하고 복사하세요.")
        if sec_scan(build_prompt(self.t)):
            if msgbox(self.root, "비밀번호나 개인정보로 보이는 값이 있어요. [점검]에서 확인해 보세요.", "보안 알림",
                      "warn", [("점검 열기", True, True), ("나중에", False)]):
                self.open_check("security")

    def library(self):
        tid = LibraryDialog(self.root, self.repo).show()
        if tid:
            lib = self.repo.get(tid)
            if lib:
                self.load_template(lib.editable_copy(), lib.name)

    def settings_dialog(self):
        ai_before = self.ai_enabled()
        SettingsDialog(self.root, self.settings, self.sound, self.data_dir).show()
        self._paint_speaker()
        if self.ai_enabled() != ai_before:          # AI 추천 단추를 보이거나 숨긴다
            self.blocks_panel.render()

    # ================================================================== [1.5] AI 추천
    def ai_enabled(self) -> bool:
        return self.settings.get_bool("ai_enabled", True)

    def suggest_block(self, b):
        """블록 하나에 쓸 내용을 gemma4(Ollama)에게 추천받아 고른 것을 넣는다 (Ctrl+Z 로 되돌리기)."""
        if self._modal_open() or b not in self.t.blocks:
            return
        w = self.blocks_panel.widget_for(b.key)
        if w is not None:
            w._text_changed()                       # 방금 친 글자까지 모델에 반영
        r = SuggestDialog(self.root, ai.AIConfig.from_settings(self.settings), self.t, b).show()
        if not r or b not in self.t.blocks:
            return
        mode, text = r
        self.snap()
        new = suggest_merge(b.content, text, mode)
        w = self.blocks_panel.widget_for(b.key)
        if w is None:
            b.content = new
            self.refresh(blocks=True)
        else:
            w.set_content(new)
            w._text_changed()
            w.text.mark_set("insert", "end-1c")
            w.text.see("insert")
            w.text.focus_set()
        self.flash("AI 추천을 넣었어요 (되돌리기: Ctrl+Z)")

    def help(self):
        msgbox(self.root,
               "엑셀 없이 만드는 프롬프트 템플릿\n\n"
               "1. 변수 영역에 바뀌는 값의 이름(예: 부서명)을 추가합니다. 엑셀의 A3, B3 같은 셀이라고 생각하세요.\n\n"
               "2. 블록 편집기에 역할·지시사항·출력 형식 등을 쓰고, 바뀌는 자리에는 변수(파란 칸)를 눌러 넣습니다. "
               "CONCATENATE 수식 대신이에요.\n\n"
               "3. 입력 양식이 자동으로 생깁니다. 값만 채우면 미리보기가 바로 바뀝니다(노란색 = 채운 값, 빨간 칸 = 아직 빈 값).\n\n"
               "4. 점검으로 빠진 구성과 비밀번호·개인정보를 확인하고 복사해서 AI 채팅창에 붙여 넣으세요.\n\n"
               "처음이라면 아티팩트 마법사나 라이브러리에서 시작하는 게 가장 쉬워요.\n\n"
               "단축키: Ctrl+N 새로 만들기 · Ctrl+O 열기 · Ctrl+S 저장 · Ctrl+Z 실행 취소 · Ctrl+Y 다시 실행 · "
               "Ctrl+Enter 복사 · Alt+F/E/T/H 메뉴",
               "사용법", "help", width=600)

    def about(self):
        msgbox(self.root,
               f"프롬프트 템플릿 생성기 버전 {__version__}\n\n"
               f"사용자: {self.user.label if self.user else '-'} ({self.user.username if self.user else ''})\n"
               f"저장 위치: {self.data_dir}\n"
               f"라이브러리: 업무 템플릿 {self.repo.count(library=True)}종 · 내 템플릿 {self.repo.count()}개\n\n"
               "글꼴: 둥근모꼴(퍼블릭 도메인)\n"
               "기본 부팅음은 이 프로그램을 위해 새로 만든 효과음입니다. 도움말 > 설정에서 내 소리 파일로 바꿀 수 있어요.",
               "프로그램 정보", "app", width=480)

    # ---------------------------------------------------------------- 시작 메뉴
    def toggle_start_menu(self):
        if getattr(self, "_start_menu", None) is not None and self._start_menu.winfo_exists():
            self._close_start_menu()
            return
        if self.user is None:
            return
        m = tk.Toplevel(self.root)
        m.wm_overrideredirect(True)
        try:
            m.attributes("-topmost", True)
        except tk.TclError:
            pass
        outer = tk.Frame(m, relief="raised", bd=2)
        outer.pack(fill="both", expand=True)
        from .widgets.win98 import Gradient
        side = Gradient(outer, vertical=True, text="프롬프트 98", width=Metrics.px(30))
        side.pack(side="left", fill="y")
        items = tk.Frame(outer)
        items.pack(side="left", fill="both", expand=True)
        entries = [("wand", "아티팩트 마법사", self.wizard), ("lib", "프롬프트 라이브러리", self.library),
                   ("new", "새 템플릿", self.new_template), ("open", "저장된 템플릿 열기", self.open_dialog),
                   ("shield", "구성·보안 점검", self.open_check), ("help", "사용법", self.help),
                   ("gear", "설정(부팅음)", self.settings_dialog), None,
                   ("start", f"로그아웃 ({self.user.label if self.user else ''})", self.logout),
                   ("app", "끝내기", self.on_close)]
        for e in entries:
            if e is None:
                tk.Frame(items, height=2, bd=1, relief="sunken").pack(fill="x", pady=Metrics.px(2))
                continue
            lab = tk.Label(items, text="  " + e[1], image=icons.get(e[0], 32), compound="left", anchor="w",
                           padx=Metrics.px(8), pady=Metrics.px(3), width=Metrics.px(220))
            lab.pack(fill="x")
            lab.bind("<Enter>", lambda ev, w=lab: w.config(bg=theme.NAVY, fg=theme.WHITE))
            lab.bind("<Leave>", lambda ev, w=lab: w.config(bg=theme.FACE, fg="#000"))
            lab.bind("<ButtonRelease-1>", lambda ev, f=e[2]: (self._close_start_menu(), self.root.after(10, f)))
        m.update_idletasks()
        x = self.start_btn.winfo_rootx()
        y = self.start_btn.winfo_rooty() - m.winfo_reqheight() - 2
        m.wm_geometry(f"+{x}+{max(0, y)}")
        self._start_menu = m
        self.start_btn.config(relief="sunken")
        m.bind("<Escape>", lambda e: self._close_start_menu())
        m.bind("<FocusOut>", lambda e: self.root.after(150, self._close_start_menu_if_unfocused))
        m.focus_force()

    def _close_start_menu_if_unfocused(self):
        m = getattr(self, "_start_menu", None)
        if m is not None and m.winfo_exists():
            f = self.root.focus_get()
            if f is None or f.winfo_toplevel() is not m:
                self._close_start_menu()

    def _close_start_menu(self):
        m = getattr(self, "_start_menu", None)
        if m is not None and m.winfo_exists():
            m.destroy()
        self._start_menu = None
        self.start_btn.config(relief="raised")

    # ================================================================== 종료
    def on_close(self):
        if self._modal_open():
            return
        if self.user is not None and not self._finish_session():   # 로그인 화면이면 저장할 작업이 없다
            return
        try:
            zoomed = self.root.state() == "zoomed"
            self.settings.set("window_zoomed", zoomed)
            if not zoomed:
                self.settings.set("window_geometry", self.root.wm_geometry())
        except sqlite3.Error:
            log.exception("종료 처리 중 DB 오류")
        self.sound.stop()
        for job in self._jobs.values():
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        log.info("정상 종료")
        self.root.destroy()
