"""웹판과 호환되는 JSON 내보내기·가져오기 (순수 함수)."""
from __future__ import annotations

import time
import uuid as _uuid

from .model import (BLOCK_TYPES, CATEGORIES, TITLE_STYLES, VAR_TYPES, Block, Template, Variable,
                    clean_block_type_def, custom_block_types, valid_var_name)


class ImportFormatError(ValueError):
    pass


def template_to_web(t: Template) -> dict:
    return {
        "name": t.name, "cat": t.category, "ts": t.title_style,
        "intro": t.intro,   # 데스크톱판 전용 키(웹판은 무시). 없으면 켜짐으로 가져온다
        "vars": [{"name": v.name, "type": v.type, "opts": v.opts, "req": v.required} for v in t.variables],
        "values": {k: str(v) for k, v in t.values.items()},
        "blocks": [{"type": b.type, "title": b.title, "content": b.content, "on": b.enabled} for b in t.blocks],
    }


def export_payload(templates: list[Template], current: Template | None = None) -> dict:
    now = int(time.time() * 1000)
    out: dict = {"app": "prompt98", "version": 1}
    if current is not None:
        out["current"] = template_to_web(current)
    out["saved"] = [{"id": t.uuid, "name": t.name, "cat": t.category, "at": now, "data": template_to_web(t)}
                    for t in templates]
    # [1.2] 사용자가 만든 블록 종류 중 실제로 쓰인 것의 정의를 함께 담는다(데스크톱판 전용 키, 웹판은 무시)
    used = {b.type for t in templates + ([current] if current else []) for b in t.blocks}
    defs = [d for d in custom_block_types() if d["key"] in used]
    if defs:
        out["blockTypes"] = defs
    return out


def import_block_types(obj) -> list[dict]:
    """가져오기 JSON에 담긴 사용자 블록 종류 정의(없으면 빈 목록). 템플릿을 읽기 전에 등록해야 그 블록이 살아남는다."""
    if not isinstance(obj, dict):
        return []
    return [d for d in (clean_block_type_def(x) for x in obj.get("blockTypes") or []) if d]


def _looks_like_template(d) -> bool:
    return isinstance(d, dict) and isinstance(d.get("blocks"), list) and isinstance(d.get("vars"), list)


def _valid_uuid(s) -> str | None:
    try:
        return str(_uuid.UUID(str(s)))
    except (ValueError, TypeError, AttributeError):
        return None


def web_to_template(d: dict, uid: str | None = None) -> tuple[Template, int]:
    """웹판 템플릿 데이터 → Template. 알 수 없는 블록·변수는 버리고 버린 개수를 돌려준다."""
    dropped = 0
    blocks = []
    for b in d.get("blocks", []):
        if isinstance(b, dict) and b.get("type") in BLOCK_TYPES and isinstance(b.get("content"), str):
            blocks.append(Block(b["type"], str(b.get("title") or "")[:30], b["content"], b.get("on") is not False))
        else:
            dropped += 1
    variables, seen = [], set()
    for v in d.get("vars", []):
        if (isinstance(v, dict) and valid_var_name(str(v.get("name", ""))) and v.get("type", "text") in VAR_TYPES
                and v["name"] not in seen):
            seen.add(v["name"])
            variables.append(Variable(v["name"], v.get("type", "text"), str(v.get("opts") or ""), bool(v.get("req", True))))
        else:
            dropped += 1
    raw_values = d.get("values") if isinstance(d.get("values"), dict) else {}
    values = {str(k): "" if val is None else str(val) for k, val in raw_values.items()}
    for v in variables:
        values.setdefault(v.name, "")
    t = Template(
        name=(str(d.get("name") or "가져온 템플릿").strip() or "가져온 템플릿")[:60],
        category=d.get("cat") if d.get("cat") in CATEGORIES else "기타",
        title_style=d.get("ts") if d.get("ts") in TITLE_STYLES else "bracket",
        intro=d.get("intro", True) is not False,
        variables=variables, blocks=blocks, values=values,
    )
    if uid:
        t.uuid = uid
    return t, dropped


def parse_import(obj) -> tuple[list[Template], int]:
    """내보내기 JSON(웹판·데스크톱판) → (템플릿 목록, 버린 항목 수)."""
    items: list[tuple[dict, str | None]] = []
    if isinstance(obj, dict) and obj.get("app") == "prompt98":
        for s in obj.get("saved") or []:
            if isinstance(s, dict) and _looks_like_template(s.get("data")):
                items.append((s["data"], _valid_uuid(s.get("id"))))
    elif isinstance(obj, list):
        items = [(t, None) for t in obj if _looks_like_template(t)]
    elif _looks_like_template(obj):
        items = [(obj, None)]
    if not items:
        raise ImportFormatError("가져올 수 있는 템플릿을 찾지 못했어요.")
    out, dropped = [], 0
    for data, uid in items:
        t, n = web_to_template(data, uid)
        out.append(t)
        dropped += n
    return out, dropped
