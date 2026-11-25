"""개발용 GUI 스모크 테스트: 실제 창을 띄워 주요 기능을 자동으로 눌러 본다.

    python tools/smoke_gui.py [--shots 폴더]

--shots 를 주면 대화상자마다 PowerShell 로 화면을 찍는다(tools/shot.ps1).
데이터는 임시 폴더에 만들어지므로 실제 DB를 건드리지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prompt98 import db, platform_win, theme  # noqa: E402
from prompt98.paths import res  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name, cond, info=""):
    results.append((name, bool(cond), info))
    print(("PASS " if cond else "FAIL ") + name + (f" — {info}" if info and not cond else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default="")
    args = ap.parse_args()
    shots = Path(args.shots) if args.shots else None

    tmp = Path(tempfile.mkdtemp(prefix="p98smoke-"))
    os.chdir(tmp)
    platform_win.set_dpi_awareness()
    platform_win.register_font(res("fonts", "DungGeunMo.ttf"))
    conn = db.connect(tmp / "prompt98.db")
    db.migrate(conn)
    from prompt98.repository import SettingsRepo, TemplateRepo, UserRepo
    TemplateRepo(conn).seed_library(json.loads(res("library.json").read_text(encoding="utf-8")), SettingsRepo(conn))
    n_samples = len(json.loads(res("samples.json").read_text(encoding="utf-8"))["templates"])
    tester = UserRepo(conn, iterations=1_000).create("tester01", "Smoke2026", "시험 사용자")

    root = tk.Tk()
    theme.init_scaling(root)
    theme.init_fonts(root)
    theme.apply_theme(root)
    from prompt98 import app as appmod
    from prompt98.dialogs import base, open_save
    App = appmod.App
    a = App(root, conn, tmp, tmp / "app.log", user=tester)   # 로그인 화면 없이 시험 사용자로 시작
    for _ in range(50):
        root.update()
        if a.user is not None:
            break
        root.after(20)
    a.users.iterations = 1_000

    def WizardDialogOpen():
        from prompt98.dialogs.wizard import WizardDialog
        return WizardDialog(root, a.settings).show()

    def shot(title, name):
        if not shots:
            return
        shots.mkdir(parents=True, exist_ok=True)
        root.update()
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "tools" / "shot.ps1"), "-Out", str(shots / f"{name}.png"), "-Title", title],
                       capture_output=True)

    def with_dialog(open_fn, actions, title=None, name=None):
        """open_fn 은 모달 대화상자를 연다. 열린 뒤 actions(top) 를 실행한다."""
        def later():
            tops = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_viewable()]
            if not tops:
                root.after(100, later)
                return
            top = tops[-1]
            root.update()
            if title and name:
                shot(title, name)
            actions(top)
        root.after(300, later)
        return open_fn()

    # ---------- 0. 둥근모꼴이 실제로 쓰이는지 (고정폭이라 i 와 W 폭이 같다)
    import tkinter.font as tkfont
    check("둥근모꼴 적용", theme.Fonts.family in theme.DUNGGEUNMO_NAMES
          and theme.Fonts.body.measure("iiii") == theme.Fonts.body.measure("WWWW"), theme.Fonts.family)

    # ---------- 1. 첫 실행: 코레일 예시가 내 템플릿에 들어 있고 하나가 열려 있음
    check("로그인 사용자", a.user is not None and a.user.username == "tester01" and "시험 사용자" in a.user_name.cget("text")
          and "tester01" in a.user_id.cget("text") and a.user_box.winfo_ismapped())
    check("코레일 예시 시드(사용자별)", n_samples >= 5 and a.repo.count() == n_samples, str(a.repo.count()))
    check("첫 실행 코레일 예시 열림", a.t.name == "열차 지연 안내문" and a.t.id is not None, a.t.name)
    check("예시는 빈칸 없이 채워짐", a.st[2].cget("text") == "입력 완료", a.st[2].cget("text"))
    check("상태 표시줄 안내", "코레일 업무 예시" in a.st[0].cget("text"), a.st[0].cget("text"))
    shot("프롬프트 템플릿", "01_main")

    from prompt98.builder import INTRO_TEXT
    pv_text = lambda: a.preview_panel.text.get("1.0", "end-1c")  # noqa: E731
    check("미리보기 첫 문장", pv_text().startswith(INTRO_TEXT + "\n\n[역할]"), pv_text()[:40])
    a.preview_panel.intro_var.set(False)
    a.preview_panel._intro_changed()
    root.update()
    check("첫 문장 끄기", pv_text().startswith("[역할]") and a.t.intro is False, pv_text()[:20])
    a.undo()
    root.update()
    check("첫 문장 끄기 실행 취소", a.t.intro is True and a.preview_panel.intro_var.get() is True)

    def open_list(top):
        shot("열기 - 저장된 템플릿", "00_open_samples")
        top.cancel()
    with_dialog(lambda: a.open_dialog(), open_list)

    # 이후 단계는 라이브러리의 주간 업무 보고서로 진행
    a.load_template(a.repo.library_by_name("주간 업무 보고서").editable_copy(), "주간 업무 보고서", confirm=False)
    root.update()
    check("미리보기 하이라이트", "filled" in a.preview_panel.text.tag_names())

    # ---------- 2. 변수 추가·삽입
    ok = a.add_variable("연락처", "text")
    check("변수 추가", ok and a.t.var("연락처"))
    check("잘못된 이름 거부", not a.add_variable("띄어 쓰기", quiet=True))
    w0 = a.blocks_panel.widgets[0]
    w0.text.mark_set("insert", "end-1c")
    a.insert_var("연락처", w0.text)
    root.update()
    check("변수 삽입", "{{연락처}}" in a.t.blocks[0].content, a.t.blocks[0].content)
    a.form_panel.inputs["연락처"]._sv.set("010-1234-5678")
    root.update()
    a._refresh_preview()
    pv = a.preview_panel.text.get("1.0", "end")
    check("입력값이 미리보기에 반영", "010-1234-5678" in pv)
    check("상태 표시줄 보안 주의", "보안 주의" in a.st[3].cget("text"), a.st[3].cget("text"))

    # ---------- 1-9. [1.3] 변수 형식 '기간' + 달력
    import datetime as _dt
    a.add_variable("교육기간", "period")
    root.update()
    pe = a.form_panel.inputs["교육기간"]
    check("기간 변수 입력칸(시작~종료)", hasattr(pe, "_ev") and isinstance(pe._end, tk.Entry))
    pe._sv.set("2026-12-01")
    btn_1w = [w for w in pe.master.master.winfo_children()[-1].winfo_children()[-1].winfo_children()
              if isinstance(w, tk.Button) and w.cget("text") == "1주"][0]
    btn_1w.invoke()
    root.update()
    check("기간 1주 버튼", a.t.values["교육기간"] == "2026-12-01 ~ 2026-12-07", a.t.values["교육기간"])
    pe._ev.set("2026-11-20")
    root.update()
    info = pe.master.master.winfo_children()[-1].winfo_children()[0]
    check("거꾸로 된 기간 안내", "빨라요" in info.cget("text"), info.cget("text"))
    pe._ev.set("2026-12-05")
    root.update()
    check("기간 일수 표시", info.cget("text") == "5일간", info.cget("text"))
    a.form_panel.list.scroll_to_widget(pe)
    shot("프롬프트 템플릿 생성기 - 주간", "19_period")
    from prompt98.widgets.calendar import CalendarPopup
    cal_btn = [w for w in pe.master.winfo_children() if isinstance(w, tk.Button)][0]
    cal_btn.invoke()
    root.update()
    pops = [w for w in cal_btn.winfo_children() if isinstance(w, CalendarPopup)]
    check("달력 팝업", len(pops) == 1 and "2026년 12월" in pops[0].head.cget("text"))
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
        root.update()
        x, y = pops[0].winfo_rootx(), pops[0].winfo_rooty()
        fx = pe.master.master.winfo_rootx()
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "tools" / "shot.ps1"), "-Out", str(shots / "18_calendar.png"),
                        "-Title", "프롬프트 템플릿 생성기 - 주간"], capture_output=True)
    pops[0].pick(_dt.date(2026, 12, 3))
    root.update()
    check("달력에서 고르기", a.t.values["교육기간"] == "2026-12-03 ~ 2026-12-05", a.t.values["교육기간"])
    a.undo()
    root.update()
    check("달력 고르기 실행 취소", a.t.values.get("교육기간") == "2026-12-01 ~ 2026-12-05", a.t.values.get("교육기간"))
    for _ in range(5):
        if a.t.var("교육기간") is None:
            break
        a.undo()
    root.update()
    check("기간 변수 정리", a.t.var("교육기간") is None)

    # ---------- 2-1. 변수 칸(칩) 표시와 덩어리 편집
    from prompt98.widgets import varchips
    wt = a.blocks_panel.widgets[1].text          # 지시사항: "...{{부서명}}의 {{보고기간}}..."
    check("블록 속 변수는 파란 칸", bool(wt.tag_ranges(varchips.TAG_OK)) and bool(wt.tag_ranges(varchips.TAG_PAD_OK)))
    before = a.t.blocks[1].content
    s, e = next((sp[0], sp[1]) for sp in varchips.spans(before) if sp[4] == "부서명")
    wt.focus_force()
    root.update()
    wt.mark_set("insert", f"1.0+{e}c")
    wt.event_generate("<BackSpace>")
    root.update()
    check("BackSpace 로 칸 통째로 지우기", a.t.blocks[1].content == before[:s] + before[e:], a.t.blocks[1].content[:40])
    a.undo()
    root.update()
    wt = a.blocks_panel.widgets[1].text
    wt.focus_force()
    root.update()
    wt.mark_set("insert", f"1.0+{s + 3}c")       # 칸 한가운데
    wt.event_generate("<KeyPress>", keysym="a")
    root.update()
    check("칸 안에 입력하면 칸 뒤에 들어감", "{{부서명}}a" in a.t.blocks[1].content, a.t.blocks[1].content[:40])
    a.undo()
    a.add_variable("임시칸", "text")
    a.insert_var("없는이름_테스트", a.blocks_panel.widgets[1].text)
    root.update()
    check("등록 안 된 변수는 빨간 칸", bool(a.blocks_panel.widgets[1].text.tag_ranges(varchips.TAG_BAD)))
    a.undo()
    a.undo()
    root.update()

    # ---------- 2-2. [1.2] 블록 제목 입력칸 없음, 블록 종류 추가·삭제
    def entries_in(w):
        out = []
        for c in w.winfo_children():
            if isinstance(c, tk.Entry):
                out.append(c)
            out += entries_in(c)
        return out
    heads = [w.winfo_children()[0] for w in a.blocks_panel.widgets]       # 색 머리줄
    check("블록 머리줄에 제목 입력칸 없음", heads and all(not entries_in(h) for h in heads))
    from prompt98.dialogs.blocktype import BlockTypeDialog

    def type_actions(top):
        if not isinstance(top, BlockTypeDialog):
            return root.after(100, lambda: type_actions([w for w in root.winfo_children()
                                                         if isinstance(w, tk.Toplevel)][-1]))
        top.name.set("참고 자료")
        top.hint.insert(0, "참고할 문서·링크를 붙여 넣으세요.")
        root.update()
        shot("블록 종류 추가", "14_blocktype")
        top._default_btn.invoke()
    with_dialog(lambda: a.add_block_type(), type_actions)
    pal_names = [lab.cget("text") for lab in a.blocks_panel._pal_items]
    check("블록 종류 추가 → 팔레트", "참고 자료" in pal_names and pal_names[-1] == "+ 종류 추가", pal_names)
    key = next(k for k, v in appmod.BLOCK_TYPES.items() if v[0] == "참고 자료")
    a.blocks_panel.add_block(key)
    root.update()
    a._refresh_preview()
    check("새 종류 블록이 미리보기 제목에", "[참고 자료]" not in a.preview_panel.text.get("1.0", "end")  # 비어 있으면 빠짐
          and a.t.blocks[-1].type == key)
    a.blocks_panel.widgets[-1].text.insert("1.0", "사내 규정 링크")
    root.update()
    a._refresh_preview()
    check("새 종류 블록 내용 반영", "[참고 자료]\n사내 규정 링크" in a.preview_panel.text.get("1.0", "end"))
    import json as _json
    check("블록 종류는 사용자 설정에 저장", "참고 자료" in (a.settings.get("custom_block_types") or ""))
    shot("프롬프트 템플릿 생성기 - 열차", "15_custom_block")
    orig_yes = appmod.ask_yes_no
    appmod.ask_yes_no = lambda *a_, **k: True
    a.delete_block_type(key)
    appmod.ask_yes_no = orig_yes
    pal_names = [lab.cget("text") for lab in a.blocks_panel._pal_items]
    check("블록 종류 지우기", "참고 자료" not in pal_names and a.t.blocks[-1].type == key, pal_names)
    a.undo()      # 블록 추가 되돌리기
    a.undo()
    root.update()

    # ---------- 3. 블록 추가·이동·삭제와 실행 취소
    n = len(a.t.blocks)
    a.blocks_panel.add_block("example")
    check("블록 추가", len(a.t.blocks) == n + 1 and a.t.blocks[-1].type == "example")
    first_key = a.t.blocks[0].key
    a.blocks_panel.move_block(first_key, len(a.t.blocks))
    check("블록 이동(맨 아래로)", a.t.blocks[-1].type == "role")
    for _ in range(10):
        a.blocks_panel.add_block("text")
    check("블록 10개 추가", len(a.t.blocks) == n + 11)
    for _ in range(10):
        a.undo()
    check("실행 취소 10회", len(a.t.blocks) == n + 1, str(len(a.t.blocks)))
    a.redo()
    check("다시 실행", len(a.t.blocks) == n + 2)
    a.undo()
    a.undo()
    check("이동 취소", a.t.blocks[0].type == "role")

    # ---------- 4. 드래그 앤 드롭 (팔레트 → 블록 사이)
    root.update()
    bp = a.blocks_panel
    bp.list.canvas.yview_moveto(0)
    root.update()
    target = bp.widgets[1]
    y = target.winfo_rooty() + 3
    x = target.winfo_rootx() + 30
    pal = bp._pal_items[4]  # 출력 형식
    a.drag.press(SimpleNamespace(x_root=pal.winfo_rootx() + 5, y_root=pal.winfo_rooty() + 5, widget=pal), "pal",
                 "format", "+ 출력 형식")
    a.drag.motion(SimpleNamespace(x_root=x, y_root=y))
    a.drag.release(SimpleNamespace(x_root=x, y_root=y))
    check("팔레트 드래그로 2번째 위치에 삽입", a.t.blocks[1].type == "format", [b.type for b in a.t.blocks])
    # 블록 순서 드래그: 1번 블록을 맨 끝으로
    root.update()
    g = bp.widgets[0]
    last = bp.widgets[-1]
    key = g.b.key
    ey = last.winfo_rooty() + last.winfo_height() - 2
    a.drag.press(SimpleNamespace(x_root=g.winfo_rootx() + 5, y_root=g.winfo_rooty() + 5, widget=g), "block", key, "역할")
    a.drag.motion(SimpleNamespace(x_root=g.winfo_rootx() + 5, y_root=ey))
    a.drag.release(SimpleNamespace(x_root=g.winfo_rootx() + 5, y_root=ey))
    check("블록 드래그 순서 변경", a.t.blocks[-1].key == key)
    a.undo()
    a.undo()

    # ---------- 4-1. [1.5] 블록 AI 추천 (가짜 추천으로 — 진짜 모델 없이도 돈다)
    from prompt98.dialogs import suggest as sugmod
    real_suggest = sugmod.ai.suggest
    real_model = os.environ.get("SMOKE_REAL_AI") == "1"
    if not real_model:
        sugmod.ai.suggest = lambda cfg, t, b, cancel=None, progress=None: (
            progress and progress(42), ["- 첫째 추천", "- {{지연시간}}분 넘으면 사과 먼저"])[1]
    root.update()
    bi = next(i for i, w in enumerate(bp.widgets) if w.b.content.strip())
    bw = bp.widgets[bi]
    check("AI 추천 단추", bw.ai_btn is not None and bw.ai_btn.winfo_ismapped())
    before = bw.b.content

    def ai_actions(top):
        def wait():
            if top.loading:
                return root.after(200, wait)
            root.update()
            shot("AI 추천", "02b_ai_suggest")
            check("AI 추천 받음", len(top.items) >= 1, top.status.cget("text"))
            if top.items:
                top.pick.set(len(top.items) - 1)
                top.btn["뒤에 붙이기"].invoke()
            else:
                top.cancel()
        wait()
    with_dialog(lambda: a.suggest_block(bw.b), ai_actions)
    after = a.t.blocks[bi].content
    check("AI 추천 뒤에 붙이기", after.startswith(before.rstrip()) and len(after) > len(before), after[-40:])
    a.undo()
    check("AI 추천 실행 취소", a.t.blocks[bi].content == before)
    sugmod.ai.suggest = real_suggest
    a.settings.set("ai_enabled", False)
    bp.render()
    check("AI 추천 끄면 단추 숨김", all(w.ai_btn is None for w in bp.widgets))
    a.settings.set("ai_enabled", True)
    bp.render()

    # ---------- 5. 점검·마스킹
    from prompt98.checks import run_checks
    r = run_checks(a.t)
    check("보안 점검에서 휴대전화 발견", "phone" in r.maskable, r.maskable)

    def check_actions(top):
        top.switch("security")
        shot("구성 및 보안 점검", "03_check")
        top._mask_all()
        root.after(50, top.cancel)
    with_dialog(lambda: a.open_check(), check_actions)
    check("마스킹 적용", a.t.values["연락처"] == "010-****-5678", a.t.values["연락처"])
    a.undo()
    check("마스킹 실행 취소", a.t.values["연락처"] == "010-1234-5678")

    # ---------- 6. 다른 이름으로 저장 → 다시 열기
    open_save_orig = appmod.save_as_dialog
    appmod.save_as_dialog = lambda parent, name, cat: ("스모크 보고서", "문서 작성")
    a.save()
    appmod.save_as_dialog = open_save_orig
    check("저장(DB)", a.t.id is not None and a.repo.get(a.t.id).name == "스모크 보고서")
    check("저장 후 변경 없음", not a.dirty)
    saved_id = a.t.id
    a.new_template_noconfirm = True
    a.snap()
    a.t = appmod.Template.blank()
    a.saved_json = a.cur_json()
    a.render_all()

    def open_actions(top):
        shot("열기 - 저장된 템플릿", "04_open")
        top.tree.selection_set(str(saved_id))
        top._default_btn.invoke()
    with_dialog(lambda: a.open_dialog(), open_actions)
    check("열기", a.t.id == saved_id and a.t.var("연락처") is not None)

    # ---------- 7. 라이브러리
    def lib_actions(top):
        top.q.set("민원")
        root.update()
        shot("업무별 프롬프트 라이브러리", "05_library")
        top._default_btn.invoke()
    root.after(0, lambda: None)
    # 지금 작업이 저장돼 있으므로 확인 없이 바뀜
    with_dialog(lambda: a.library(), lib_actions)
    check("라이브러리에서 불러오기(사본)", a.t.name == "민원 답변 초안" and a.t.id is None, a.t.name)

    # ---------- 8. 마법사
    def wiz_actions(top):
        top.next()                                  # 1 이름
        top.e_name.insert(0, "팀 업무 현황판")
        top.next()                                  # 2 목적
        top.t_purpose.insert("1.0", "팀원 업무 공유")
        top.e_user.insert(0, "팀원 8명")
        top.next()                                  # 3 기능
        top.feat_entries[0].insert(0, "업무 등록")
        top._feat_quick("검색·필터")
        top.next()                                  # 4 화면
        top.next()                                  # 5 방식
        shot("아티팩트 마법사", "06_wizard")
        top.mode_var.set("제작해줘.")
        top._mode_changed()
        top.next()                                  # 6 완료
        top.next()                                  # 마침
    with_dialog(lambda: a.wizard(), wiz_actions)
    from prompt98.builder import build_prompt
    out = build_prompt(a.t)
    check("마법사 결과", out.startswith("아래의 지시에 따라 아티팩트를 제작해줘.") and "1) 업무 등록" in out
          and "2) 검색·필터" in out and "- 사용 대상: 팀원 8명" in out, out[:200])
    check("마법사 결과엔 첫 문장 없음", INTRO_TEXT not in out and not a.preview_panel.intro_var.get())
    shot("프롬프트 템플릿 생성기 - 팀", "12_wizard_result")

    # ---------- 9. 설정, 사용법, 복사
    def settings_actions(top):
        shot("설정", "07_settings")
        top.cancel()
    with_dialog(lambda: a.settings_dialog(), settings_actions)

    def help_actions(top):
        shot("사용법", "08_help")
        top.cancel()
    with_dialog(lambda: a.help(), help_actions)

    # ---------- 9-1. 아티팩트 마법사: 자주 쓰는 기능 추가·삭제·고치기
    from prompt98.dialogs.wizard import QUICK_FEATURES, QuickListDialog, load_quick_features
    seen = {}

    def quick_actions(wiz):
        wiz.w["name"] = "교육 출석부"
        wiz.step = 3                                  # 4단계(기능)로 바로
        wiz.draw()
        seen["before"] = list(wiz.quick_buttons)
        wiz._feat_quick(QUICK_FEATURES[0])           # 하나 넣으면 그 버튼은 흐려짐
        seen["used_disabled"] = str(wiz.quick_buttons[QUICK_FEATURES[0]].cget("state")) == "disabled"

        def edit(_=None):
            top = next((w for w in wiz.winfo_children() if isinstance(w, QuickListDialog)), None)
            if top is None:
                root.after(100, edit)
                return
            top.var.set("QR 코드로 출석 체크")
            top.add()                                 # 추가
            top.lb.selection_clear(0, "end")
            top.lb.selection_set(1)
            top.delete()                              # 2번째(관리자/일반…) 삭제
            top.lb.selection_set(0)
            top._selected()
            top.var.set("비밀번호로 접속 제한 (4자리 PIN)")
            top.update_selected()                     # 1번째 고치기
            top.lb.selection_clear(0, "end")
            top.lb.selection_set(len(top.items) - 1)
            top.move(-1)                              # 마지막 항목 한 칸 위로
            shot("자주 쓰는 기능 편집", "10_quick_edit")
            top._default_btn.invoke()
        root.after(300, edit)
        wiz.edit_quick()
        seen["after"] = list(wiz.quick_buttons)
        shot("아티팩트 마법사", "11_wizard_quick")
        wiz.cancel()
    with_dialog(lambda: WizardDialogOpen(), quick_actions)
    after = seen.get("after", [])
    check("이미 넣은 기능 버튼은 흐려짐", seen.get("used_disabled"))
    check("자주 쓰는 기능 추가", "QR 코드로 출석 체크" in after, after)
    check("자주 쓰는 기능 삭제", "관리자/일반 사용자 권한 구분" not in after)
    check("자주 쓰는 기능 고치기", after[:1] == ["비밀번호로 접속 제한 (4자리 PIN)"], after[:2])
    check("자주 쓰는 기능 순서 바꾸기", after[-2:] == ["QR 코드로 출석 체크", "인쇄용 화면"], after[-2:])
    check("자주 쓰는 기능 저장(다시 열어도 유지)", load_quick_features(a.settings) == after)

    a.t.values = {k: "값" for k in a.t.values}
    a.render_all()
    copied = {}

    def copy_done(top):
        copied["title"] = top.title()
        copied["text"] = " ".join(w.cget("text") for w in top.body.winfo_children()[0].winfo_children()
                                  if isinstance(w, tk.Label))
        shot("복사 완료", "13_copy_done")
        top._default_btn.invoke()                   # [확인]
    with_dialog(lambda: a.copy_flow(), copy_done)
    check("클립보드 복사", root.clipboard_get().startswith("아래의 지시에 따라"))
    check("복사 완료 대화상자", copied.get("title") == "복사 완료" and "복사했어요" in copied.get("text", ""),
          str(copied))

    # ---------- 10. JSON 내보내기 → 가져오기
    from prompt98.jsonio import export_payload, parse_import
    data = json.loads(json.dumps(export_payload([a.repo.get(saved_id)])))
    items, dropped = parse_import(data)
    check("JSON 왕복", items[0].name == "스모크 보고서" and dropped == 0)

    # ---------- 11. 좁은 창 → 탭 배치
    root.geometry("900x700")
    root.update()
    check("좁은 창 탭 배치", a.narrow)
    a._show_tab(2)
    root.update()
    shot("프롬프트 템플릿", "09_narrow")
    root.geometry("1400x860")
    root.update()
    check("넓은 창 3단 배치", not a.narrow)

    # ---------- 11-1. [1.2] 로그아웃 → 로그인 화면 → 틀린 비밀번호 → 로그인 → 회원가입
    a.saved_json = a.cur_json()
    a.logout()
    root.update()
    ls = a.login_screen
    check("로그아웃 → 로그인 화면", a.user is None and ls is not None and ls.winfo_ismapped())
    check("로그아웃하면 사용자 칸 비움", a.user_name.cget("text") == "" and a.user_id.cget("text") == "")
    check("로그인 화면에 진행 막대 없음", not ls.find_withtag("bar"))
    a.new_template()                                   # 로그인 화면에서는 단축키·동작이 막혀야 하지만 메서드는 직접 호출
    ls.uid.set("tester01")
    ls.pw.set("wrong999x")
    ls.login()
    check("틀린 비밀번호 거부", a.user is None and "맞지 않아요" in ls.err.cget("text"), ls.err.cget("text"))
    shot("프롬프트 템플릿", "16_login")
    ls.pw.set("Smoke2026")
    ls.login()
    root.update()
    check("다시 로그인", a.user is not None and a.user.username == "tester01")
    a.saved_json = a.cur_json()
    a.logout()
    root.update()
    from prompt98.dialogs.account import SignupDialog

    def signup_actions(top):
        if not isinstance(top, SignupDialog):
            return root.after(100, lambda: signup_actions([w for w in root.winfo_children()
                                                           if isinstance(w, tk.Toplevel)][-1]))
        top.uid.set("newbie01")
        top.name.set("새내기")
        top.pw.set("Hello2026")
        top.pw2.set("Hello2026")
        shot("회원가입", "17_signup")
        top._default_btn.invoke()
    with_dialog(lambda: a.login_screen.signup(), signup_actions)
    root.update()
    check("회원가입 후 바로 로그인", a.user is not None and a.user.username == "newbie01")
    check("새 사용자는 자기 예시만", a.repo.count() == n_samples
          and "스모크 보고서" not in [s.name for s in a.repo.list()])
    check("새 사용자는 사용자 블록 종류 없음", [d for d in appmod.custom_block_types()] == [])

    # ---------- 12. 자동 저장·정상 종료 표시
    a._autosave()
    row = a.autosave.load()
    check("자동 저장", row is not None and json.loads(row["payload"])["name"] == a.t.name)
    a.saved_json = a.cur_json()  # 종료 확인 대화상자 건너뛰기
    a.on_close()
    check("정상 종료 표시", a.autosave.load()["clean_exit"] == 1)
    conn.close()

    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
