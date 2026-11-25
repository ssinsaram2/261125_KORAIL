"""[1.5] 블록 내용 AI 추천 — 이 PC의 Ollama(gemma4)에게 블록에 쓸 내용을 물어본다.

표준 라이브러리(urllib)만 쓴다. 인터넷으로 나가지 않고 Ollama 주소(기본 127.0.0.1:11434)에만 연결한다.
tkinter 와 무관하게 만들어 백그라운드 스레드에서 부르고, 테스트에서는 가짜 서버로 시험한다.
"""
from __future__ import annotations

import json
import re
import socket
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass

from .model import BLOCK_TYPES, VAR_TYPES, Block, Template, block_name

DEFAULT_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma4"
MAX_SUGGESTIONS = 3
MAX_LEN = 600                 # 추천 하나의 최대 글자 수
CONTEXT_CHARS = 160           # 다른 블록 내용을 알려줄 때 블록마다 앞부분만
VAR_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

SCHEMA = {
    "type": "object",
    "properties": {"suggestions": {"type": "array", "items": {"type": "string"},
                                   "minItems": 1, "maxItems": MAX_SUGGESTIONS}},
    "required": ["suggestions"],
}

SYSTEM = (
    "당신은 한국철도공사(코레일) 직원이 생성형 AI에게 줄 프롬프트를 쓰도록 돕는 도우미입니다.\n"
    "프롬프트는 여러 '블록'(역할, 상황·배경, 지시사항, 조건·제약, 출력 형식, 예시 등)으로 나뉘어 있고, "
    "사용자는 지금 그중 한 블록을 쓰고 있습니다. 그 블록에 들어갈 내용을 서로 다른 방향으로 "
    f"{MAX_SUGGESTIONS}개 추천하세요.\n"
    "규칙:\n"
    "- 각 추천은 그 블록에 그대로 넣을 수 있는 완성된 한국어 문장이어야 합니다. 설명이나 머리말은 쓰지 마세요.\n"
    "- 블록 종류의 역할에 맞게 쓰세요. 조건·제약은 '- '로 시작하는 줄 목록이 좋습니다.\n"
    "- 각 추천은 300자 이내로 짧고 구체적으로 쓰세요.\n"
    "- 변수는 {{이름}} 형태로 쓰되, 아래 '등록된 변수'에 있는 이름만 쓰세요. 새 변수를 만들지 마세요.\n"
    "- 블록이 비어 있으면 블록 전체 내용을 추천하세요.\n"
    "- 블록에 이미 내용이 있으면, 지금 내용 뒤에 이어 붙일 '빠진 내용'만 추천하세요. 이미 있는 내용을 되풀이하지 마세요.\n"
    "- 개인정보·비밀번호 같은 민감한 정보를 예시로 넣지 마세요.\n"
    '- 답은 JSON 한 개만: {"suggestions": ["추천1", "추천2", "추천3"]}'
)


class AIError(Exception):
    """사용자에게 그대로 보여줄 수 있는 한국어 오류."""


@dataclass
class AIConfig:
    url: str = DEFAULT_URL
    model: str = DEFAULT_MODEL
    timeout: float = 180.0     # CPU 만으로 돌리면 몇십 초 걸릴 수 있다

    @classmethod
    def from_settings(cls, s) -> "AIConfig":
        return cls(url=(s.get("ai_url") or DEFAULT_URL).strip().rstrip("/") or DEFAULT_URL,
                   model=(s.get("ai_model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL)


# ---------------------------------------------------------------- 질문 만들기
def _clip(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def build_messages(t: Template, block: Block) -> list[dict]:
    name, _color, hint = BLOCK_TYPES.get(block.type, (block.title or "블록", "", ""))
    if block.type not in BLOCK_TYPES:
        name = block.title or block_name(block.type)
    lines = [f"템플릿 이름: {t.name or '제목 없음'}", f"분류: {t.category}"]
    if t.variables:
        lines.append("등록된 변수: " + ", ".join(
            f"{{{{{v.name}}}}}({VAR_TYPES.get(v.type, v.type)})" for v in t.variables))
    else:
        lines.append("등록된 변수: 없음 (변수를 쓰지 마세요)")
    others = [b for b in t.blocks if b is not block and b.content.strip()]
    if others:
        lines.append("다른 블록:")
        lines += [f"- [{b.title or block_name(b.type)}] {_clip(b.content, CONTEXT_CHARS)}" for b in others]
    lines.append(f"\n지금 쓰는 블록 종류: {name}")
    if hint:
        lines.append(f"이 블록의 입력 안내: {hint}")
    cur = block.content.strip()
    if cur:
        lines.append("지금 내용(이 뒤에 이어 붙일 내용을 추천):\n" + cur)
    else:
        lines.append("지금 내용: (비어 있음 — 블록 전체 내용을 추천)")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}]


# ---------------------------------------------------------------- 답 정리
def clean_suggestion(s: str, var_names: set[str]) -> str:
    """앞뒤 군더더기를 다듬고, 등록되지 않은 {{변수}} 는 괄호를 벗겨 보통 글자로 만든다."""
    s = (s or "").replace("\r\n", "\n").strip()
    s = re.sub(r"^(추천\s*\d+\s*[:.)]|\d+\s*[.)])\s*", "", s)
    s = s.strip().strip('"').strip("\n")

    def fix(m):
        n = m.group(1).strip()
        return "{{" + n + "}}" if n in var_names else n
    s = VAR_RE.sub(fix, s)
    s = "\n".join(re.sub(r"^(\s*)(?:[-•]\s*){2,}", r"\1- ", ln).rstrip() for ln in s.split("\n"))
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s[:MAX_LEN].rstrip()


def parse_suggestions(text: str, var_names: set[str], current: str = "") -> list[str]:
    raw: list = []
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            raw = data.get("suggestions") or [] if isinstance(data, dict) else []
        except json.JSONDecodeError:
            raw = []
    if not raw and text and not text.startswith("{"):
        raw = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: list[str] = []
    cur = (current or "").strip()
    for item in raw:
        if not isinstance(item, str):
            continue
        s = clean_suggestion(item, var_names)
        if s and s != cur and s not in out:
            out.append(s)
    return out[:MAX_SUGGESTIONS]


# ---------------------------------------------------------------- Ollama 연결
def _friendly(e: Exception, cfg: AIConfig) -> AIError:
    if isinstance(e, AIError):
        return e
    if isinstance(e, urllib.error.HTTPError):
        try:
            detail = json.loads(e.read().decode("utf-8", "replace")).get("error", "")
        except Exception:
            detail = ""
        if e.code == 404 or "not found" in detail:
            return AIError(f"'{cfg.model}' 모델을 찾지 못했어요.\n명령 프롬프트에서 ollama pull {cfg.model} 으로 받아 주세요.")
        return AIError(f"Ollama 가 오류를 돌려줬어요 ({e.code}). {detail}".strip())
    reason = getattr(e, "reason", e)
    if isinstance(reason, (socket.timeout, TimeoutError)) or isinstance(e, (socket.timeout, TimeoutError)):
        return AIError("추천을 기다리다 시간이 너무 오래 걸렸어요. 잠시 뒤 다시 해 보세요.")
    return AIError(f"Ollama 에 연결하지 못했어요 ({cfg.url}).\n"
                   "Ollama 가 켜져 있는지(작업 표시줄 알림 영역의 라마 아이콘) 확인해 주세요.")


def _model_matches(name: str, want: str) -> bool:
    return name == want or name == f"{want}:latest" or (":" in want and name == want)


def check(cfg: AIConfig, timeout: float = 5.0) -> str:
    """연결 확인. 정상이면 안내 문구를, 아니면 AIError."""
    try:
        with urllib.request.urlopen(cfg.url + "/api/tags", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise _friendly(e, cfg) from None
    names = [m.get("name", "") for m in data.get("models", [])]
    hit = next((n for n in names if _model_matches(n, cfg.model)), None)
    if not hit:
        raise AIError(f"Ollama 는 켜져 있지만 '{cfg.model}' 모델이 없어요.\n"
                      f"명령 프롬프트에서 ollama pull {cfg.model} 으로 받아 주세요."
                      + (f"\n(설치된 모델: {', '.join(names)})" if names else ""))
    return f"연결됨 — {cfg.url} 의 {hit} 모델을 쓸 수 있어요."


def suggest(cfg: AIConfig, t: Template, block: Block, cancel: threading.Event | None = None,
            progress=None) -> list[str]:
    """블록에 쓸 내용 추천 목록. 스트리밍으로 받아 cancel 이 켜지면 바로 멈춘다.

    progress(n) 은 지금까지 받은 글자 수로 불린다(백그라운드 스레드에서)."""
    body = {"model": cfg.model, "messages": build_messages(t, block), "stream": True, "think": False,
            "format": SCHEMA, "keep_alive": "15m",
            "options": {"temperature": 0.7, "num_predict": 700, "num_ctx": 4096}}
    req = urllib.request.Request(cfg.url + "/api/chat", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    parts: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout) as r:
            for line in r:
                if cancel is not None and cancel.is_set():
                    return []
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line.decode("utf-8"))
                if msg.get("error"):
                    raise AIError("Ollama 오류: " + str(msg["error"]))
                parts.append((msg.get("message") or {}).get("content", ""))
                if progress:
                    progress(sum(map(len, parts)))
                if msg.get("done"):
                    break
    except Exception as e:
        if cancel is not None and cancel.is_set():
            return []
        raise _friendly(e, cfg) from None
    out = parse_suggestions("".join(parts), {v.name for v in t.variables}, block.content)
    if not out:
        raise AIError("추천을 만들지 못했어요. [다시 추천]을 눌러 보세요.")
    return out
