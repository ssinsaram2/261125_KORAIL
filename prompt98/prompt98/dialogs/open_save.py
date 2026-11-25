"""열기·다른 이름으로 저장·내보내기·가져오기."""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from .. import theme
from ..jsonio import ImportFormatError, export_payload, import_block_types, parse_import
from ..model import CATEGORIES, new_uuid
from ..repository import TemplateRepo
from ..theme import Fonts, Metrics
from .base import Dialog, ask_yes_no, msgbox, text_label


def save_as_dialog(parent, name: str, category: str) -> tuple[str, str] | None:
    d = Dialog(parent, "다른 이름으로 저장", min_width=400)
    text_label(d.body, "템플릿 이름").pack(fill="x")
    nv = tk.StringVar(value=name)
    e = tk.Entry(d.body, textvariable=nv)
    e.pack(fill="x", pady=(Metrics.px(2), Metrics.px(8)))
    e.select_range(0, "end")
    nv.trace_add("write", lambda *_: len(nv.get()) > 60 and nv.set(nv.get()[:60]))
    text_label(d.body, "분류").pack(fill="x")
    cb = ttk.Combobox(d.body, values=CATEGORIES, state="readonly")
    cb.set(category if category in CATEGORIES else "기타")
    cb.pack(fill="x", pady=(Metrics.px(2), Metrics.px(8)))
    text_label(d.body, "템플릿은 이 PC의 데이터베이스에 저장됩니다. 다른 PC로 옮길 땐 파일 > 내보내기를 쓰세요.",
               font=Fonts.small, fg=theme.HINT_FG, wraplength=Metrics.px(360)).pack(fill="x")
    out = {}

    def handler(v):
        if v is None:
            return True
        n = nv.get().strip()
        if not n:
            msgbox(d, "이름을 입력해 주세요.", "알림", "warn")
            return False
        out["r"] = (n, cb.get())
        return True
    d.add_buttons([("저장", True, True), ("취소", None)], handler)
    d.show(focus=e)
    return out.get("r")


class OpenDialog(Dialog):
    """저장된 사용자 템플릿 목록. 결과: 열 템플릿 id (또는 None)."""

    def __init__(self, parent, repo: TemplateRepo, current_id: int | None):
        super().__init__(parent, "열기 - 저장된 템플릿", min_width=620, resizable=True)
        self.repo, self.current_id = repo, current_id
        self.deleted_current = False
        top = tk.Frame(self.body)
        top.pack(fill="x", pady=(0, Metrics.px(6)))
        tk.Label(top, text="검색").pack(side="left")
        self.q = tk.StringVar()
        qe = tk.Entry(top, textvariable=self.q)
        qe.pack(side="left", fill="x", expand=True, padx=Metrics.px(6))
        self.q.trace_add("write", lambda *_: self.reload())
        frame = tk.Frame(self.body, bd=2, relief="sunken")
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("cat", "nv", "at"), height=12, selectmode="browse")
        self.tree.heading("#0", text="이름")
        self.tree.heading("cat", text="분류")
        self.tree.heading("nv", text="변수")
        self.tree.heading("at", text="고친 때")
        self.tree.column("#0", width=Metrics.px(260))
        self.tree.column("cat", width=Metrics.px(110))
        self.tree.column("nv", width=Metrics.px(50), anchor="e")
        self.tree.column("at", width=Metrics.px(150))
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._open())
        self.empty = tk.Label(self.body, text="저장된 템플릿이 없어요. 파일 > 저장으로 지금 작업을 보관해 보세요.",
                              fg=theme.SHADOW)
        tk.Label(self.body, text="이 PC의 데이터베이스에 저장된 템플릿입니다.", font=Fonts.small,
                 fg=theme.HINT_FG, anchor="w").pack(fill="x", pady=(Metrics.px(4), 0))
        self.add_buttons([("열기", "open", True), ("삭제", "delete"), ("닫기", None)], self._handle)
        self.reload()
        kids = self.tree.get_children()
        if kids:
            self.tree.selection_set(kids[0])
            self.tree.focus(kids[0])

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        items = self.repo.list(library=False, query=self.q.get().strip())
        for s in items:
            self.tree.insert("", "end", iid=str(s.id), text=s.name, values=(s.category, s.n_vars, s.updated_at[:16]))
        if items:
            self.empty.pack_forget()
        else:
            self.empty.pack(fill="x", pady=Metrics.px(6))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _open(self):
        if self._selected() is not None:
            self.close(("open", self._selected()))

    def _handle(self, v):
        if v is None:
            return True
        tid = self._selected()
        if tid is None:
            msgbox(self, "목록에서 템플릿을 골라 주세요.")
            return False
        if v == "open":
            self.result_value = ("open", tid)
            self.close(("open", tid))
            return False
        if v == "delete":
            name = self.tree.item(str(tid), "text")
            if ask_yes_no(self, f"\"{name}\" 템플릿을 삭제할까요? 되돌릴 수 없어요.", "삭제 확인", "warn",
                          yes="삭제", no="취소", default_yes=False):
                self.repo.delete(tid)
                if tid == self.current_id:
                    self.deleted_current = True
                self.reload()
            return False
        return True


def export_to_file(parent, repo: TemplateRepo, current) -> Path | None:
    path = filedialog.asksaveasfilename(parent=parent, title="내보내기 (JSON)", defaultextension=".json",
                                        initialfile="prompt98_templates.json",
                                        filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")])
    if not path:
        return None
    temps = [repo.get(s.id) for s in repo.list(library=False)]
    payload = export_payload([t for t in temps if t], current=current)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def import_from_file(parent, repo: TemplateRepo, register_types=None) -> tuple[int, int] | None:
    """(가져온 개수, 버린 항목 수). 취소면 None. 형식 오류는 안내 후 None.

    register_types(defs): 파일에 담긴 사용자 블록 종류를 먼저 등록하는 콜백(그래야 그 블록이 버려지지 않는다).
    """
    path = filedialog.askopenfilename(parent=parent, title="가져오기", filetypes=[
        ("JSON 파일", "*.json"), ("텍스트 파일", "*.txt"), ("모든 파일", "*.*")])
    if not path:
        return None
    try:
        raw = Path(path).read_text(encoding="utf-8-sig")
        obj = json.loads(raw)
        defs = import_block_types(obj)
        if defs and register_types:
            register_types(defs)
        items, dropped = parse_import(obj)
    except (ValueError, OSError, UnicodeDecodeError) as e:
        msg = str(e) if isinstance(e, ImportFormatError) else "JSON 형식이 올바르지 않아요."
        msgbox(parent, msg, "가져오기", "err")
        return None
    for t in items:
        if repo.exists_uuid(t.uuid):
            t.uuid = new_uuid()
        repo.save(t)
    return len(items), dropped


def save_text_file(parent, text: str, name: str) -> Path | None:
    safe = "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "프롬프트"
    path = filedialog.asksaveasfilename(parent=parent, title="프롬프트를 텍스트로 저장", defaultextension=".txt",
                                        initialfile=f"{safe}.txt",
                                        filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")])
    if not path:
        return None
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)
