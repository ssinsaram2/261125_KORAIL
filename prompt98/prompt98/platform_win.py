"""Windows 연동: DPI 인식, 글꼴 등록, MCI 소리 재생, 단일 실행 뮤텍스.

모두 ctypes 로 호출하며, Windows 가 아니거나 실패해도 앱은 계속 돈다.
"""
from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from pathlib import Path

log = logging.getLogger(__name__)
IS_WIN = sys.platform == "win32"
ERROR_ALREADY_EXISTS = 183


def set_dpi_awareness() -> bool:
    if not IS_WIN:
        return False
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
        return True
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return True
        except Exception:
            log.warning("DPI 인식 설정 실패", exc_info=True)
            return False


def register_font(path: Path) -> bool:
    """설치하지 않고 이 프로세스에서만 쓰는 글꼴로 등록한다. Tk() 생성 전에 호출."""
    if not IS_WIN or not Path(path).exists():
        return False
    try:
        FR_PRIVATE = 0x10
        n = ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0)
        return n > 0
    except Exception:
        log.warning("글꼴 등록 실패: %s", path, exc_info=True)
        return False


def message_box(text: str, title: str = "프롬프트 98", icon: int = 0x40) -> None:
    """Tk 가 뜨기 전에 쓰는 기본 메시지 상자 (0x40 정보, 0x30 경고, 0x10 오류)."""
    if IS_WIN:
        try:
            ctypes.windll.user32.MessageBoxW(None, text, title, icon)
            return
        except Exception:
            pass
    print(f"{title}: {text}", file=sys.stderr)


class SingleInstance:
    """이름 있는 뮤텍스로 같은 DB를 쓰는 두 번째 실행을 막는다."""

    def __init__(self, name: str):
        self.handle = None
        self.already_running = False
        if not IS_WIN:
            return
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = wintypes.HANDLE
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self._k32 = k32
        self.handle = k32.CreateMutexW(None, False, name)
        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS

    def release(self) -> None:
        if self.handle:
            self._k32.CloseHandle(wintypes.HANDLE(self.handle))
            self.handle = None


class Sound:
    """winmm MCI 로 mp3·wav 를 비동기 재생한다. 실패하면 wav 만 winsound 로 재생."""

    ALIAS = "p98boot"

    def __init__(self):
        self._open = False
        try:
            self._mci = ctypes.windll.winmm.mciSendStringW if IS_WIN else None
            if self._mci:
                self._mci.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HANDLE]
                self._mci.restype = wintypes.DWORD
        except Exception:
            self._mci = None

    def _send(self, cmd: str) -> int:
        return self._mci(cmd, None, 0, None) if self._mci else -1

    def stop(self) -> None:
        if self._open:
            self._send(f"stop {self.ALIAS}")
            self._send(f"close {self.ALIAS}")
            self._open = False
        try:
            import winsound
            winsound.PlaySound(None, 0)
        except Exception:
            pass

    def play(self, path: Path | str) -> bool:
        path = Path(path)
        if not path.exists():
            log.warning("소리 파일 없음: %s", path)
            return False
        self.stop()
        kind = "waveaudio" if path.suffix.lower() == ".wav" else "mpegvideo"
        if self._mci:
            err = self._send(f'open "{path}" type {kind} alias {self.ALIAS}')
            if err != 0 and kind == "waveaudio":
                err = self._send(f'open "{path}" type mpegvideo alias {self.ALIAS}')
            if err == 0:
                self._open = True
                if self._send(f"play {self.ALIAS}") == 0:
                    return True
                self.stop()
            log.warning("MCI 재생 실패(%s): %s", err, path)
        if path.suffix.lower() == ".wav":
            try:
                import winsound
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                return True
            except Exception:
                log.warning("winsound 재생 실패", exc_info=True)
        return False


def work_area() -> tuple[int, int, int, int] | None:
    """작업 표시줄을 뺀 화면 영역 (left, top, right, bottom). 실패하면 None."""
    if not IS_WIN:
        return None
    try:
        r = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):  # SPI_GETWORKAREA
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return None


def open_folder(path: Path) -> None:
    try:
        import os
        os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception:
        log.warning("폴더 열기 실패: %s", path, exc_info=True)
