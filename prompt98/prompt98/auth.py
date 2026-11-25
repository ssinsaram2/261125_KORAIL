"""[1.2] 로그인용 비밀번호 해시와 입력 규칙 (GUI와 무관한 순수 함수).

비밀번호는 저장하지 않는다. PBKDF2-HMAC-SHA256(솔트 16바이트, 반복 200,000회)의 결과만 저장하고,
확인할 때는 같은 계산을 해서 hmac.compare_digest 로 비교한다.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets

PBKDF2_ITERATIONS = 200_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{4,20}$")
PASSWORD_MIN, PASSWORD_MAX = 8, 64
DISPLAY_MAX = 20


def hash_password(password: str, salt_hex: str | None = None,
                  iterations: int = PBKDF2_ITERATIONS) -> tuple[str, str, int]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return digest.hex(), salt.hex(), iterations


def verify_password(password: str, pw_hash: str, salt_hex: str, iterations: int) -> bool:
    calc, _, _ = hash_password(password, salt_hex, iterations)
    return hmac.compare_digest(calc, pw_hash)


def username_error(username: str) -> str | None:
    if not USERNAME_RE.match(username or ""):
        return "아이디는 영문·숫자·밑줄(_)로 4~20자, 띄어쓰기 없이 지어 주세요."
    return None


def password_error(password: str, confirm: str | None = None, username: str = "") -> str | None:
    if not (PASSWORD_MIN <= len(password or "") <= PASSWORD_MAX):
        return f"비밀번호는 {PASSWORD_MIN}~{PASSWORD_MAX}자로 정해 주세요."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "비밀번호에는 영문과 숫자를 함께 넣어 주세요."
    if username and username.lower() in password.lower():
        return "비밀번호에 아이디를 그대로 넣지 마세요."
    if confirm is not None and password != confirm:
        return "비밀번호 확인이 일치하지 않아요."
    return None


class LoginThrottle:
    """같은 아이디로 5번 연속 틀리면 30초 동안 로그인을 막는다(프로그램이 켜져 있는 동안)."""

    def __init__(self, limit: int = 5, lock_seconds: float = 30.0, clock=None):
        import time
        self.limit, self.lock_seconds = limit, lock_seconds
        self.clock = clock or time.monotonic
        self._fails: dict[str, int] = {}
        self._until: dict[str, float] = {}

    def wait_seconds(self, username: str) -> int:
        left = self._until.get(username.lower(), 0) - self.clock()
        return max(0, int(left + 0.999))

    def failed(self, username: str) -> None:
        k = username.lower()
        self._fails[k] = self._fails.get(k, 0) + 1
        if self._fails[k] >= self.limit:
            self._until[k] = self.clock() + self.lock_seconds
            self._fails[k] = 0

    def succeeded(self, username: str) -> None:
        self._fails.pop(username.lower(), None)
        self._until.pop(username.lower(), None)
