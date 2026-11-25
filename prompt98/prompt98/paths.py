"""리소스·데이터 경로를 한곳에서 계산한다.

PyInstaller로 묶이면 리소스가 임시 폴더(sys._MEIPASS)로 풀리므로 res()로만 접근한다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME

PORTABLE_FLAG = "portable.flag"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def res(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base.joinpath("resources", *parts)


def exe_dir() -> Path:
    """exe(또는 개발 중이면 프로젝트 루트)가 있는 폴더."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir(portable: bool = False) -> Path:
    """DB·로그를 둘 폴더를 만들고 돌려준다.

    - --portable 옵션이면 현재 작업 폴더
    - exe 옆에 portable.flag가 있으면 exe 폴더 (USB 휴대용)
    - 그 밖에는 %APPDATA%\\Prompt98
    """
    if portable:
        d = Path.cwd()
    elif (exe_dir() / PORTABLE_FLAG).exists():
        d = exe_dir()
    else:
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        d = Path(appdata) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    (d / "logs").mkdir(exist_ok=True)
    return d
