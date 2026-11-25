"""아티팩트 마법사 (7단계)."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk

from .. import theme
from ..builder import build_segments
from ..model import Block, Template, Variable
from ..theme import Fonts, Metrics
from ..widgets.preview_panel import configure_preview_tags, fill_preview
from ..widgets.win98 import Gradient, Win98Button
from .base import Dialog, ask_yes_no, msgbox

MODES = ["제작하기 위한 프롬프트를 만들어줘.", "제작해줘."]
STYLES = ["깔끔한 업무용", "Windows 98 레트로", "다크 모드", "모바일 우선", "귀엽고 친근한"]
QUICK_FEATURES = ["비밀번호로 접속 제한", "관리자/일반 사용자 권한 구분", "새로고침해도 데이터 유지",
                  "처음 열면 예시 데이터 표시", "검색·필터", "그래프로 시각화", "엑셀(CSV)로 내보내기", "인쇄용 화면"]
QUICK_NAMES = ["회의록 작성기", "팀 업무 현황판", "교육 출석부", "명함 제작기", "민원 답변 도우미", "점심 메뉴 추천기"]
TITLES = ["시작", "이름", "목적", "기능", "화면·추가 요청", "요청 방식", "완료"]
LAST = len(TITLES) - 1

# ---------------------------------------------------------------- 자주 쓰는 기능 목록 (설정에 저장)
QUICK_KEY = "wizard_quick_features"
MAX_QUICK = 20
MAX_QUICK_LEN = 40


def clean_quick(items) -> list[str]:
    """앞뒤 공백 제거, 빈 줄·중복 제거, 길이·개수 제한."""
    out: list[str] = []
    for s in items or []:
        s = " ".join(str(s).split())[:MAX_QUICK_LEN]
        if s and s not in out:
            out.append(s)
    return out[:MAX_QUICK]


def load_quick_features(settings) -> list[str]:
    """저장된 목록(없으면 기본 8개). 사용자가 모두 지웠다면 빈 목록 그대로."""
    raw = settings.get(QUICK_KEY) if settings is not None else None
    if not raw:
        return list(QUICK_FEATURES)
    try:
        data = json.loads(raw)
    except ValueError:
        return list(QUICK_FEATURES)
    return clean_quick(data) if isinstance(data, list) else list(QUICK_FEATURES)


def save_quick_features(settings, items) -> list[str]:
    items = clean_quick(items)
    settings.set(QUICK_KEY, json.dumps(items, ensure_ascii=False))
    return items


class QuickListDialog(Dialog):
    """자주 쓰는 기능 편집: 추가·고치기·삭제·순서 바꾸기·기본값. 결과는 새 목록(취소면 None)."""

    def __init__(self, parent, items: list[str]):
        super().__init__(parent, "자주 쓰는 기능 편집", min_width=560)
        self.items = list(items)
        tk.Label(self.body, text="아티팩트 마법사 4단계에서 눌러 넣을 기능 목록입니다.", anchor="w").pack(fill="x")
        tk.Label(self.body, text=f"한 항목은 {MAX_QUICK_LEN}자 이내, 최대 {MAX_QUICK}개까지 둘 수 있어요.",
                 font=Fonts.small, fg=theme.HINT_FG, anchor="w").pack(fill="x", pady=(0, Metrics.px(6)))
        mid = tk.Frame(self.body)
        mid.pack(fill="both", expand=True)
        self.lb = tk.Listbox(mid, height=10, exportselection=False, activestyle="none")
        self.lb.pack(side="left", fill="both", expand=True)
        side = tk.Frame(mid, padx=Metrics.px(8))
        side.pack(side="left", fill="y")
        for text, cmd in (("▲ 위로", lambda: self.move(-1)), ("▼ 아래로", lambda: self.move(1)),
                          ("삭제", self.delete)):
            Win98Button(side, text, cmd, width=8).pack(fill="x", pady=(0, Metrics.px(4)))
        Win98Button(side, "기본값으로", self.reset, width=8).pack(fill="x", side="bottom")

        row = tk.Frame(self.body)
        row.pack(fill="x", pady=(Metrics.px(8), 0))
        tk.Label(row, text="기능").pack(side="left")
        self.var = tk.StringVar()
        self.entry = tk.Entry(row, textvariable=self.var)
        self.entry.pack(side="left", fill="x", expand=True, padx=Metrics.px(6))
        self.var.trace_add("write", lambda *_: len(self.var.get()) > MAX_QUICK_LEN
                           and self.var.set(self.var.get()[:MAX_QUICK_LEN]))
        Win98Button(row, "추가", self.add).pack(side="left")
        Win98Button(row, "고치기", self.update_selected).pack(side="left", padx=(Metrics.px(4), 0))
        self.entry.bind("<Return>", lambda e: (self.add(), "break")[1])
        self.lb.bind("<<ListboxSelect>>", self._selected)
        self.lb.bind("<Delete>", lambda e: self.delete())
        self.add_buttons([("확인", True, True), ("취소", None)], self._handle)
        self.redraw()

    def redraw(self, select: int | None = None):
        self.lb.delete(0, "end")
        for s in self.items:
            self.lb.insert("end", s)
        if not self.items:
            self.lb.insert("end", "(비어 있음 — 아래 칸에 적고 [추가]를 누르세요)")
            self.lb.itemconfig(0, fg=theme.SHADOW)
        elif select is not None:
            select = max(0, min(select, len(self.items) - 1))
            self.lb.selection_set(select)
            self.lb.see(select)

    def _sel(self) -> int | None:
        s = self.lb.curselection()
        return s[0] if s and self.items and s[0] < len(self.items) else None

    def _selected(self, _e=None):
        i = self._sel()
        if i is not None:
            self.var.set(self.items[i])

    def _check(self, text: str, ignore: int | None = None) -> str | None:
        if not text:
            msgbox(self, "기능 내용을 입력해 주세요.", "알림", "warn")
            return None
        if any(s == text for k, s in enumerate(self.items) if k != ignore):
            msgbox(self, f"\"{text}\"은(는) 이미 목록에 있어요.", "알림", "warn")
            return None
        return text

    def add(self):
        text = self._check(" ".join(self.var.get().split()))
        if text is None:
            return
        if len(self.items) >= MAX_QUICK:
            msgbox(self, f"최대 {MAX_QUICK}개까지만 둘 수 있어요. 안 쓰는 항목을 먼저 지워 주세요.", "알림", "warn")
            return
        self.items.append(text)
        self.var.set("")
        self.redraw(len(self.items) - 1)
        self.var.set("")
        self.entry.focus_set()

    def update_selected(self):
        i = self._sel()
        if i is None:
            msgbox(self, "목록에서 고칠 항목을 먼저 골라 주세요.")
            return
        text = self._check(" ".join(self.var.get().split()), ignore=i)
        if text is None:
            return
        self.items[i] = text
        self.redraw(i)

    def delete(self):
        i = self._sel()
        if i is None:
            msgbox(self, "목록에서 지울 항목을 먼저 골라 주세요.")
            return
        self.items.pop(i)
        self.var.set("")
        self.redraw(i)

    def move(self, d: int):
        i = self._sel()
        if i is None or not (0 <= i + d < len(self.items)):
            return
        self.items[i], self.items[i + d] = self.items[i + d], self.items[i]
        self.redraw(i + d)

    def reset(self):
        if ask_yes_no(self, "처음 들어 있던 기능 8개로 되돌릴까요?\n지금 목록은 사라집니다.", "기본값으로", "q"):
            self.items = list(QUICK_FEATURES)
            self.var.set("")
            self.redraw(0)

    def _handle(self, v):
        if v is not None:
            self.result_items = clean_quick(self.items)
        return True

    def show(self, focus=None):
        self.result_items = None
        super().show(focus=self.entry)
        return self.result_items


def make_template(name: str, purpose: str, user: str, feats: list[str], style: str, extra: str, mode: str) -> Template:
    """마법사 답변 → 변수가 들어간 템플릿 (부록 C)."""
    feat_text = "\n".join(f"{i}) {s.strip()}" for i, s in enumerate([f for f in feats if f.strip()], 1))
    vars_ = [Variable("요청방식", "select", ",".join(MODES)), Variable("아티팩트이름"),
             Variable("아티팩트목적", "area"), Variable("아티팩트기능", "area")]
    values = {"요청방식": mode, "아티팩트이름": name, "아티팩트목적": purpose, "아티팩트기능": feat_text}
    body = "1. 아티팩트 이름:\n{{아티팩트이름}}\n2. 아티팩트 목적:\n{{아티팩트목적}}"
    n = 3
    if user.strip():
        vars_.append(Variable("사용대상"))
        values["사용대상"] = user
        body += "\n- 사용 대상: {{사용대상}}"
    body += f"\n{n}. 아티팩트 기능:\n{{{{아티팩트기능}}}}"
    n += 1
    if style:
        vars_.append(Variable("화면스타일", "select", ",".join(STYLES)))
        values["화면스타일"] = style
        body += f"\n{n}. 화면 디자인:\n{{{{화면스타일}}}}"
        n += 1
    if extra.strip():
        vars_.append(Variable("추가요청", "area"))
        values["추가요청"] = extra
        body += f"\n{n}. 추가 요청:\n{{{{추가요청}}}}"
    # 결과가 "아래의 지시에 따라 아티팩트를 …"로 시작하므로 기본 첫 문장(intro)은 붙이지 않는다
    return Template(name=(name.strip() or "아티팩트 제작 요청")[:60], category="아티팩트 제작", title_style="none",
                    intro=False, variables=vars_, values=values,
                    blocks=[Block("task", content="아래의 지시에 따라 아티팩트를 {{요청방식}}"),
                            Block("text", "요청 내용", body)])


class WizardDialog(Dialog):
    def __init__(self, parent, settings=None):
        super().__init__(parent, "아티팩트 마법사", min_width=760)
        self.settings = settings
        self.quick_features = load_quick_features(settings)
        self.step = 0
        self._feat_focus = 0
        self._focus = None
        self.bind("<Return>", self._on_return)
        self.w = {"name": "", "purpose": "", "user": "", "feats": ["", "", ""], "style": "깔끔한 업무용",
                  "extra": "", "mode": MODES[0]}
        self.template: Template | None = None
        main = tk.Frame(self.body)
        main.pack(fill="both", expand=True)
        self.side = tk.Canvas(main, width=Metrics.px(150), height=Metrics.px(340), highlightthickness=0,
                              bd=2, relief="sunken")
        self.side.pack(side="left", fill="y")
        self.side.bind("<Configure>", lambda e: self._paint_side())
        self.right = tk.Frame(main, padx=Metrics.px(14))
        self.right.pack(side="left", fill="both", expand=True)
        tk.Frame(self, height=2, bd=1, relief="sunken").pack(fill="x", side="bottom", before=self.buttons)
        self.btn_cancel = Win98Button(self.buttons, "취소", self.cancel, width=8)
        self.btn_cancel.pack(side="right", padx=(Metrics.px(6), 0))
        self.btn_next = Win98Button(self.buttons, "다음(N) >", self.next, default=True, width=10)
        self.btn_next.pack(side="right")
        self.btn_back = Win98Button(self.buttons, "< 뒤로(B)", self.back, width=10)
        self.btn_back.pack(side="right")
        self.bind("<Alt-n>", lambda e: self.next())
        self.bind("<Alt-b>", lambda e: self.back())
        self.right.configure(height=Metrics.px(420), width=Metrics.px(560))
        self.right.pack_propagate(False)
        self.draw()

    # ------------------------------------------------------------------ 그림
    def _paint_side(self):
        c = self.side
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        for y in range(0, h, 3):
            col = Gradient.mix(theme.TEAL, theme.NAVY, y / max(1, h))
            c.create_rectangle(0, y, w, y + 3, fill=col, outline=col)
        s = w / 150
        def R(x, y, ww, hh, col):
            c.create_rectangle(x * s, y * s, (x + ww) * s, (y + hh) * s, fill=col, outline="")
        R(25, 70, 100, 76, "#c0c0c0"); R(27, 72, 96, 72, "#808080"); R(31, 76, 88, 64, "#000080")
        R(38, 84, 40, 5, "#ffff88"); R(38, 95, 70, 5, "#fff"); R(38, 106, 58, 5, "#fff"); R(38, 117, 30, 5, "#ffff88")
        R(62, 146, 26, 10, "#808080"); R(45, 156, 60, 10, "#c0c0c0")
        c.create_line(96 * s, 240 * s, 124 * s, 188 * s, fill="#000", width=5 * s)
        c.create_line(96 * s, 240 * s, 110 * s, 214 * s, fill="#fff", width=2 * s)
        R(120, 178, 10, 10, "#ffff00")
        for x, y in ((20, 210), (40, 250), (70, 280), (120, 40), (30, 30)):
            R(x, y, 4, 4, "#99ccff")

    def draw(self):
        for w in self.right.winfo_children():
            w.destroy()
        getattr(self, f"_step{self.step}")()
        tk.Label(self.right, text=f"{self.step + 1} / {LAST + 1} 단계 · {TITLES[self.step]}", font=Fonts.small,
                 fg=theme.HINT_FG, anchor="w").pack(side="bottom", fill="x")
        self.btn_back.config(state="disabled" if self.step == 0 else "normal")
        self.btn_next.config(text="마침" if self.step == LAST else "다음(N) >")
        f = getattr(self, "_focus", None)
        (f or self.btn_next).focus_set()
        self._focus = None

    def _h(self, text):
        tk.Label(self.right, text=text, font=Fonts.big, anchor="w").pack(fill="x", pady=(0, Metrics.px(8)))

    def _p(self, text, hint=False):
        lab = tk.Label(self.right, text=text, anchor="w", justify="left", font=Fonts.small if hint else Fonts.body,
                       fg=theme.HINT_FG if hint else "#000", wraplength=Metrics.px(520))
        lab.pack(fill="x", pady=(0, Metrics.px(6)))
        return lab

    def _quick(self, items, cb, used: set[str] = frozenset()):
        """버튼을 폭에 맞춰 여러 줄로 흘려 놓는다. used 에 있는 항목은 이미 넣었으므로 흐리게."""
        fr = tk.Frame(self.right)
        fr.pack(fill="x")
        width = Metrics.px(530)
        row, x = None, width + 1
        self.quick_buttons = {}
        for it in items:
            b_parent = row if row is not None else fr
            b = Win98Button(b_parent, it, lambda s=it: cb(s), small=True,
                            state="disabled" if it in used else "normal")
            need = b.winfo_reqwidth() + Metrics.px(3)
            if x + need > width:
                b.destroy()
                row = tk.Frame(fr)
                row.pack(fill="x", pady=1)
                x = 0
                b = Win98Button(row, it, lambda s=it: cb(s), small=True,
                                state="disabled" if it in used else "normal")
            b.pack(side="left", padx=(0, Metrics.px(3)))
            x += need
            self.quick_buttons[it] = b

    def _step0(self):
        self._h("아티팩트 마법사에 오신 것을 환영합니다")
        self._p("엑셀에서 셀을 나눠 쓰고 CONCATENATE로 붙이던 \"아티팩트 이름 · 목적 · 기능\" 요청문을, "
                "질문에 답하기만 하면 만들어 드립니다.")
        self._p("만든 결과는 변수가 들어간 템플릿으로 열리기 때문에, 다음에는 입력 양식만 바꿔서 다시 쓸 수 있어요.")
        self._p("계속하려면 [다음]을 누르세요.", hint=True)

    def _step1(self):
        self._h("무엇을 만들까요?")
        tk.Label(self.right, text="아티팩트 이름", anchor="w").pack(fill="x")
        self.e_name = tk.Entry(self.right)
        self.e_name.insert(0, self.w["name"])
        self.e_name.pack(fill="x", pady=(Metrics.px(2), Metrics.px(8)))
        self.e_name.bind("<Return>", lambda e: self.next())
        self._p("예시를 눌러 채울 수도 있어요.", hint=True)
        self._quick(QUICK_NAMES, lambda s: (self.e_name.delete(0, "end"), self.e_name.insert(0, s)))
        self._focus = self.e_name

    def _step2(self):
        self._h("왜 필요한가요?")
        tk.Label(self.right, text="아티팩트 목적", anchor="w").pack(fill="x")
        self.t_purpose = tk.Text(self.right, height=5, wrap="word")
        self.t_purpose.insert("1.0", self.w["purpose"])
        self.t_purpose.pack(fill="x", pady=(Metrics.px(2), Metrics.px(8)))
        tk.Label(self.right, text="누가 쓰나요? (선택)", anchor="w").pack(fill="x")
        self.e_user = tk.Entry(self.right)
        self.e_user.insert(0, self.w["user"])
        self.e_user.pack(fill="x", pady=(Metrics.px(2), 0))
        self._p("예) 팀원 8명과 팀장", hint=True)
        self._focus = self.t_purpose

    def _step3(self):
        self._h("어떤 기능이 필요한가요?")
        self._p("한 줄에 기능 하나씩. 번호는 자동으로 붙습니다. (Enter = 아래에 줄 추가)", hint=True)
        box = tk.Frame(self.right)
        box.pack(fill="x")
        self.feat_entries = []
        for i, f in enumerate(self.w["feats"]):
            row = tk.Frame(box)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{i + 1})", width=3, anchor="e").pack(side="left")
            e = tk.Entry(row)
            e.insert(0, f)
            e.pack(side="left", fill="x", expand=True, padx=Metrics.px(4))
            e.bind("<Return>", lambda ev, k=i: self._feat_add(k + 1))
            Win98Button(row, "×", lambda k=i: self._feat_del(k), small=True).pack(side="left")
            self.feat_entries.append(e)
        Win98Button(self.right, "+ 기능 추가", lambda: self._feat_add(len(self.w["feats"])), small=True
                    ).pack(anchor="w", pady=Metrics.px(4))
        head = tk.Frame(self.right)
        head.pack(fill="x", pady=(Metrics.px(2), Metrics.px(2)))
        tk.Label(head, text="자주 쓰는 기능 바로 넣기", font=Fonts.small, fg=theme.HINT_FG).pack(side="left")
        Win98Button(head, "편집…", self.edit_quick, small=True).pack(side="left", padx=Metrics.px(6))
        if self.quick_features:
            used = {f.strip() for f in self.w["feats"]}
            self._quick(self.quick_features, self._feat_quick, used)
        else:
            self._p("목록이 비어 있어요. [편집…]을 눌러 자주 쓰는 기능을 추가하세요.", hint=True)
        self._focus = self.feat_entries[min(self._feat_focus, len(self.feat_entries) - 1)]
        self._feat_focus = 0

    def edit_quick(self):
        """자주 쓰는 기능 목록 편집 → 설정에 저장하고 이 단계를 다시 그린다."""
        self._read()
        items = QuickListDialog(self, self.quick_features).show()
        if items is None:
            return
        self.quick_features = save_quick_features(self.settings, items) if self.settings is not None \
            else clean_quick(items)
        self.draw()

    def _feat_add(self, at):
        self._read()
        self.w["feats"].insert(at, "")
        self._feat_focus = at
        self.draw()

    def _feat_del(self, k):
        self._read()
        self.w["feats"].pop(k)
        if not self.w["feats"]:
            self.w["feats"].append("")
        self.draw()

    def _feat_quick(self, s):
        self._read()
        feats = self.w["feats"]
        i = next((k for k, f in enumerate(feats) if not f.strip()), None)
        if i is None:
            feats.append(s)
        else:
            feats[i] = s
        self.draw()

    def _step4(self):
        self._h("화면과 추가 요청")
        tk.Label(self.right, text="화면 스타일", anchor="w").pack(fill="x")
        self.c_style = ttk.Combobox(self.right, values=["(지정 안 함)"] + STYLES, state="readonly")
        self.c_style.set(self.w["style"] or "(지정 안 함)")
        self.c_style.pack(fill="x", pady=(Metrics.px(2), Metrics.px(8)))
        tk.Label(self.right, text="그 밖에 바라는 점 (선택)", anchor="w").pack(fill="x")
        self.t_extra = tk.Text(self.right, height=5, wrap="word")
        self.t_extra.insert("1.0", self.w["extra"])
        self.t_extra.pack(fill="x", pady=(Metrics.px(2), 0))
        self._p("예) 버튼은 크게, 글씨는 14px 이상", hint=True)

    def _step5(self):
        self._h("어떻게 요청할까요?")
        self.mode_var = tk.StringVar(value=self.w["mode"])
        tk.Radiobutton(self.right, text="프롬프트를 만들어 달라고 요청 (한 번 더 다듬고 싶을 때)", value=MODES[0],
                       variable=self.mode_var, anchor="w", command=self._mode_changed).pack(fill="x")
        tk.Radiobutton(self.right, text="바로 아티팩트를 만들어 달라고 요청", value=MODES[1],
                       variable=self.mode_var, anchor="w", command=self._mode_changed).pack(fill="x")
        self._p("미리보기", hint=True)
        self.pv = tk.Text(self.right, height=10, wrap="word", font=Fonts.small, state="disabled",
                          padx=Metrics.px(6), pady=Metrics.px(4))
        self.pv.pack(fill="both", expand=True)
        configure_preview_tags(self.pv)
        self.pv.tag_configure("heading", font=Fonts.small_bold)
        self._mode_changed()

    def _mode_changed(self):
        self.w["mode"] = self.mode_var.get()
        fill_preview(self.pv, build_segments(self._make()))

    def _step6(self):
        self._h("아티팩트 마법사를 완료했습니다")
        self._p(f"[마침]을 누르면 \"{self.w['name'] or '아티팩트 제작 요청'}\" 템플릿이 편집기에 열립니다.")
        self._p("입력 양식에서 내용을 고치고, 미리보기 옆의 [복사]를 눌러 Claude 채팅창에 붙여 넣으세요.")
        self._p("비밀번호 같은 값을 넣었다면 [점검]으로 한 번 확인해 보세요.", hint=True)

    # ------------------------------------------------------------------ 흐름
    def _read(self):
        s = self.step
        if s == 1:
            self.w["name"] = self.e_name.get()
        elif s == 2:
            self.w["purpose"] = self.t_purpose.get("1.0", "end-1c")
            self.w["user"] = self.e_user.get()
        elif s == 3:
            for i, e in enumerate(self.feat_entries):
                self.w["feats"][i] = e.get()
        elif s == 4:
            st = self.c_style.get()
            self.w["style"] = "" if st == "(지정 안 함)" else st
            self.w["extra"] = self.t_extra.get("1.0", "end-1c")
        elif s == 5:
            self.w["mode"] = self.mode_var.get()

    def _make(self) -> Template:
        w = self.w
        return make_template(w["name"], w["purpose"], w["user"], w["feats"], w["style"], w["extra"], w["mode"])

    def back(self):
        if self.step == 0:
            return
        self._read()
        self.step -= 1
        self.draw()

    def next(self):
        self._read()
        if self.step == 1 and not self.w["name"].strip():
            msgbox(self, "아티팩트 이름을 입력해 주세요.", "알림", "warn")
            return
        if self.step == 3 and not any(f.strip() for f in self.w["feats"]):
            msgbox(self, "기능을 하나 이상 적어 주세요.", "알림", "warn")
            return
        if self.step < LAST:
            self.step += 1
            self.draw()
            return
        self.template = self._make()
        self.close(self.template)

    def _on_return(self, e):
        if isinstance(e.widget, (tk.Text, tk.Entry)):
            return
        self.next()
