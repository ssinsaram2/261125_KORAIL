"""저장소 계층 — GUI는 SQL을 직접 쓰지 않고 이 클래스들만 쓴다."""
from __future__ import annotations

import json
import sqlite3
import uuid as _uuid
from dataclasses import dataclass

from . import auth
from .model import Block, CATEGORIES, Template, Variable, VAR_TYPES, TITLE_STYLES, content_fingerprint

LIB_NS = _uuid.UUID("6c1f0f0e-9d8a-4f39-9a59-2f0e2b9b7a98")
SAMPLE_NS = _uuid.UUID("0b9a6e43-2f6c-4d8e-a8a1-7c3e5d2f9b10")


def sample_uuid(owner_id: int | None, name: str) -> str:
    """코레일 예시의 고정 uuid. 사용자마다 따로 갖도록 주인 id를 섞는다(로그인 전 자료는 이름만)."""
    return str(_uuid.uuid5(SAMPLE_NS, name if owner_id is None else f"{owner_id}:{name}"))


class ReadOnlyError(Exception):
    """라이브러리 템플릿을 바꾸려 할 때."""


class AuthError(Exception):
    """회원가입·로그인 입력이 규칙에 맞지 않을 때(메시지는 사용자에게 그대로 보여 준다)."""


@dataclass
class TemplateSummary:
    id: int
    uuid: str
    name: str
    category: str
    description: str
    updated_at: str
    n_vars: int
    is_library: bool


@dataclass
class User:
    id: int
    username: str
    display_name: str

    @property
    def label(self) -> str:
        return self.display_name or self.username


def _clean_name(name: str) -> str:
    name = (name or "").strip()[:60]
    return name or "제목 없음"


def _block_type(t: str) -> str:
    t = (t or "").strip()
    return t if 1 <= len(t) <= 40 else "text"


class TemplateRepo:
    """owner_id 가 정해져 있으면 '내 템플릿' 조회·저장은 그 사용자 것만 다룬다."""

    def __init__(self, conn: sqlite3.Connection, owner_id: int | None = None):
        self.conn = conn
        self.owner_id = owner_id

    # ---- 분류 ----
    def categories(self) -> list[str]:
        return [r["name"] for r in self.conn.execute("SELECT name FROM categories ORDER BY sort_order, id")]

    def _category_id(self, name: str) -> int | None:
        r = self.conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
        if r is None:
            r = self.conn.execute("SELECT id FROM categories WHERE name = '기타'").fetchone()
        return r["id"] if r else None

    # ---- 조회 ----
    def list(self, library: bool = False, category: str | None = None, query: str = "") -> list[TemplateSummary]:
        sql = ("SELECT t.id, t.uuid, t.name, COALESCE(c.name,'기타') AS cat, t.description, t.updated_at, "
               "t.is_library, (SELECT COUNT(*) FROM variables v WHERE v.template_id = t.id) AS nv "
               "FROM templates t LEFT JOIN categories c ON c.id = t.category_id WHERE t.is_library = ?")
        args: list = [1 if library else 0]
        if not library:
            sql += " AND t.owner_id IS ?"
            args.append(self.owner_id)
        if category:
            sql += " AND c.name = ?"
            args.append(category)
        if query:
            sql += " AND (t.name || ' ' || t.description || ' ' || COALESCE(c.name,'')) LIKE ?"
            args.append(f"%{query}%")
        sql += " ORDER BY c.sort_order, t.id" if library else " ORDER BY t.updated_at DESC, t.id DESC"
        return [TemplateSummary(r["id"], r["uuid"], r["name"], r["cat"], r["description"], r["updated_at"],
                                r["nv"], bool(r["is_library"])) for r in self.conn.execute(sql, args)]

    def count(self, library: bool = False) -> int:
        if library:
            return self.conn.execute("SELECT COUNT(*) FROM templates WHERE is_library = 1").fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM templates WHERE is_library = 0 AND owner_id IS ?",
                                 (self.owner_id,)).fetchone()[0]

    def get(self, template_id: int) -> Template | None:
        r = self.conn.execute(
            "SELECT t.*, COALESCE(c.name,'기타') AS cat FROM templates t "
            "LEFT JOIN categories c ON c.id = t.category_id WHERE t.id = ?", (template_id,)).fetchone()
        if r is None:
            return None
        t = Template(id=r["id"], uuid=r["uuid"], name=r["name"], category=r["cat"],
                     title_style=r["title_style"], description=r["description"], is_library=bool(r["is_library"]),
                     intro=bool(r["intro"]))
        for v in self.conn.execute("SELECT * FROM variables WHERE template_id = ? ORDER BY position", (t.id,)):
            try:
                opts = json.loads(v["options_json"] or "[]")
            except ValueError:
                opts = []
            t.variables.append(Variable(v["name"], v["type"], ",".join(map(str, opts)), bool(v["required"])))
            t.values[v["name"]] = v["value"]
        for b in self.conn.execute("SELECT * FROM blocks WHERE template_id = ? ORDER BY position", (t.id,)):
            t.blocks.append(Block(b["type"], b["title"], b["content"], bool(b["enabled"])))
        return t

    def get_by_uuid(self, uuid: str) -> Template | None:
        """라이브러리이거나 지금 사용자의 템플릿일 때만 돌려준다."""
        r = self.conn.execute("SELECT id FROM templates WHERE uuid = ? AND (is_library = 1 OR owner_id IS ?)",
                              (uuid, self.owner_id)).fetchone()
        return self.get(r["id"]) if r else None

    def exists_uuid(self, uuid: str) -> bool:
        return self.conn.execute("SELECT 1 FROM templates WHERE uuid = ?", (uuid,)).fetchone() is not None

    def library_by_name(self, name: str) -> Template | None:
        r = self.conn.execute("SELECT id FROM templates WHERE is_library = 1 AND name = ?", (name,)).fetchone()
        return self.get(r["id"]) if r else None

    # ---- 저장 ----
    def _write(self, t: Template, is_library: bool) -> int:
        """트랜잭션 안에서 호출: 템플릿 UPSERT → 블록·변수 삭제 후 재삽입. 주인은 처음 넣을 때만 정한다."""
        row = self.conn.execute("SELECT id, is_library, owner_id FROM templates WHERE uuid = ?", (t.uuid,)).fetchone()
        if row is not None and row["is_library"] and not is_library:
            raise ReadOnlyError("라이브러리 템플릿은 바꿀 수 없어요. 다른 이름으로 저장하세요.")
        if row is not None and not is_library and row["owner_id"] != self.owner_id:
            raise ReadOnlyError("다른 사용자의 템플릿은 바꿀 수 없어요. 다른 이름으로 저장하세요.")
        ts = t.title_style if t.title_style in TITLE_STYLES else "bracket"
        self.conn.execute(
            "INSERT INTO templates(uuid, name, category_id, description, title_style, is_library, intro, owner_id) "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(uuid) DO UPDATE SET name = excluded.name, "
            "category_id = excluded.category_id, description = excluded.description, "
            "title_style = excluded.title_style, intro = excluded.intro",
            (t.uuid, _clean_name(t.name), self._category_id(t.category), t.description or "", ts,
             1 if is_library else 0, 1 if t.intro else 0, None if is_library else self.owner_id))
        tid = self.conn.execute("SELECT id FROM templates WHERE uuid = ?", (t.uuid,)).fetchone()["id"]
        self.conn.execute("DELETE FROM blocks WHERE template_id = ?", (tid,))
        self.conn.execute("DELETE FROM variables WHERE template_id = ?", (tid,))
        self.conn.executemany(
            "INSERT INTO blocks(template_id, position, type, title, content, enabled) VALUES (?,?,?,?,?,?)",
            [(tid, i, _block_type(b.type), b.title, b.content, 1 if b.enabled else 0)
             for i, b in enumerate(t.blocks)])
        self.conn.executemany(
            "INSERT INTO variables(template_id, position, name, type, options_json, required, value) "
            "VALUES (?,?,?,?,?,?,?)",
            [(tid, i, v.name, v.type if v.type in VAR_TYPES else "text",
              json.dumps(v.options(), ensure_ascii=False), 1 if v.required else 0, t.value(v.name))
             for i, v in enumerate(t.variables)])
        return tid

    def save(self, t: Template) -> int:
        if t.is_library:
            raise ReadOnlyError("라이브러리 템플릿은 바꿀 수 없어요. 다른 이름으로 저장하세요.")
        t.name = _clean_name(t.name)
        with self.conn:
            t.id = self._write(t, is_library=False)
        return t.id

    def delete(self, template_id: int) -> None:
        r = self.conn.execute("SELECT is_library, owner_id FROM templates WHERE id = ?", (template_id,)).fetchone()
        if r is not None and r["is_library"]:
            raise ReadOnlyError("라이브러리 템플릿은 지울 수 없어요.")
        if r is not None and r["owner_id"] != self.owner_id:
            raise ReadOnlyError("다른 사용자의 템플릿은 지울 수 없어요.")
        with self.conn:
            self.conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))

    # ---- 라이브러리 시드 ----
    def seed_library(self, data: dict, settings: "SettingsRepo") -> bool:
        """library.json 버전이 더 새로우면 라이브러리 행만 교체한다. 사용자 템플릿은 그대로."""
        version = int(data.get("version", 1))
        if settings.get_int("library_version", 0) >= version and self.count(library=True) > 0:
            return False
        with self.conn:
            self.conn.execute("DELETE FROM templates WHERE is_library = 1")
            for e in data.get("templates", []):
                t = Template.from_library_entry(e)
                t.uuid = str(_uuid.uuid5(LIB_NS, t.name))
                t.is_library = True
                self._write(t, is_library=True)
            self.conn.execute("INSERT INTO settings(key, value) VALUES ('library_version', ?) "
                              "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (str(version),))
        return True

    # ---- 예시(내 템플릿) 시드 ----
    def seed_samples(self, data: dict, settings: "SettingsRepo") -> list[str]:
        """samples.json 버전이 새로우면 예시를 지금 사용자의 '내 템플릿'으로 넣거나 새 내용으로 바꾼다.
        넣거나 바꾼 uuid 목록(파일 순서)을 돌려준다.

        - 없는 예시는 넣는다.
        - [1.3] 이미 있는 예시는 내용 지문이 예전에 배포한 그대로(previousFingerprints)일 때만 새 내용으로 바꾼다.
          사용자가 한 글자라도 고친 예시는 그대로 둔다.
        - 같은 버전이면 아무것도 하지 않으므로, 사용자가 지운 예시는 그 버전 안에서는 되살아나지 않는다.
        - samples_version 은 사용자별 설정이라 새 사용자는 자기 예시를 받는다.
        """
        version = int(data.get("version", 1))
        if settings.get_int("samples_version", 0) >= version:
            return []
        untouched = set(data.get("previousFingerprints") or [])
        changed = []
        with self.conn:
            # 목록(고친 때 최신순)에서 파일 순서대로 보이도록 뒤에서부터 넣는다
            for e in reversed(data.get("templates", [])):
                t = Template.from_library_entry(e)
                old = None
                for uid in (sample_uuid(self.owner_id, t.name), sample_uuid(None, t.name)):  # 로그인 전 예시도
                    r = self.conn.execute("SELECT id FROM templates WHERE uuid = ? AND owner_id IS ?",
                                          (uid, self.owner_id)).fetchone()
                    if r is not None:
                        old = self.get(r["id"])
                        break
                if old is None:
                    if self.exists_uuid(sample_uuid(self.owner_id, t.name)):
                        continue        # 다른 사람 것과 겹치는 이상한 경우는 건드리지 않음
                    t.uuid = sample_uuid(self.owner_id, t.name)
                elif content_fingerprint(old) in untouched:
                    t.uuid = old.uuid   # 손대지 않은 예전 예시 → 같은 자리에서 새 내용으로
                else:
                    continue            # 사용자가 고친 예시는 그대로
                self._write(t, is_library=False)
                changed.append(t.uuid)
        settings.set("samples_version", version)
        return list(reversed(changed))


class SettingsRepo:
    """키-값 설정. USER_KEYS 는 로그인한 사용자마다 따로 저장된다(user:<id>:<key>)."""

    DEFAULTS = {
        "boot_sound_enabled": "1",
        "boot_sound_path": "",
        "autosave_seconds": "2",
        "last_template_uuid": "",
        "last_username": "",
        "window_geometry": "",
        "window_zoomed": "0",
        "ai_enabled": "1",          # [1.5] 블록 AI 추천(Ollama)
        "ai_url": "http://127.0.0.1:11434",
        "ai_model": "gemma4",
    }
    USER_KEYS = frozenset({"last_template_uuid", "wizard_quick_features", "custom_block_types",
                           "samples_version", "first_run_done"})

    def __init__(self, conn: sqlite3.Connection, user_id: int | None = None):
        self.conn = conn
        self.user_id = user_id

    def _k(self, key: str) -> str:
        return f"user:{self.user_id}:{key}" if self.user_id is not None and key in self.USER_KEYS else key

    def get(self, key: str, default: str | None = None) -> str | None:
        r = self.conn.execute("SELECT value FROM settings WHERE key = ?", (self._k(key),)).fetchone()
        if r is not None:
            return r["value"]
        return self.DEFAULTS.get(key, default) if default is None else default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, str(default)))
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        v = self.get(key)
        return default if v is None else v == "1"

    def set(self, key: str, value) -> None:
        if isinstance(value, bool):
            value = "1" if value else "0"
        with self.conn:
            self.conn.execute("INSERT INTO settings(key, value) VALUES (?, ?) "
                              "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (self._k(key), str(value)))


class UserRepo:
    def __init__(self, conn: sqlite3.Connection, iterations: int = auth.PBKDF2_ITERATIONS):
        self.conn = conn
        self.iterations = iterations

    @staticmethod
    def _user(r) -> User:
        return User(r["id"], r["username"], r["display_name"])

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def exists(self, username: str) -> bool:
        return self.conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone() is not None

    def get(self, user_id: int) -> User | None:
        r = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._user(r) if r else None

    def create(self, username: str, password: str, display_name: str = "", confirm: str | None = None) -> User:
        username = (username or "").strip()
        display_name = " ".join((display_name or "").split())[:auth.DISPLAY_MAX]
        err = auth.username_error(username) or auth.password_error(password, confirm, username)
        if err:
            raise AuthError(err)
        if self.exists(username):
            raise AuthError("이미 쓰고 있는 아이디예요. 다른 아이디를 골라 주세요.")
        first = self.count() == 0
        h, salt, it = auth.hash_password(password, iterations=self.iterations)
        with self.conn:
            cur = self.conn.execute("INSERT INTO users(username, display_name, pw_hash, pw_salt, pw_iter) "
                                    "VALUES (?,?,?,?,?)", (username, display_name, h, salt, it))
        user = User(cur.lastrowid, username, display_name)
        if first:
            claim_legacy_data(self.conn, user.id)
        return user

    def authenticate(self, username: str, password: str) -> User | None:
        r = self.conn.execute("SELECT * FROM users WHERE username = ?", ((username or "").strip(),)).fetchone()
        if r is None:
            auth.hash_password(password or "", iterations=self.iterations)  # 없는 아이디도 같은 시간이 걸리게
            return None
        if not auth.verify_password(password or "", r["pw_hash"], r["pw_salt"], r["pw_iter"]):
            return None
        with self.conn:
            self.conn.execute("UPDATE users SET last_login = datetime('now','localtime') WHERE id = ?", (r["id"],))
        return self._user(r)

    def change_password(self, user_id: int, old: str, new: str, confirm: str) -> None:
        r = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if r is None or not auth.verify_password(old or "", r["pw_hash"], r["pw_salt"], r["pw_iter"]):
            raise AuthError("지금 비밀번호가 맞지 않아요.")
        err = auth.password_error(new, confirm, r["username"])
        if err:
            raise AuthError(err)
        h, salt, it = auth.hash_password(new, iterations=self.iterations)
        with self.conn:
            self.conn.execute("UPDATE users SET pw_hash = ?, pw_salt = ?, pw_iter = ? WHERE id = ?",
                              (h, salt, it, user_id))


def claim_legacy_data(conn: sqlite3.Connection, user_id: int) -> None:
    """로그인 기능이 생기기 전의 자료(주인 없는 내 템플릿, 사용자별 설정, 자동 저장)를 첫 가입자에게 넘긴다."""
    with conn:
        conn.execute("UPDATE templates SET owner_id = ? WHERE is_library = 0 AND owner_id IS NULL", (user_id,))
        for key in SettingsRepo.USER_KEYS:
            conn.execute("INSERT OR IGNORE INTO settings(key, value) SELECT ?, value FROM settings WHERE key = ?",
                         (f"user:{user_id}:{key}", key))
        conn.execute("UPDATE autosave SET user_id = ? WHERE user_id IS NULL", (user_id,))


class AutosaveRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save(self, payload: str, template_id: int | None, user_id: int | None = None) -> None:
        with self.conn:
            if template_id is not None and self.conn.execute(
                    "SELECT 1 FROM templates WHERE id = ?", (template_id,)).fetchone() is None:
                template_id = None
            self.conn.execute(
                "INSERT INTO autosave(id, payload, template_id, clean_exit, saved_at, user_id) "
                "VALUES (1, ?, ?, 0, datetime('now','localtime'), ?) ON CONFLICT(id) DO UPDATE SET "
                "payload = excluded.payload, template_id = excluded.template_id, clean_exit = 0, "
                "saved_at = excluded.saved_at, user_id = excluded.user_id", (payload, template_id, user_id))

    def load(self) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM autosave WHERE id = 1").fetchone()

    def set_clean_exit(self, clean: bool) -> None:
        with self.conn:
            self.conn.execute("UPDATE autosave SET clean_exit = ? WHERE id = 1", (1 if clean else 0,))


class CheckRunRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, template_id: int | None, score: int, findings: list[dict]) -> None:
        """findings 는 이미 마스킹된 값만 담고 있어야 한다(checks.check_security 가 보장)."""
        with self.conn:
            if template_id is not None and self.conn.execute(
                    "SELECT 1 FROM templates WHERE id = ?", (template_id,)).fetchone() is None:
                template_id = None
            self.conn.execute("INSERT INTO check_runs(template_id, score, findings_json) VALUES (?,?,?)",
                              (template_id, score, json.dumps(findings, ensure_ascii=False)))
            # 오래된 기록은 200건만 남긴다
            self.conn.execute("DELETE FROM check_runs WHERE id NOT IN "
                              "(SELECT id FROM check_runs ORDER BY id DESC LIMIT 200)")


__all__ = ["TemplateRepo", "SettingsRepo", "AutosaveRepo", "CheckRunRepo", "UserRepo", "User", "ReadOnlyError",
           "AuthError", "TemplateSummary", "CATEGORIES", "sample_uuid", "claim_legacy_data"]
