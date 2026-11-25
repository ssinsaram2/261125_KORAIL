# 프롬프트 98 — 프롬프트 템플릿 생성기 (Windows 데스크톱판)

웹 아티팩트 「프롬프트 템플릿 생성기」를 **Python tkinter + sqlite3**로 옮긴 Windows 98 스타일 데스크톱 앱입니다.
실행에는 표준 라이브러리만 씁니다(인터넷·`pip install` 불필요).

## 아이콘으로 실행

`my_second_winapp` 폴더에 실행 아이콘 두 개가 있습니다.

| 파일 | 용도 |
|---|---|
| `프롬프트 98.lnk` | 이 PC용 바로 가기. 서명된 `pythonw.exe`로 `python -m prompt98`를 실행합니다(콘솔 창 없음). 스마트 앱 컨트롤이 켜져 있어도 열립니다. 바탕화면 등으로 복사해도 됩니다. |
| `Prompt98.exe` | 배포용 단일 실행 파일(`dist\Prompt98.exe` 사본). 파이썬이 없는 PC에서도 실행됩니다. 코드 서명 전에는 스마트 앱 컨트롤이 켜진 PC에서 차단됩니다. |

## 빠른 시작

```powershell
cd prompt98
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt   # 테스트·빌드용 (실행만 할 땐 필요 없음)

python -m prompt98             # 일반 실행 (%APPDATA%\Prompt98 사용)
python -m prompt98 --portable  # 현재 폴더에 DB 생성
python -m prompt98 --reset-db  # 개발용: DB 백업 후 새로 만들기
```

## 로그인

- 시작하면 로그인 화면이 뜹니다. 처음이면 **[회원가입]**으로 계정을 만드세요(아이디 영문·숫자 4~20자, 비밀번호 8자 이상 영문+숫자).
- 계정은 이 PC의 DB에만 저장되고, 비밀번호는 원문 대신 PBKDF2 해시로만 저장됩니다. **잊으면 되찾을 수 없습니다.**
- 내 템플릿·자동 저장·자주 쓰는 기능·직접 만든 블록 종류는 계정마다 따로 보관됩니다. 로그인 기능 전에 만든 자료는 처음 가입한 계정으로 넘어갑니다.
- 로그아웃: 파일 > 로그아웃 또는 시작 메뉴. 비밀번호 바꾸기: 도움말 메뉴.

## 테스트

```powershell
pytest                          # 단위 테스트 (builder · checks · repository · JSON)
python tools\smoke_gui.py       # 실제 창을 띄워 주요 기능을 자동으로 눌러 보는 스모크 테스트
```

## exe 빌드

```powershell
pytest
pyinstaller prompt98.spec --clean --noconfirm      # → dist\Prompt98.exe (단일 파일)
$env:PROMPT98_ONEDIR = "1"; pyinstaller prompt98.spec --clean --noconfirm   # → dist\Prompt98\ (폴더판, 백신 오탐 대비)
```

- exe 옆에 빈 파일 `portable.flag`를 두면 DB·로그를 exe 폴더에 저장합니다(USB 휴대용).
- **코드 서명이 없는 exe는 Windows 스마트 앱 컨트롤(Smart App Control)이 켜진 PC에서 차단됩니다.**
  배포 전 코드 서명 인증서로 서명(`signtool sign /fd SHA256 /tr <타임스탬프 URL> /td SHA256 dist\Prompt98.exe`)하는 것을 권장합니다.

## 데이터 위치

| 항목 | 경로 |
|---|---|
| DB | `%APPDATA%\Prompt98\prompt98.db` (휴대용: exe 폴더) |
| 로그 | `%APPDATA%\Prompt98\logs\app.log` (1MB × 3개 순환) |

## 구조

```
prompt98/            앱 코드
  __main__.py        진입점: 로그 → DPI → 글꼴 → 중복 실행 확인 → DB → App
  app.py             메인 창(메뉴·툴바·3단·상태 표시줄·작업 표시줄·단축키·자동 저장)
  model.py           Template · Block · Variable
  builder.py         프롬프트 조립·변수 치환 (순수 함수)
  checks.py          구성·보안 점검 (순수 함수)
  history.py         실행 취소/다시 실행 (100단계)
  db.py              연결·마이그레이션 (PRAGMA user_version)
  repository.py      TemplateRepo · SettingsRepo · AutosaveRepo · CheckRunRepo
  jsonio.py          웹판 호환 JSON 내보내기·가져오기
  platform_win.py    글꼴 등록 · DPI · MCI 소리 · 단일 실행 뮤텍스
  widgets/           Win98 위젯, 아이콘, ①변수 ②블록 ③양식 ④미리보기
  dialogs/           열기·저장, 라이브러리, 점검, 마법사, 설정
resources/           글꼴, 효과음, 아이콘, library.json, schema/001_init.sql
tests/               pytest
tools/               make_assets.py(효과음·아이콘 생성), smoke_gui.py, shot.ps1
```

## 단축키

Ctrl+N 새로 만들기 · Ctrl+O 열기 · Ctrl+S 저장 · Ctrl+Shift+S 다른 이름으로 저장 · Ctrl+Z 실행 취소 ·
Ctrl+Y 다시 실행 · Ctrl+Enter 복사 · F1 사용법 · Alt+F/E/T/H 메뉴

## 저작권

- 글꼴: 둥근모꼴(DungGeunMo) — 퍼블릭 도메인
- 기본 부팅음·아이콘: `tools/make_assets.py`로 이 프로젝트에서 직접 합성·그린 자체 제작물
- Microsoft Windows 시작음 등 타사 저작물은 포함하지 않습니다. 사용자가 고른 소리 파일은 경로만 기억합니다.
