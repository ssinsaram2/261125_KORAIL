"""[1.3] 웹판 html 의 라이브러리(LIB)·예시(SAMPLES) 자료를 데스크톱판 JSON 과 똑같이 맞춘다.

    python tools/sync_web.py [html 경로]

- resources/library.json  → const LIB=[ … ];
- resources/samples.json  → const SAMPLES_V=…,SAMPLES=[ … ];  const PREV_WEB_FP=[ … ];
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "resources"
HTML = ROOT.parent / "프롬프트_템플릿_생성기.html"


def web_entry(t: dict, desc: str | None = None) -> str:
    e = {"cat": t["cat"], "name": t["name"], "desc": desc if desc is not None else t.get("desc", ""),
         "ts": t.get("ts", "bracket")}
    if t.get("intro") is False:
        e["intro"] = False
    e["vars"] = [[v["name"], v["type"], v.get("value", "") or ""] + ([v["opts"]] if v.get("opts") else [])
                 for v in t["vars"]]
    e["blocks"] = [[b["type"], b["content"]] + ([b["title"]] if b.get("title") else []) for b in t["blocks"]]
    return json.dumps(e, ensure_ascii=False)


def main(path: Path):
    lib = json.loads((RES / "library.json").read_text(encoding="utf-8"))
    sam = json.loads((RES / "samples.json").read_text(encoding="utf-8"))
    s = path.read_text(encoding="utf-8")

    lib_js = "const LIB=[\n" + ",\n".join(web_entry(t) for t in lib["templates"]) + "\n];"
    s, n1 = re.subn(r"const LIB=\[\n.*?\n\];", lambda m: lib_js, s, count=1, flags=re.S)

    sam_js = (f"const SAMPLES_V={sam['version']},SAMPLES=[\n"
              + ",\n".join(web_entry(t, "코레일 업무 예시") for t in sam["templates"]) + "\n];\n"
              + "const PREV_WEB_FP=" + json.dumps(sam.get("previousWebFingerprints") or []) + ";")
    s, n2 = re.subn(r"const SAMPLES_V=\d+,SAMPLES=\[\n.*?\n\];(\nconst PREV_WEB_FP=\[.*?\];)?",
                    lambda m: sam_js, s, count=1, flags=re.S)
    if n1 != 1 or n2 != 1:
        raise SystemExit(f"자리를 찾지 못했어요 (LIB {n1}, SAMPLES {n2})")
    path.write_text(s, encoding="utf-8", newline="")
    print(f"웹판 동기화: 라이브러리 {len(lib['templates'])}종(v{lib['version']}), "
          f"예시 {len(sam['templates'])}종(v{sam['version']})")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HTML)
