"""python -m prompt98 진입점 (PyInstaller 도 이 파일에서 시작).

순서: 데이터 폴더·로그 → DPI → 글꼴 등록 → 중복 실행 확인 → DB·마이그레이션·시드 → Tk → App
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import shutil
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# PyInstaller 가 이 파일을 스크립트로 실행할 때도 동작하도록 절대 import 를 쓴다.
from prompt98 import APP_NAME, __version__, db, platform_win
from prompt98.paths import data_dir, res


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="prompt98", description="프롬프트 템플릿 생성기 (Windows 98 스타일)")
    p.add_argument("--portable", action="store_true", help="현재 폴더에 DB를 만든다")
    p.add_argument("--reset-db", action="store_true", help="개발용: DB를 백업한 뒤 새로 만든다")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p.parse_args(argv)


def setup_logging(ddir: Path) -> Path:
    path = ddir / "logs" / "app.log"
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if sys.stderr is not None:
        root.addHandler(logging.StreamHandler(sys.stderr))
    return path


def reset_db(db_path: Path) -> None:
    if not db_path.exists():
        return
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_name(f"{db_path.stem}.backup-{stamp}.db")
    shutil.copy2(db_path, backup)
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()
    logging.info("DB 백업 후 초기화: %s", backup)


def main(argv=None) -> int:
    args = parse_args(argv)
    ddir = data_dir(portable=args.portable)
    log_path = setup_logging(ddir)
    log = logging.getLogger("prompt98")
    log.info("시작 %s %s (데이터: %s)", APP_NAME, __version__, ddir)

    platform_win.set_dpi_awareness()
    font_ok = platform_win.register_font(res("fonts", "DungGeunMo.ttf"))
    log.info("둥근모꼴 등록: %s", font_ok)

    db_path = ddir / "prompt98.db"
    mutex_name = "Local\\Prompt98_" + hashlib.sha1(str(db_path).lower().encode()).hexdigest()[:16]
    instance = platform_win.SingleInstance(mutex_name)
    if instance.already_running:
        platform_win.message_box("프롬프트 템플릿 생성기가 이미 실행 중이에요.\n작업 표시줄에서 열려 있는 창을 확인하세요.",
                                 "프롬프트 98", 0x30)
        return 1

    if args.reset_db:
        reset_db(db_path)

    import tkinter as tk
    from prompt98 import theme
    from prompt98.app import App
    from prompt98.repository import SettingsRepo, TemplateRepo

    conn = db.get_connection(db_path)
    try:
        db.migrate(conn)
        settings = SettingsRepo(conn)
        lib = json.loads(res("library.json").read_text(encoding="utf-8"))
        if TemplateRepo(conn).seed_library(lib, settings):
            log.info("라이브러리 시드 버전 %s 적용", lib.get("version"))
        # [1.2] 코레일 예시는 사용자마다 로그인할 때 넣는다(App.login_as)

        root = tk.Tk()
        root.withdraw()
        theme.init_scaling(root)
        log.info("사용 글꼴: %s", theme.init_fonts(root))
        theme.apply_theme(root)
        App(root, conn, ddir, log_path)   # 로그인 화면부터 시작

        root.deiconify()
        root.mainloop()
    except Exception:
        log.exception("치명적 오류")
        platform_win.message_box(f"프로그램을 시작하지 못했어요.\n로그: {log_path}", "프롬프트 98", 0x10)
        return 2
    finally:
        db.close_connection()
        instance.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
