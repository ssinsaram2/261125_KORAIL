"""SQLite 연결 관리와 스키마 마이그레이션."""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

from .paths import res

log = logging.getLogger(__name__)

_conn: sqlite3.Connection | None = None


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_connection(path: str | Path | None = None) -> sqlite3.Connection:
    """앱 전체가 공유하는 연결 1개."""
    global _conn
    if _conn is None:
        if path is None:
            raise RuntimeError("DB가 아직 열리지 않았습니다")
        _conn = connect(path)
    return _conn


def close_connection() -> None:
    global _conn
    if _conn is not None:
        try:
            _conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        _conn.close()
        _conn = None


def migrations(schema_dir: Path | None = None) -> list[tuple[int, Path]]:
    schema_dir = schema_dir or res("schema")
    out = []
    for p in schema_dir.glob("*.sql"):
        m = re.match(r"^(\d+)_", p.name)
        if m:
            out.append((int(m.group(1)), p))
    return sorted(out)


def user_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection, schema_dir: Path | None = None) -> int:
    """user_version 보다 높은 버전의 SQL 파일을 순서대로 적용한다. 다시 불러도 안전."""
    current = user_version(conn)
    for ver, path in migrations(schema_dir):
        if ver <= current:
            continue
        sql = path.read_text(encoding="utf-8")
        log.info("스키마 %s 적용 (%s)", ver, path.name)
        try:
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {ver};\nCOMMIT;")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        current = ver
    conn.execute("PRAGMA foreign_keys = ON")
    return current
