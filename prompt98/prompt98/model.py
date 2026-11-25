"""도메인 객체: Template, Block, Variable 과 상수."""
from __future__ import annotations

import itertools
import re
import uuid as _uuid
from dataclasses import dataclass, field

# 블록 종류: type -> (이름, 색, 입력 안내)
BLOCK_TYPES: dict[str, tuple[str, str, str]] = {
    "role": ("역할", "#000080", "예) 당신은 10년 차 행정 전문가입니다."),
    "context": ("상황·배경", "#008080", "예) 다음 주 신규 직원 30명 대상 교육이 있습니다."),
    "task": ("지시사항", "#800000", "예) 아래 내용을 바탕으로 안내문을 작성해 주세요."),
    "constraint": ("조건·제약", "#6b6b00", "예) - 300자 이내\n- 입력에 없는 사실은 지어내지 말 것"),
    "format": ("출력 형식", "#800080", "예) 제목 / 본문 / 요약 3줄 순서의 표"),
    "example": ("예시", "#006000", "원하는 결과물의 예시를 붙여 넣으세요."),
    "text": ("자유 텍스트", "#505050", "자유롭게 작성하세요."),
}

VAR_TYPES: dict[str, str] = {
    "text": "한 줄 글",
    "area": "여러 줄 글",
    "number": "숫자",
    "date": "날짜",
    "period": "기간",          # [1.3] 시작일 ~ 종료일 ("2026-12-01 ~ 2026-12-05")
    "select": "선택 목록",
}

CATEGORIES = ["문서 작성", "데이터·분석", "고객·민원", "교육·홍보", "기획·아이디어",
              "아티팩트 제작", "안전·현장", "요약·번역", "기타"]

TITLE_STYLES: dict[str, str] = {
    "none": "붙이지 않음",
    "bracket": "[제목]",
    "md": "## 제목",
    "num": "1. 제목",
}

VNAME_RE = re.compile(r"^[가-힣A-Za-z0-9_]{1,20}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PERIOD_SEP = " ~ "


def valid_date(s: str) -> bool:
    import datetime as _dt
    if not DATE_RE.match(s or ""):
        return False
    try:
        _dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def split_period(value: str) -> tuple[str, str]:
    """'2026-12-01 ~ 2026-12-05' → ('2026-12-01', '2026-12-05'). 형식이 다르면 가능한 만큼만."""
    m = re.match(r"^\s*(\d{4}-\d{2}-\d{2})?\s*~?\s*(\d{4}-\d{2}-\d{2})?\s*$", value or "")
    if not m:
        return "", ""
    return m.group(1) or "", m.group(2) or ""


def join_period(start: str, end: str) -> str:
    """둘 다 비면 '' (= 아직 입력 안 함), 하나만 있으면 그 날짜만."""
    start, end = (start or "").strip(), (end or "").strip()
    if start and end:
        return f"{start}{PERIOD_SEP}{end}"
    return start or end


def period_days(start: str, end: str) -> int | None:
    """시작일부터 종료일까지 며칠인지(양 끝 포함). 날짜가 잘못됐거나 거꾸로면 None."""
    import datetime as _dt
    if not (valid_date(start) and valid_date(end)):
        return None
    d = (_dt.date.fromisoformat(end) - _dt.date.fromisoformat(start)).days + 1
    return d if d >= 1 else None

_keys = itertools.count(1)


def new_key() -> str:
    """화면에서 블록·변수를 구분하는 실행 중 전용 키."""
    return f"k{next(_keys)}"


def new_uuid() -> str:
    return str(_uuid.uuid4())


def valid_var_name(name: str) -> bool:
    return bool(VNAME_RE.match(name or ""))


def block_name(btype: str) -> str:
    return BLOCK_TYPES.get(btype, BLOCK_TYPES["text"])[0]


def block_color(btype: str) -> str:
    return BLOCK_TYPES.get(btype, BLOCK_TYPES["text"])[1]


# ---------------------------------------------------------------- [1.2] 사용자가 만든 블록 종류
BUILTIN_BLOCK_TYPES = frozenset(BLOCK_TYPES)
CUSTOM_PREFIX = "c_"
BLOCK_NAME_MAX = 10
# 팔레트에서 고를 수 있는 Win98 풍 색 (흰 글자가 잘 보이는 어두운 색)
CUSTOM_COLORS = ["#005f87", "#874f00", "#5f2f87", "#00704a", "#8a2050", "#3c3c8c", "#6f5c00", "#2f6f6f"]


def is_custom_type(btype: str) -> bool:
    return btype not in BUILTIN_BLOCK_TYPES


def custom_block_types() -> list[dict]:
    """지금 등록된 사용자 블록 종류: [{key, name, color, hint}]"""
    return [{"key": k, "name": v[0], "color": v[1], "hint": v[2]}
            for k, v in BLOCK_TYPES.items() if k not in BUILTIN_BLOCK_TYPES]


def clean_block_type_def(d) -> dict | None:
    """설정·JSON에서 읽은 블록 종류 정의를 검사한다(잘못되면 None)."""
    if not isinstance(d, dict):
        return None
    key = str(d.get("key", "")).strip()
    name = " ".join(str(d.get("name", "")).split())[:BLOCK_NAME_MAX]
    color = str(d.get("color", ""))
    if not (key.startswith(CUSTOM_PREFIX) and 3 <= len(key) <= 40) or not name:
        return None
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        color = CUSTOM_COLORS[0]
    return {"key": key, "name": name, "color": color, "hint": str(d.get("hint", ""))[:60]}


def set_custom_block_types(defs) -> list[dict]:
    """사용자 블록 종류 목록을 통째로 바꿔 등록한다(기본 7종은 그대로). 정리된 목록을 돌려준다."""
    for k in [k for k in BLOCK_TYPES if k not in BUILTIN_BLOCK_TYPES]:
        del BLOCK_TYPES[k]
    out, names = [], {v[0] for v in BLOCK_TYPES.values()}
    for d in defs or []:
        d = clean_block_type_def(d)
        if d and d["key"] not in BLOCK_TYPES and d["name"] not in names:
            BLOCK_TYPES[d["key"]] = (d["name"], d["color"], d["hint"] or f"{d['name']} 내용을 적어 주세요.")
            names.add(d["name"])
            out.append(d)
    return out


def content_fingerprint(t: "Template") -> str:
    """[1.3] 템플릿 내용의 지문(이름·분류·변수·값·블록). 예시를 사용자가 고쳤는지 알아볼 때 쓴다."""
    import hashlib
    import json as _json
    d = {"name": t.name, "cat": t.category, "ts": t.title_style, "intro": t.intro,
         "vars": [[v.name, v.type, v.opts, v.required] for v in t.variables],
         "values": {v.name: str(t.values.get(v.name, "")) for v in t.variables},
         "blocks": [[b.type, b.title, b.content, b.enabled] for b in t.blocks]}
    return hashlib.sha1(_json.dumps(d, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def new_custom_type_key() -> str:
    return CUSTOM_PREFIX + _uuid.uuid4().hex[:8]


@dataclass
class Variable:
    name: str
    type: str = "text"
    opts: str = ""          # select 형식의 선택지 (쉼표 구분, 웹판과 동일)
    required: bool = True
    key: str = field(default_factory=new_key, compare=False, repr=False)

    def options(self) -> list[str]:
        return [o.strip() for o in self.opts.split(",") if o.strip()]

    def to_dict(self) -> dict:
        return {"name": self.name, "type": self.type, "opts": self.opts, "req": self.required}

    @classmethod
    def from_dict(cls, d: dict) -> "Variable":
        return cls(name=d["name"], type=d.get("type", "text"), opts=d.get("opts", "") or "",
                   required=bool(d.get("req", True)))


@dataclass
class Block:
    type: str
    title: str = ""
    content: str = ""
    enabled: bool = True
    key: str = field(default_factory=new_key, compare=False, repr=False)

    def __post_init__(self):
        if not self.title:
            self.title = block_name(self.type)

    def to_dict(self) -> dict:
        return {"type": self.type, "title": self.title, "content": self.content, "on": self.enabled}

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        return cls(type=d["type"], title=d.get("title") or "", content=d.get("content", ""),
                   enabled=d.get("on", True) is not False)


@dataclass
class Template:
    name: str = "제목 없음"
    category: str = "기타"
    title_style: str = "bracket"
    description: str = ""
    variables: list[Variable] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    values: dict[str, str] = field(default_factory=dict)
    uuid: str = field(default_factory=new_uuid)
    id: int | None = None
    is_library: bool = False
    intro: bool = True      # 맨 앞에 INTRO_TEXT 첫 문장을 붙일지 (아티팩트 마법사 결과는 False)

    # ---- 조회 도우미 ----
    def var(self, name: str) -> Variable | None:
        return next((v for v in self.variables if v.name == name), None)

    def value(self, name: str) -> str:
        return str(self.values.get(name, "") or "")

    # ---- 직렬화 (자동 저장·실행 취소용, id/uuid 포함) ----
    def to_dict(self) -> dict:
        return {
            "id": self.id, "uuid": self.uuid, "is_library": self.is_library,
            "name": self.name, "cat": self.category, "ts": self.title_style, "desc": self.description,
            "intro": self.intro,
            "vars": [v.to_dict() for v in self.variables],
            "values": dict(self.values),
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Template":
        return cls(
            id=d.get("id"), uuid=d.get("uuid") or new_uuid(), is_library=bool(d.get("is_library")),
            name=d.get("name", "제목 없음"), category=d.get("cat", "기타"),
            title_style=d.get("ts", "bracket"), description=d.get("desc", ""),
            intro=d.get("intro", True) is not False,
            variables=[Variable.from_dict(v) for v in d.get("vars", [])],
            values={k: str(v if v is not None else "") for k, v in (d.get("values") or {}).items()},
            blocks=[Block.from_dict(b) for b in d.get("blocks", [])],
        )

    def clone(self) -> "Template":
        return Template.from_dict(self.to_dict())

    def editable_copy(self) -> "Template":
        """라이브러리 템플릿을 편집용 사용자 템플릿으로 복사(새 uuid, 저장 전)."""
        t = self.clone()
        t.id = None
        t.uuid = new_uuid()
        t.is_library = False
        return t

    @classmethod
    def blank(cls) -> "Template":
        return cls(blocks=[Block("role"), Block("task"), Block("format")])

    @classmethod
    def from_library_entry(cls, e: dict) -> "Template":
        """resources/library.json 의 항목 하나를 Template 으로."""
        vars_, values = [], {}
        for v in e.get("vars", []):
            vars_.append(Variable(name=v["name"], type=v.get("type", "text"), opts=v.get("opts", "") or "",
                                  required=bool(v.get("req", True))))
            values[v["name"]] = v.get("value", "") or ""
        blocks = [Block(type=b["type"], title=b.get("title") or "", content=b.get("content", ""))
                  for b in e.get("blocks", [])]
        return cls(name=e["name"], category=e.get("cat", "기타"), title_style=e.get("ts", "bracket"),
                   description=e.get("desc", ""), variables=vars_, blocks=blocks, values=values,
                   intro=e.get("intro", True) is not False)
