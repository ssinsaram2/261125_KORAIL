# 261125_KORAIL — 프롬프트 98 (프롬프트 템플릿 생성기)

코레일 업무용 프롬프트를 블록·변수로 조립하는 Windows 98 감성의 도구입니다.

| 구성 | 위치 | 배포 |
|---|---|---|
| 웹판 | `프롬프트_템플릿_생성기.html` (한 파일) | Vercel 프로젝트 `261125_korail` — https://261125korail-beryl.vercel.app |
| 웹판 계정·자료 | `supabase/` (Auth + `user_data` 표, RLS) | Supabase 프로젝트 `261125_KORAIL` |
| 데스크톱판 | `prompt98/` (Python tkinter + sqlite3) | GitHub Release 의 `Prompt98.exe` |
| 작업지시서 | `작업지시서_프롬프트98_tkinter.md` | — |

## 웹판
- Vercel 이 `프롬프트_템플릿_생성기.html` 을 `index.html` 로 올립니다 (`vercel.json`).
- 로그인하면 템플릿·자주 쓰는 기능·블록 종류가 Supabase 에 저장돼 어느 PC에서나 이어서 쓸 수 있습니다.
- 인터넷이 없거나 Supabase 에 닿지 않으면 예전처럼 이 브라우저(localStorage)에만 저장하는 오프라인 모드로 동작합니다.

## 데스크톱판
```
cd prompt98
python -m venv .venv && .venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
.venv\Scripts\python -m PyInstaller prompt98.spec
```
자세한 내용은 `prompt98/README.md` 를 보세요.
