"""[1.3] 예시 지문 만들기: resources/samples_history/v*.json(예전에 배포한 예시)의 지문을 samples.json 에 적는다.

    python tools/build_samples.py

- previousFingerprints     : 데스크톱판(model.content_fingerprint, SHA-1)
- previousWebFingerprints  : 웹판(webFingerprint, FNV-1a 32bit — 아래 web_fp 와 html 의 JS 가 같은 계산)
업그레이드 때 이 목록에 있는 지문과 같은(=사용자가 손대지 않은) 예시만 새 내용으로 바꾼다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prompt98.model import Template, block_name, content_fingerprint  # noqa: E402

RES = ROOT / "resources"


def web_canonical(entry: dict) -> str:
    """웹판 fromLib() 로 넣은 예시 데이터의 정규 문자열 (html 의 webCanonical 과 같아야 함)."""
    vars_ = [[v["name"], v["type"], v.get("opts", "") or "", True] for v in entry["vars"]]
    values = [[v["name"], v.get("value", "") or ""] for v in entry["vars"]]
    blocks = [[b["type"], b.get("title") or block_name(b["type"]), b["content"], True] for b in entry["blocks"]]
    arr = [entry["name"], entry["cat"], entry.get("ts", "bracket"), entry.get("intro", True) is not False,
           vars_, values, blocks]
    return json.dumps(arr, ensure_ascii=False, separators=(",", ":"))


def web_fp(s: str) -> str:
    """FNV-1a 32bit over UTF-16 code units (JS charCodeAt 와 같음)."""
    h = 0x811C9DC5
    data = s.encode("utf-16-le")
    for i in range(0, len(data), 2):
        h ^= data[i] | (data[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def main():
    desk, web = [], []
    for p in sorted((RES / "samples_history").glob("v*.json")):
        for e in json.loads(p.read_text(encoding="utf-8"))["templates"]:
            desk.append(content_fingerprint(Template.from_library_entry(e)))
            web.append(web_fp(web_canonical(e)))
    path = RES / "samples.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["previousFingerprints"] = sorted(set(desk))
    data["previousWebFingerprints"] = sorted(set(web))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"samples v{data['version']}: {len(data['templates'])}종, 예전 지문 {len(desk)}개")


if __name__ == "__main__":
    main()
