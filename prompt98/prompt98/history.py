"""실행 취소 / 다시 실행 스택 (스냅샷 = 템플릿 JSON 문자열)."""
from __future__ import annotations


class History:
    def __init__(self, limit: int = 100):
        self.limit = limit
        self._undo: list[str] = []
        self._redo: list[str] = []

    def push(self, snapshot: str) -> None:
        if self._undo and self._undo[-1] == snapshot:
            return
        self._undo.append(snapshot)
        if len(self._undo) > self.limit:
            del self._undo[0]
        self._redo.clear()

    def undo(self, current: str) -> str | None:
        while self._undo:
            prev = self._undo.pop()
            if prev != current:
                self._redo.append(current)
                return prev
        return None

    def redo(self, current: str) -> str | None:
        if not self._redo:
            return None
        nxt = self._redo.pop()
        self._undo.append(current)
        return nxt

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def __len__(self) -> int:
        return len(self._undo)
