# 작업 지시서 — 프롬프트 템플릿 생성기 Windows 데스크톱판 (tkinter + sqlite3)

> 대상: 개발 담당자(또는 코드를 작성할 AI)
> 원본: 웹 아티팩트 「프롬프트 템플릿 생성기」 (Windows 98 스타일, 둥근모꼴)
> 목표: 같은 기능을 **Python tkinter**로 다시 만들고, 데이터는 **sqlite3**에 저장하며, 최종적으로 **Windows용 단일 exe**로 배포한다.
> 진행 순서: ① 로컬에서 `python`으로 실행되는 상태를 먼저 완성 → ② exe 빌드
>
> **개정 1.1 (2026-11-25)** — 1차 구현 후 사용자 검토에서 나온 요구를 반영했다. 바뀐 곳은 본문에 **[1.1]**로 표시하고, 맨 끝 「변경 이력」에 모았다.
> **개정 1.2 (2026-11-25)** — 로그인·회원가입, 사용자별 자료, 블록 종류 추가, 블록 제목 입력칸 삭제. 본문에 **[1.2]**로 표시(2-6, 2-7, 5-2-2).
> **개정 1.3 (2026-11-25)** — 변수 형식 「기간」과 달력 고르기, 툴바 오른쪽 사용자 정보 칸. 본문에 **[1.3]**로 표시.
> 웹판(`.html`)에도 1.2 내용을 같은 화면·규칙으로 반영했다. 차이는 부록 E 참고.
> 구현 위치: `my_second_winapp\prompt98\` (원본 웹판은 같은 폴더의 `프롬프트_템플릿_생성기.html`)

---

## 0. 한눈에 보기

| 항목 | 결정 |
|---|---|
| 언어 / 버전 | Python 3.12 (64bit) |
| GUI | `tkinter` + `tkinter.ttk` (표준 라이브러리만 사용) |
| DB | `sqlite3` (표준 라이브러리), 파일 1개, 스키마 버전 **4** **[1.3]** |
| 로그인 **[1.2]** | 이 PC의 DB에 계정 저장. 비밀번호는 PBKDF2-HMAC-SHA256(솔트 16바이트, 200,000회) 해시만 저장. 내 템플릿·설정은 사용자별 |
| 외부 패키지 | **실행에는 없음.** 빌드용 `pyinstaller`, 테스트용 `pytest`만 사용 |
| 글꼴 | 둥근모꼴 `DungGeunMo.ttf` (퍼블릭 도메인) — 앱에 포함해 배포. **한국어 Windows에서는 글꼴 이름이 "둥근모꼴"로 잡힌다 [1.1]** |
| 소리 | Windows 내장 `winmm` MCI를 `ctypes`로 호출해 mp3/wav 재생 (추가 패키지 없음) |
| 배포 | PyInstaller `--onefile --windowed` → `Prompt98.exe`. **코드 서명 권장 [1.1]** |
| 실행 아이콘 | 프로젝트 폴더에 `프롬프트 98.lnk` 바로 가기(서명된 `pythonw.exe -m prompt98`) + `Prompt98.exe` 사본 **[1.1]** |
| 데이터 위치 | 기본 `%APPDATA%\Prompt98\prompt98.db` / exe 옆에 `portable.flag`가 있으면 exe 폴더 |

---

## 1. 구현할 기능 (웹판과 동일, 10가지)

| # | 기능 | 데스크톱 구현 요점 |
|---|---|---|
| 1 | 기본 프롬프트 생성 | 블록(역할·상황·지시사항·조건·출력 형식·예시·자유 텍스트)을 이어 붙여 최종 프롬프트 생성. 블록 제목 표시 방식 4종: 없음 / `[제목]` / `## 제목` / `1. 제목`. **[1.1] 맨 앞에 첫 문장 "아래의 지시사항에 따라 결과물을 생성해줘."를 기본으로 붙인다(템플릿마다 켜고 끔, 6-1 참고)** |
| 2 | 사용자 정의 변수 추가·삭제 | 이름 규칙 `^[가-힣A-Za-z0-9_]{1,20}$`, 형식 6종(한 줄 글·여러 줄 글·숫자·날짜·**기간 [1.3]**·선택 목록), 필수 여부, 이름 바꾸기 시 블록 속 `{{이름}}` 일괄 치환. **[1.1] 화면에는 `{{ }}`를 보이지 않고 이름만 색 칸으로 표시(2-5 참고)** |
| 3 | 변수 기반 입력 양식 자동 생성 | 변수 목록이 바뀔 때마다 오른쪽 양식 영역을 다시 그림. 형식별 위젯: `Entry` / `Text` / `Spinbox` / 날짜 `Entry`(YYYY-MM-DD 검증, [오늘] 버튼) / `ttk.Combobox(readonly)`. **[1.3] 날짜 칸에 달력 버튼(팝업 달력: ◀▶ 달 이동, 오늘·지우기). 기간 = 시작일 [달력] ~ 종료일 [달력] + "N일간" 표시 + [1일][1주][2주][한 달] 빠른 버튼(시작일, 없으면 오늘부터), 종료일이 시작일보다 빠르면 빨간 안내. 값은 `YYYY-MM-DD ~ YYYY-MM-DD` 한 줄로 저장(`model.split_period`/`join_period`/`period_days`). 달력·빠른 버튼으로 고른 값은 실행 취소 한 단계. 스키마 4판(`004_period.sql`)에서 `variables.type` CHECK에 `period` 추가** |
| 4 | 실시간 미리보기·복사 | `Text` 위젯 + 태그 하이라이트(채운 값 = 노란 배경, 빈 값 = 빨간 칸). 입력 후 150ms 디바운스로 갱신. 복사 전 미입력·민감 정보 확인 대화상자. **[1.1] 복사가 끝나면 상태 표시줄 문구가 아니라 「복사 완료」 대화상자(글자 수 표시, [확인])를 띄운다** |
| 5 | **아티팩트 마법사** **[1.1] 이름 변경** | 7단계 위자드(시작 → 이름 → 목적·사용 대상 → 기능 목록 → 화면 스타일·추가 요청 → 요청 방식 → 완료). 결과는 변수가 들어간 템플릿으로 편집기에 열림. **[1.1] 툴바·메뉴·시작 메뉴·창 제목 모두 "아티팩트 마법사"로 통일. 기능 단계의 "자주 쓰는 기능 바로 넣기" 목록을 사용자가 추가·고치기·삭제·순서 변경할 수 있음(부록 C). 결과 템플릿은 첫 문장을 붙이지 않음** |
| 6 | 템플릿 저장·불러오기 | sqlite3 저장. 열기 / 저장 / 다른 이름으로 저장 / 삭제 / JSON 내보내기·가져오기 / 프롬프트를 .txt로 저장. **[1.1] 첫 실행 때 코레일 업무 예시 7종을 "내 템플릿"으로 넣음(부록 D)** |
| 7 | 블록 드래그 앤 드롭 편집 | 블록 헤더의 점무늬 손잡이로 순서 변경, 팔레트에서 끌어 원하는 위치에 삽입. ▲▼ 버튼도 함께 제공. **[1.2] 블록 머리줄의 제목 입력칸은 없앤다(블록 종류 이름만 표시, 이름 변경 불가). 대신 팔레트 끝 [+ 종류 추가]로 새 블록 종류를 만든다(2-7)** |
| 8 | 업무별 프롬프트 라이브러리 | 9개 분류, 기본 템플릿 17종을 첫 실행 때 DB에 넣음. 검색·분류 필터·미리보기 |
| 9 | 구성·보안 점검 | 구성 점검(지시사항 누락, 미등록·미사용 변수, 필수값 누락 등) + 보안 점검(주민번호·전화·카드·계좌·이메일·비밀번호·API 키·내부 IP·대외비). 점수, 원클릭 수정, 마스킹 |
| 10 | Windows 98 스타일 GUI | 회색 `#c0c0c0` 면, 남색 제목줄, 입체 테두리(raised/sunken), 청록 바탕, 둥근모꼴 |

웹판의 부가 요소도 함께 옮긴다: 부팅 화면(**[1.2] 진행 막대를 없애고 로그인 화면으로 바꿈**), 시작 메뉴, 상태 표시줄, 실행 취소, 단축키(Ctrl+N/O/S/Z, Ctrl+Enter 복사, Alt+F/E/T/H 메뉴). 데스크톱판은 다시 실행(Ctrl+Y), 다른 이름으로 저장(Ctrl+Shift+S), 사용법(F1)을 더한다.

---

## 2. 데스크톱판에서 새로 필요한 개발 기능 (요구사항 1번)

웹판은 브라우저가 대신 해 주던 일이 많다. 데스크톱에서는 아래를 직접 만들어야 실제로 동작한다.

### 2-1. 데이터 계층
- **DB 연결 관리자** `db.py`: 연결 1개를 앱 전체에서 공유, 시작할 때 `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL` 적용.
- **스키마 마이그레이션**: `PRAGMA user_version`으로 버전 관리. `resources/schema/NNN_*.sql`을 번호순으로, 현재 버전보다 높은 것만 한 트랜잭션씩 적용하는 함수 `migrate(conn)`. 다시 불러도 안전해야 한다.
- **저장소(Repository) 계층** `repository.py`: GUI 코드는 SQL을 직접 쓰지 않는다. `TemplateRepo.save(template)`처럼 도메인 객체 단위로 저장·조회.
- **트랜잭션**: 템플릿 저장은 블록·변수까지 한 트랜잭션(`with conn:`)으로 처리해 반쯤 저장되는 일을 막는다.
- **라이브러리 시드**: `resources/library.json`을 읽어 `is_library=1` 템플릿으로 넣는다. `settings.library_version`과 비교해 새 버전이면 라이브러리 행만 교체(사용자 템플릿은 건드리지 않음). **[1.1] 현재 라이브러리 버전 2.**
- **[1.1] 예시 시드**: `resources/samples.json`을 읽어 **사용자 템플릿(`is_library=0`)**으로 넣는다. `settings.samples_version`보다 새 버전일 때만, 이미 있는 uuid는 덮어쓰지 않는다. 같은 버전이면 아무것도 하지 않으므로 사용자가 지운 예시는 되살아나지 않는다. uuid는 `uuid5(SAMPLE_NS, 이름)`으로 고정.

### 2-2. 작업 보존
- **자동 저장**: 편집 후 2초(설정 가능) 동안 입력이 없으면 `autosave` 테이블에 현재 작업을 JSON으로 기록.
- **비정상 종료 복구**: 시작할 때 `autosave.clean_exit = 0`이면 "지난번 작업을 복구할까요?" 대화상자 표시. 정상 종료 시 `clean_exit = 1`.
- **실행 취소 / 다시 실행**: 메모리 스택(최대 100단계). 구조 변경(블록 추가·삭제·이동, 변수 추가·삭제·이름 변경, 마스킹, 첫 문장 켜고 끄기)마다 스냅샷 저장. 글자 입력은 입력칸에 포커스가 들어온 뒤 **처음 바뀔 때** 한 번만 스냅샷.
- **종료 확인**: 저장하지 않은 변경이 있으면 창 닫기(`WM_DELETE_WINDOW`) 때 저장 / 저장 안 함 / 취소 확인.

### 2-3. 운영체제 연동
- **클립보드**: `root.clipboard_clear()` → `root.clipboard_append(text)` → `root.update()`.
- **파일 대화상자**: `filedialog`로 JSON 내보내기·가져오기, 프롬프트를 `.txt`(UTF-8)로 저장.
- **글꼴 등록**: 설치하지 않고 앱 안에서만 둥근모꼴을 쓴다. `Tk()` 생성 **전에** 호출해야 한다.
  ```python
  import ctypes
  FR_PRIVATE = 0x10
  ctypes.windll.gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0)
  ```
  - **[1.1] 주의 — 글꼴 이름:** 한국어 Windows는 이 글꼴을 이름표의 한국어 이름 **"둥근모꼴"**로만 목록에 올린다. `"DungGeunMo"`로만 찾으면 못 찾고 조용히 굴림으로 대체된다. `tkinter.font.families()`에서 **"둥근모꼴" → "DungGeunMo"** 순으로 찾고, 실제 쓰는 글꼴 이름을 로그에 남긴다.
  - 둘 다 없으면 `굴림` → `돋움` → `TkDefaultFont` 순으로 대체.
  - 검증: 둥근모꼴은 고정폭이므로 `font.measure("iiii") == font.measure("WWWW")`이면 실제 적용된 것.
- **고해상도 화면(DPI)**: 시작 직후 `ctypes.windll.shcore.SetProcessDpiAwareness(1)`. 실패하면 `user32.SetProcessDPIAware()`. 그 뒤 `root.tk.call('tk', 'scaling', dpi/72)`.
- **[1.1] 창 크기**: 첫 크기는 1400×860(배율 반영)이되 `SystemParametersInfoW(SPI_GETWORKAREA)` 작업 영역 안에 들어오게 줄이고, 창이 뜬 뒤 실제 아래쪽 끝을 재서 작업 표시줄에 가리면 다시 줄인다.
- **소리 재생(부팅음)**: `winmm.mciSendStringW`로 mp3·wav 재생(wav는 `waveaudio`, 실패하면 `winsound`).
  - 소리 파일은 **사용자가 [설정]에서 직접 고른 파일**의 경로를 `settings.boot_sound_path`에 저장해 재생한다.
  - 고른 파일이 없으면 앱에 포함된 **자체 제작 효과음** `resources/sounds/boot_default.wav`를 재생한다(`tools/make_assets.py`로 합성).
  - Microsoft Windows 98 시작음 같은 타사 저작물은 배포 패키지(exe, resources)에 **넣지 않는다**.
- **리소스 경로**: PyInstaller로 묶이면 파일이 임시 폴더로 풀리므로 경로 함수를 통일한다.
  ```python
  def res(*p):
      base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
      return base.joinpath("resources", *p)
  ```
- **데이터 폴더**: `%APPDATA%\Prompt98\`를 만들고 DB·로그 저장. exe 옆에 `portable.flag`가 있으면 exe 폴더를 사용(USB 휴대용).
- **단일 실행**: 같은 DB를 두 개의 프로세스가 동시에 쓰지 않도록 이름 있는 뮤텍스(`kernel32.CreateMutexW`, 이름에 DB 경로 해시 포함)로 중복 실행 시 안내 후 종료.

### 2-4. 품질
- **로깅**: `logging` + `RotatingFileHandler`(1MB × 3개) → `%APPDATA%\Prompt98\logs\app.log`.
- **예외 처리**: `root.report_callback_exception`을 덮어써서 오류를 로그에 남기고 Win98 스타일 오류 대화상자로 안내(프로그램은 계속 실행).
- **점검 엔진 분리**: `checks.py`, `builder.py`는 GUI와 무관한 순수 함수로 작성해 `pytest`로 단위 테스트.
- **입력 검증**: 가져오기 JSON은 스키마를 검사하고, 알 수 없는 블록·변수 형식은 버리고 개수를 알려 준다.

### 2-5. [1.1] 변수 표시 규칙 — `{{ }}`를 화면에 보이지 않기
컴퓨터에 익숙하지 않은 사용자에게 `{{부서명}}` 표기는 어렵다. **저장 형식과 복사 결과는 그대로 `{{이름}}`**(웹판 JSON 호환)으로 두고, 화면에서만 이름을 색 칸으로 보여 준다.

| 위치 | 표시 |
|---|---|
| ① 변수 영역 | 파란 버튼 모양 칸에 이름만 (`#cfe3ff` 바탕, 남색 글자) |
| ② 블록 편집기 `Text` | `{{`·`}}`와 안쪽 공백에 **아주 작은 글자 + 칸과 같은 색** 태그 → 괄호는 안 보이고 칸 양옆 여백처럼 보임. 이름에는 파란 칸 태그. 변수 영역에 없는 이름은 빨간 칸 |
| ② 블록 편집 동작 | 칸은 한 덩어리: 칸 바로 뒤 BackSpace / 바로 앞 Delete → 칸 통째 삭제, 칸 안에 글자를 치면 칸 뒤로 커서 이동, 칸 안을 클릭하면 칸 뒤로 |
| ④ 미리보기 | 채운 값 = 노란 배경, 빈 값 = 괄호 없이 빨간 칸 |
| 변수 삽입 목록·점검·안내 문구 | `{{이름}}` 대신 이름 또는 「이름」 |

구현: `widgets/varchips.py`(`spans`, `setup_tags`, `decorate`, `install_atomic`). 복사 전 확인 대화상자는 "빈 칸은 `{{이름}}`처럼 괄호 모양 그대로 복사됩니다"라고 안내한다.

### 2-6. [1.2] 로그인·회원가입
- **시작 화면 = 로그인 화면** (`boot.py`의 `LoginScreen`): 하늘 배경과 로고는 그대로, **진행 막대는 없애고** 그 자리에 Win98 창 모양의 로그인 상자(아이디, 비밀번호 `●`, [아이디 기억하기], [로그인] [회원가입]). Enter로 로그인. 계정이 하나도 없으면 "처음 쓰시나요? [회원가입]…" 안내.
- **회원가입** (`dialogs/account.py`의 `SignupDialog`): 아이디(영문·숫자·밑줄 4~20자, 대소문자 구분 없이 중복 불가), 이름(선택, 20자), 비밀번호(8~64자, 영문+숫자, 아이디 포함 금지), 비밀번호 확인. 가입하면 바로 로그인.
- **비밀번호 저장**: 원문은 어디에도 저장하지 않는다. `auth.hash_password` = PBKDF2-HMAC-SHA256, 무작위 솔트 16바이트, 200,000회. 확인은 `hmac.compare_digest`. 없는 아이디도 같은 계산을 해서 응답 시간 차이를 줄인다.
- **잠금**: 같은 아이디로 5번 연속 틀리면 30초 동안 로그인을 막는다(`auth.LoginThrottle`, 프로그램이 켜져 있는 동안).
- **로그아웃**: 파일 메뉴·시작 메뉴 [로그아웃]. 저장 안 한 변경이 있으면 저장 여부를 묻고, 자동 저장을 정상 종료로 표시한 뒤 로그인 화면으로 돌아간다. 로그인 화면에서는 단축키가 동작하지 않는다.
- **비밀번호 바꾸기**: 도움말 메뉴. 지금 비밀번호 확인 후 새 비밀번호 규칙 적용.
- **사용자별로 나뉘는 것**: 내 템플릿(`templates.owner_id`), 자동 저장(`autosave.user_id`, 다른 사용자가 로그인하면 복구 질문 안 함), 사용자 설정 키(`SettingsRepo.USER_KEYS` → `user:<id>:<key>`로 저장: `last_template_uuid`, `wizard_quick_features`, `custom_block_types`, `samples_version`, `first_run_done`), 코레일 예시(사용자마다 따로 받음, uuid = `uuid5(SAMPLE_NS, "<id>:<이름>")`).
- **모두가 같이 쓰는 것**: 라이브러리, 부팅음·자동 저장 시간·창 크기 같은 프로그램 설정, `last_username`(아이디 기억하기).
- **기존 자료 넘기기**: 로그인 기능 전의 자료(주인 없는 내 템플릿, 사용자 설정, 자동 저장)는 **처음 가입하는 사용자**에게 넘긴다(`claim_legacy_data`). 두 번째 가입자부터는 빈 상태에서 자기 예시를 받는다.
- 다른 사용자의 템플릿은 열기 목록에 보이지 않고, 저장·삭제도 거부한다(`ReadOnlyError`).
- 비밀번호를 잊으면 되찾을 수 없다(관리자 재설정 기능 없음). 회원가입 창에 안내한다.

### 2-7. [1.2] 블록 종류 추가
- 블록 머리줄: 점무늬 손잡이 · 블록 종류 이름 · ▲ ▼ ⧉ ×. **제목 입력칸 없음**(블록의 `title`은 만들 때의 종류 이름으로 고정, 미리보기 제목에 쓰임). 블록 복제 때 " 사본"을 붙이지 않는다.
- 팔레트 끝 **[+ 종류 추가]** → `dialogs/blocktype.py`: 이름(10자, 기본 7종·기존 종류와 겹치면 안 됨), 색(어두운 Win98 색 8가지 중 선택), 입력 안내(선택, 빈 블록의 회색 예시 문구), 미리 보기 띠.
- 만든 종류는 기본 7종 뒤에 붙고, 끌어 넣기·편집 메뉴 "○○ 블록 추가"에도 나타난다. 사용자별 설정 `custom_block_types`(JSON `[{key, name, color, hint}]`, key = `c_` + 8자리)에 저장.
- 직접 만든 종류는 팔레트에서 **오른쪽 클릭 → 지우기**. 기본 7종은 지울 수 없다. 이미 그 종류로 만든 블록은 내용·제목이 그대로 남고 회색 블록으로 보인다.
- DB `blocks.type`의 고정 목록 CHECK를 없앴다(스키마 3판, 5-2-2).
- JSON 내보내기에 쓰인 사용자 종류 정의를 `"blockTypes"`로 함께 담고, 가져올 때 먼저 등록한다(웹판은 이 키를 무시).

---

## 3. 프로젝트 구조

```
my_second_winapp\
├─ 프롬프트 98.lnk            # [1.1] 이 PC용 실행 바로 가기 (pythonw -m prompt98)
├─ Prompt98.exe               # [1.1] 배포용 exe 사본
├─ 작업지시서_프롬프트98_tkinter.md / 프롬프트_템플릿_생성기.html
└─ prompt98\
   ├─ prompt98\
   │  ├─ __main__.py          # python -m prompt98 진입점 (로그 → DPI → 글꼴 → 뮤텍스 → DB·시드 → App)
   │  ├─ app.py               # 메인 창, 메뉴, 툴바, 상태 표시줄, 작업 표시줄, 단축키, 자동 저장
   │  ├─ theme.py             # Win98 색상·글꼴 상수, ttk 스타일 설정
   │  ├─ widgets\
   │  │  ├─ win98.py          # Win98Button, ToolButton, GroupBox, Gradient, ProgressBlocks, ScrollFrame, Tooltip
   │  │  ├─ icons.py          # 16×16 픽셀 아이콘(PhotoImage에 직접 그림)
   │  │  ├─ varchips.py       # [1.1] 글 속 {{변수}} → 색 칸 표시·덩어리 편집
   │  │  ├─ variable_panel.py # ① 변수 영역
   │  │  ├─ block_editor.py   # ② 블록 편집기 (드래그 앤 드롭 포함)
   │  │  ├─ form_panel.py     # ③ 입력 양식 자동 생성
   │  │  └─ preview_panel.py  # ④ 미리보기 + 첫 문장 켜고 끄기 + 복사
   │  ├─ dialogs\
   │  │  ├─ base.py           # Win98 대화상자 공통(모달, 확인·취소, Esc 닫기), 오류 보고
   │  │  ├─ account.py        # [1.2] 회원가입·비밀번호 바꾸기
   │  │  ├─ blocktype.py      # [1.2] 블록 종류 추가
   │  │  ├─ wizard.py         # 아티팩트 마법사 + 자주 쓰는 기능 편집(QuickListDialog)
   │  │  ├─ library.py        # 라이브러리
   │  │  ├─ open_save.py      # 열기·저장·내보내기·가져오기·텍스트 저장
   │  │  ├─ check.py          # 구성·보안 점검
   │  │  └─ settings.py       # 부팅음·부팅 화면·자동 저장·자주 쓰는 기능·데이터 위치
   │  ├─ boot.py              # [1.2] 시작 화면 = 로그인 화면 (LoginScreen)
   │  ├─ auth.py              # [1.2] 비밀번호 해시·입력 규칙·로그인 잠금 (순수 함수)
   │  ├─ model.py             # dataclass: Template(intro 포함), Block, Variable
   │  ├─ builder.py           # 프롬프트 조립·변수 치환·첫 문장 (순수 함수)
   │  ├─ checks.py            # 구성·보안 점검 (순수 함수)
   │  ├─ history.py           # 실행 취소 스택
   │  ├─ db.py                # 연결·마이그레이션
   │  ├─ repository.py        # TemplateRepo(owner_id, seed_library, seed_samples), SettingsRepo(user_id), UserRepo, AutosaveRepo, CheckRunRepo
   │  ├─ jsonio.py            # 웹판 호환 JSON 내보내기·가져오기
   │  ├─ platform_win.py      # 글꼴 등록, DPI, 작업 영역, MCI 소리, 뮤텍스
   │  └─ paths.py             # res(), data_dir()
   ├─ resources\
   │  ├─ fonts\DungGeunMo.ttf
   │  ├─ sounds\boot_default.wav   # 자체 제작 효과음
   │  ├─ icons\app.ico, app.png    # 자체 제작 픽셀 아이콘
   │  ├─ library.json              # 기본 라이브러리 17종 (버전 2)
   │  ├─ samples.json              # [1.1] 코레일 업무 예시 7종
   │  └─ schema\001_init.sql, 002_intro.sql, 003_users_blocktypes.sql
   ├─ tests\
   │  ├─ test_builder.py, test_checks.py, test_repository.py   # :memory: DB 사용
   │  ├─ test_samples.py      # [1.1] 예시 시드·예시 품질
   │  ├─ test_wizard.py       # [1.1] 자주 쓰는 기능 저장, 마법사 결과
   │  └─ test_users.py        # [1.2] 비밀번호 해시·가입 규칙·로그인·잠금·사용자별 자료·블록 종류·스키마 3판
   ├─ tools\
   │  ├─ make_assets.py       # 부팅 효과음·아이콘 생성
   │  ├─ smoke_gui.py         # 실제 창을 띄워 기능을 자동으로 눌러 보는 스모크 테스트
   │  └─ shot.ps1             # 스모크 테스트용 창 캡처
   ├─ prompt98.spec, version_info.txt   # PyInstaller 설정
   ├─ requirements-dev.txt    # pyinstaller, pytest
   └─ README.md
```

---

## 4. 로컬 실행 구성 (요구사항 2번)

### 4-1. 개발 환경 준비
```powershell
cd prompt98
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 4-2. 실행
```powershell
python -m prompt98            # 일반 실행 (%APPDATA%\Prompt98 사용)
python -m prompt98 --portable # 현재 폴더에 DB 생성
python -m prompt98 --reset-db # 개발용: DB 백업 후 새로 만들기
# [1.2] --no-boot 는 없앴다: 시작 화면이 로그인 화면이라 건너뛸 수 없다
```
**[1.1]** 일반 사용자는 명령 대신 `my_second_winapp\프롬프트 98.lnk` 바로 가기를 더블클릭한다(콘솔 창 없음). 바로 가기는 프로젝트 폴더 안의 코드를 실행하므로 폴더를 옮기면 바로 가기도 다시 만든다.

### 4-3. 첫 실행 흐름
1. 데이터 폴더 확인·생성 → 로그 설정
2. DPI 인식 설정 → 둥근모꼴 등록 → 중복 실행 확인
3. DB 연결 → `migrate()` → 라이브러리 시드 → **[1.1] 코레일 예시 시드** 확인
4. **[1.2] 로그인 화면** 표시(계정이 없으면 회원가입 안내) → 로그인 또는 회원가입 성공 시 부팅음 재생
5. **[1.2] 사용자 자료 불러오기**: 사용자 블록 종류 등록 → 코레일 예시(그 사용자가 처음이면) → `autosave` 확인(그 사용자의 비정상 종료일 때만 복구 질문) → 메인 창 표시
6. **[1.1] 시작 템플릿:** 지난번 템플릿(`last_template_uuid`) → (첫 실행이면) 코레일 예시 「열차 지연 안내문」 → 가장 최근의 내 템플릿 → 라이브러리 「주간 업무 보고서」 사본 → 빈 템플릿 순으로 연다. 첫 실행이면 상태 표시줄에 "코레일 업무 예시 7개가 내 템플릿에 들어 있어요. 파일 > 열기에서 골라 보세요." 안내.

### 4-4. 로컬 완료 기준
- [x] 인터넷 연결 없이 실행된다.
- [x] `pip install` 없이 표준 라이브러리만으로 실행된다(테스트·빌드 도구 제외).
- [x] 프로그램을 껐다 켜도 저장한 템플릿과 설정이 남아 있다.
- [x] `pytest`가 모두 통과한다. (1.1 기준 80개)
- [x] **[1.1]** `python tools\smoke_gui.py`가 모두 통과한다. (1.1 기준 48개)

---

## 5. 데이터베이스 설계 (요구사항 3번)

### 5-1. 테이블 관계
```
categories 1 ─── N templates 1 ─┬─ N blocks
                                └─ N variables
settings (키-값)   autosave (1행)   check_runs (점검 기록, 선택)
```

### 5-2. DDL — `resources/schema/001_init.sql`
```sql
PRAGMA foreign_keys = ON;

CREATE TABLE categories (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE templates (
    id           INTEGER PRIMARY KEY,
    uuid         TEXT    NOT NULL UNIQUE,                 -- 내보내기·가져오기용 고유값
    name         TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    description  TEXT    NOT NULL DEFAULT '',
    title_style  TEXT    NOT NULL DEFAULT 'bracket'
                 CHECK (title_style IN ('none','bracket','md','num')),
    is_library   INTEGER NOT NULL DEFAULT 0 CHECK (is_library IN (0,1)),
    created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_templates_category ON templates(category_id);
CREATE INDEX idx_templates_library  ON templates(is_library, name);

CREATE TABLE blocks (
    id           INTEGER PRIMARY KEY,
    template_id  INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,                         -- 0부터, 저장 시 재번호
    type         TEXT    NOT NULL
                 CHECK (type IN ('role','context','task','constraint','format','example','text')),
    title        TEXT    NOT NULL DEFAULT '',
    content      TEXT    NOT NULL DEFAULT '',
    enabled      INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1))
);
CREATE INDEX idx_blocks_template ON blocks(template_id, position);

CREATE TABLE variables (
    id           INTEGER PRIMARY KEY,
    template_id  INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    type         TEXT    NOT NULL DEFAULT 'text'
                 CHECK (type IN ('text','area','number','date','select')),
    options_json TEXT    NOT NULL DEFAULT '[]',            -- select 형식의 선택지 배열
    required     INTEGER NOT NULL DEFAULT 1 CHECK (required IN (0,1)),
    value        TEXT    NOT NULL DEFAULT '',              -- 현재 입력값(=기본값)
    UNIQUE (template_id, name)
);
CREATE INDEX idx_variables_template ON variables(template_id, position);

CREATE TABLE settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

CREATE TABLE autosave (
    id          INTEGER PRIMARY KEY CHECK (id = 1),       -- 항상 1행
    payload     TEXT    NOT NULL,                          -- 현재 작업 JSON
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    clean_exit  INTEGER NOT NULL DEFAULT 0,
    saved_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE check_runs (                                  -- 점검 기록(선택 기능)
    id            INTEGER PRIMARY KEY,
    template_id   INTEGER REFERENCES templates(id) ON DELETE CASCADE,
    score         INTEGER NOT NULL,
    findings_json TEXT    NOT NULL,                        -- 민감값 원문은 저장하지 않음(마스킹 후)
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TRIGGER trg_templates_touch AFTER UPDATE ON templates
BEGIN
    UPDATE templates SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;

INSERT INTO categories(name, sort_order) VALUES
 ('문서 작성',1),('데이터·분석',2),('고객·민원',3),('교육·홍보',4),
 ('기획·아이디어',5),('아티팩트 제작',6),('안전·현장',7),('요약·번역',8),('기타',99);

PRAGMA user_version = 1;
```
> `trg_templates_touch`가 스스로 UPDATE를 다시 부르지 않도록 `PRAGMA recursive_triggers`는 기본값(OFF)을 유지한다.

### 5-2-1. [1.1] DDL — `resources/schema/002_intro.sql`
```sql
-- 템플릿마다 첫 문장을 붙일지 여부. 기존 템플릿은 켜짐.
ALTER TABLE templates ADD COLUMN intro INTEGER NOT NULL DEFAULT 1 CHECK (intro IN (0,1));
PRAGMA user_version = 2;
```
버전 1 DB를 쓰던 사용자는 다음 실행 때 자동으로 2가 되고, 저장해 둔 템플릿은 모두 첫 문장이 켜진다(테스트로 확인).

### 5-3. settings 키 목록

| key | 예시 값 | 설명 |
|---|---|---|
| `library_version` | `2` | 라이브러리 시드 버전 |
| `samples_version` | `1` | **[1.1]** 코레일 예시 시드 버전 |
| `first_run_done` | `1` | **[1.1]** 첫 실행(부팅 화면 통과) 완료 여부 |
| `boot_sound_enabled` | `1` | 부팅음 켜기 |
| `boot_sound_path` | `C:\Users\...\my_sound.mp3` | 사용자가 고른 부팅음 파일 경로(없으면 기본 효과음) |
| ~~`show_boot_screen`~~ | | **[1.2]** 없앰(시작 화면은 항상 로그인 화면) |
| `last_username` | `korail01` | **[1.2]** "아이디 기억하기"를 켠 마지막 아이디 |
| `custom_block_types` | `[{"key":"c_…","name":"참고 자료",…}]` | **[1.2]** 사용자가 만든 블록 종류(사용자별) |
| `autosave_seconds` | `2` | 자동 저장 대기 시간 |
| `last_template_uuid` | `...` | 다음 실행 때 열 템플릿 |
| `window_geometry` | `1400x860+40+30` | 창 크기·위치 |
| `window_zoomed` | `0` | 최대화 여부 |
| `wizard_quick_features` | `["검색·필터", …]` | **[1.1]** 아티팩트 마법사 "자주 쓰는 기능" 목록(JSON 배열). 없으면 기본 8개, 빈 배열이면 빈 목록 그대로 |
| `ai_enabled` | `1` | **[1.5]** 블록 편집기에 [AI 추천] 단추 보이기 |
| `ai_url` | `http://127.0.0.1:11434` | **[1.5]** Ollama 주소 |
| `ai_model` | `gemma4` | **[1.5]** 추천에 쓸 Ollama 모델 이름 |

> **[1.2]** `last_template_uuid`, `wizard_quick_features`, `custom_block_types`, `samples_version`, `first_run_done`은 사용자별 키다. 실제로는 `user:<사용자 id>:<key>`로 저장되며 `SettingsRepo(user_id=…)`가 알아서 바꿔 준다.

### 5-2-2. [1.2] DDL — `resources/schema/003_users_blocktypes.sql` (요약)
```sql
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL DEFAULT '', pw_hash TEXT NOT NULL, pw_salt TEXT NOT NULL,
    pw_iter INTEGER NOT NULL, created_at TEXT …, last_login TEXT);
ALTER TABLE templates ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE;  -- 라이브러리는 NULL
ALTER TABLE autosave  ADD COLUMN user_id INTEGER;
-- blocks.type 의 고정 목록 CHECK 를 없애려고 blocks 표를 다시 만든다(내용·id 보존)
--   type TEXT NOT NULL CHECK (length(type) BETWEEN 1 AND 40)
PRAGMA user_version = 3;
```

### 5-4. 저장 규칙
- 템플릿 저장 = `templates` UPSERT(`intro` 포함) → 해당 템플릿의 `blocks`, `variables`를 **삭제 후 다시 삽입**(순서·이름 변경을 단순하게 처리). 모두 한 트랜잭션.
- 라이브러리 템플릿(`is_library=1`)은 읽기 전용. 불러오면 **복사본**이 편집기에 열리고, 저장할 때 새 `uuid`의 사용자 템플릿이 된다.
- **[1.1]** 코레일 예시는 사용자 템플릿이므로 바로 고쳐서 [저장]할 수 있다.
- 삭제는 `ON DELETE CASCADE`로 블록·변수가 함께 지워진다. 삭제 전 확인 대화상자 필수.
- 자동 저장은 `INSERT ... ON CONFLICT(id) DO UPDATE`로 1행만 유지.

### 5-5. JSON 내보내기 형식 (웹판과 호환)
```json
{
  "app": "prompt98", "version": 1,
  "saved": [
    { "id": "uuid", "name": "주간 업무 보고서", "cat": "문서 작성",
      "data": { "name": "...", "cat": "...", "ts": "bracket", "intro": true,
                "vars":   [{"name":"부서명","type":"text","opts":"","req":true}],
                "values": {"부서명":"여객사업처 영업팀"},
                "blocks": [{"type":"role","title":"역할","content":"...","on":true}] } }
  ]
}
```
웹판에서 내보낸 JSON을 데스크톱판에서 그대로 가져올 수 있어야 한다(반대도 동일). **[1.1]** `intro` 키가 없으면 켜짐으로 가져온다.

---

## 6. 핵심 로직 명세

### 6-1. 변수 치환·조립 (`builder.py`)
- 정규식: `\{\{\s*([^{}]+?)\s*\}\}`
- 값이 비어 있으면 `{{이름}}`을 그대로 남긴다.
- `enabled=0`이거나 내용이 공백뿐인 블록은 제외. 블록 사이는 빈 줄 하나.
- **[1.1] 첫 문장:** `INTRO_TEXT = "아래의 지시사항에 따라 결과물을 생성해줘."`. 템플릿의 `intro`가 참이고 포함된 블록이 하나 이상이면 맨 앞에 붙이고 빈 줄 하나를 둔다(블록 제목 앞). 블록이 하나도 없으면 첫 문장도 붙이지 않는다(빈 프롬프트 복사 방지).
  - 기본값: 새 템플릿·예시·대부분의 라이브러리 = 켜짐
  - 꺼짐: 아티팩트 마법사 결과, 라이브러리 「아티팩트 제작 프롬프트 요청」·「교육 홍보 이미지」(이미 "아래의 … 따라 …"로 시작)
  - 미리보기 막대의 **[✓ 첫 문장 넣기]** 체크 상자로 템플릿마다 바꾼다(실행 취소 가능).
- 미리보기용 함수는 `(텍스트, 태그)` 조각 목록을 돌려주고(이어 붙이면 `build_prompt()`와 같음), `Text` 위젯이 `intro` / `filled` / `missing` / `heading` 태그로 칠한다.

### 6-2. 점검 (`checks.py`)
반환 형식: `Finding(level: 'ok'|'info'|'warn'|'err', title, detail, fix: str|None)`
점수 = `100 − 18×err − 8×warn − 3×info` (0 미만은 0)

**구성 점검**

| 조건 | 등급 | 수정 동작 |
|---|---|---|
| 포함된 블록 없음 | err | — |
| 지시사항(또는 자유 텍스트) 없음 | err | 지시사항 블록 추가 |
| 블록에 쓰였지만 등록 안 된 변수 (「이름」으로 표시) | err | 변수 만들기 |
| 출력 형식 없음 | warn | 출력 형식 블록 추가 |
| 빈 블록 / 필수값 미입력 / 40자 미만 | warn | — |
| 역할·조건 없음, 미사용 변수, 8000자 초과, 모호한 표현(적당히·알아서·대충 등) | info | 블록 추가 / 변수 삭제 |

**보안 점검** (최종 프롬프트 기준, `\b`·`\d`는 웹판과 같게 ASCII 기준)

| 항목 | 정규식(요약) | 마스킹 예 |
|---|---|---|
| 주민등록번호 | `\b\d{6}-?[1-4]\d{6}\b` | `900101-1******` |
| 카드번호 | `\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b` | `****-****-****-1234` |
| 휴대전화 | `\b01[016789]-?\d{3,4}-?\d{4}\b` | `010-****-5678` |
| 계좌번호 추정 | `\b\d{3,6}-\d{2,6}-\d{3,7}\b` (전화·주민번호·날짜 제외) | `110-***-****` |
| 이메일 | 일반 이메일 패턴 | `h***@korail.com` |
| 비밀번호·PIN | `(비밀번호|비번|패스워드|암호|password|pw|pin)\s*(은|는|:|=)?\s*값` | `비번 ****` |
| API 키 | `sk-…`, `AKIA…`, `ghp_…`, `AIza…` | `sk-a****` |
| 내부 IP | 10.x / 172.16–31.x / 192.168.x | `x.x.x.x` |
| 대외비 표시 | 대외비·기밀·사내 한정·내부용·confidential | 경고만 |

- 마스킹은 **입력값과 블록 내용·제목 양쪽**에 적용하고, 적용 전 실행 취소 스냅샷을 남긴다.
- 점검 결과 상세에는 원문이 아니라 마스킹된 값만 보이고, `check_runs`에도 마스킹된 결과만 저장한다.

### 6-3. 드래그 앤 드롭 (`block_editor.py`)
- 블록 목록은 `Canvas` + 내부 `Frame`(스크롤 가능)으로 구성.
- 손잡이에서 `<ButtonPress-1>` → 6px 이상 움직이면 드래그 시작 → 반투명 `Toplevel`(`overrideredirect(True)`, `-alpha 0.85`) 고스트가 커서를 따라감.
- 각 블록 프레임의 `winfo_rooty()`와 높이의 중간값으로 삽입 위치를 계산하고, 남색 선(`Frame`)을 그 위치에 `place`.
- 가장자리 30px 안에서는 캔버스를 자동 스크롤.
- `<ButtonRelease-1>`에서 순서를 확정하고 실행 취소 스냅샷 저장. 팔레트 버튼은 클릭이면 맨 끝에 추가, 끌면 놓은 위치에 삽입.
- 변수 칩을 블록 `Text`로 끌어 놓으면 놓은 좌표의 문자 위치(`text.index(f"@{x},{y}")`)에 `{{변수}}` 삽입(화면에는 칸으로 보임). 칩 클릭은 마지막 커서 위치에 삽입.

### 6-4. [1.1] 복사
1. 프롬프트가 비어 있으면 "복사할 내용이 없어요" 안내.
2. 미입력 변수나 민감 정보가 있으면 「복사 전 확인」(그래도 복사 / 점검 열기 / 취소).
3. 클립보드에 넣은 뒤 **「복사 완료」 대화상자**: "프롬프트를 클립보드에 복사했어요. (N자) / AI 채팅창에 붙여 넣으세요. (Ctrl+V)" + [확인]. 툴바·미리보기 [복사], 도구 메뉴, Ctrl+Enter 모두 같다.

### 6-5. [1.5] 블록 AI 추천 (`ai.py`, `dialogs/suggest.py`)
- **무엇:** 블록마다 아래쪽에 **[AI 추천]** 단추(블록 안에서 `Ctrl+Space`). 누르면 이 PC의 Ollama(`gemma4`)가 그 블록에 쓸 내용을 **3개** 추천하고, 하나를 골라 넣는다.
  - 블록이 비어 있으면 블록 전체 내용을 추천 → **[넣기]**.
  - 내용이 있으면 이어 붙일 빠진 내용을 추천 → **[뒤에 붙이기]**(기본, 다음 줄에 덧붙임) 또는 **[바꾸기]**.
  - **[다시 추천]**, **[닫기]**(받는 중이면 바로 멈춤). 넣기 전에 실행 취소 스냅샷을 남겨 `Ctrl+Z` 로 되돌린다.
- **모델에 주는 정보:** 템플릿 이름·분류, 등록된 변수(이름·형식), 다른 블록 내용(블록마다 앞 160자), 지금 블록 종류·입력 안내·내용. 시스템 지시로 "블록에 그대로 넣을 한국어 문장, 300자 이내, 등록된 변수만 `{{이름}}` 로, 민감 정보 예시 금지"를 준다.
- **호출:** `POST {ai_url}/api/chat`, `stream: true`, `think: false`(CPU 에서 빠르게), `format` = `{"suggestions": [문자열 1~3개]}` JSON 스키마, `temperature 0.7`, `num_predict 700`, `num_ctx 4096`, `keep_alive 15m`, 제한 시간 180초. 표준 라이브러리 `urllib` 만 쓰고, 받는 일은 백그라운드 스레드에서 하며 화면은 `after()` 로만 고친다. 받는 동안 "추천을 만드는 중… N초 · 받은 글자 M" 표시.
- **답 정리:** JSON 이 깨지면 빈 줄로 나눈 문단을 쓴다. 번호 머리("1.", "추천 1:")·겹친 글머리("- - ")를 지우고, **등록되지 않은 `{{변수}}` 는 괄호를 벗겨** 보통 글자로 만든다. 같은 것·지금 내용과 같은 것은 빼고 최대 3개, 하나당 600자까지.
- **오류 안내(한국어):** Ollama 꺼짐 → "Ollama 에 연결하지 못했어요… 켜져 있는지 확인", 모델 없음 → "`ollama pull gemma4` 으로 받아 주세요", 시간 초과, 빈 답 → "[다시 추천]을 눌러 보세요".
- **설정 → AI 추천 (Ollama):** 단추 보이기(끄면 블록 편집기에서 단추가 사라짐), 주소, 모델, **[연결 확인]**(`GET /api/tags` 로 모델이 있는지 확인). 쓰는 내용은 설정한 Ollama 주소로만 가고 인터넷으로 보내지 않는다.
- **참고(이 PC):** 내장 그래픽뿐이라 100% CPU 로 돌고, 추천 3개에 20~25초 걸린다(첫 호출은 모델을 메모리에 올리느라 더 걸림).
- **웹판:** 아직 없음. 브라우저에서 Ollama 를 부르려면 PC마다 `OLLAMA_ORIGINS` 설정이 필요해서 데스크톱판에만 넣었다.

---

## 7. Windows 98 스타일 구현 가이드

| 요소 | 값 |
|---|---|
| 바탕화면 | `#008080` |
| 창·버튼 면 | `#c0c0c0` |
| 밝은 테두리 / 그림자 / 진한 그림자 | `#ffffff` / `#808080` / `#0a0a0a` |
| 제목줄 | `#000080` → `#1084d0` 그라데이션(Canvas에 세로선으로 그림) |
| 선택 강조 | 배경 `#000080`, 글자 흰색 |
| 미리보기 하이라이트 | 채운 값 `#ffff80`, 빈 값 `#ffd0d0` + 글자 `#a00000` |
| **[1.1] 변수 칸** | `#cfe3ff` 바탕 + `#000080` 글자 (등록 안 된 변수는 빨간 칸) |
| 블록 색 | 역할 `#000080`, 상황 `#008080`, 지시 `#800000`, 조건 `#6b6b00`, 출력 `#800080`, 예시 `#006000`, 자유 `#505050` |
| 글꼴 | **[1.1] 픽셀 단위(음수 크기)로 16px의 정수배만 사용**: 본문 16px, 큰 제목 32px, 점수 48px. 화면 배율 175% 이상이면 2배 |

- **[1.1] 글꼴 크기 주의:** 둥근모꼴은 16px 격자 픽셀 글꼴이다. pt로 크기를 주면 화면 배율(예: 125%)에 따라 20px 같은 크기가 되어 획 굵기가 1px·2px로 들쭉날쭉해진다. 반드시 `tkfont.Font(size=-16)`처럼 픽셀로 지정한다.
- 입체 테두리는 `relief=tk.RAISED / SUNKEN`, `bd=2`를 기본으로 한다.
- `ttk` 위젯(Combobox, Scrollbar, Treeview)은 `ttk.Style().theme_use('clam')` 후 위 색상으로 다시 설정한다. 한글은 글자 폭이 2배이므로 Combobox 너비를 넉넉히 준다.
- 창 테두리는 Windows 기본 테두리를 쓰고(스냅·작업 표시줄 연동 유지), 창 **안쪽**을 Win98 모양으로 꾸민다. 대화상자도 기본 `Toplevel` + `transient(root)` + `grab_set()`. 대화상자의 버튼 줄은 본문보다 **먼저** 배치해야 본문이 커져도 밀려나지 않는다.
- 화면 배치: 3단 `PanedWindow`(변수 270px | 블록 | 양식+미리보기). 창 너비 960px 미만이면 탭 막대(① 변수 / ② 블록 / ③ 양식·④ 미리보기)로 전환.
- 창 아래에 Win98 작업 표시줄([시작] 버튼, 현재 템플릿 이름, 스피커·시계 트레이)을 둔다.

---

## 8. exe 빌드

### 8-1. `prompt98.spec` 핵심
```python
a = Analysis(['prompt98/__main__.py'], pathex=['.'],
             datas=[('resources', 'resources')],
             hiddenimports=[], excludes=['numpy', 'PIL', 'pytest'])
exe = EXE(pyz, a.scripts, a.binaries, a.datas,
          name='Prompt98', icon='resources/icons/app.ico',
          console=False, upx=False, version='version_info.txt')
```
- `__main__.py`는 PyInstaller가 스크립트로 실행하므로 **절대 import**(`from prompt98 import …`)를 쓰고 `pathex=['.']`를 준다.
- 환경 변수 `PROMPT98_ONEDIR=1`이면 폴더판(`dist\Prompt98\`)으로 빌드.

### 8-2. 빌드 명령
```powershell
pytest
python tools\smoke_gui.py
python -m PyInstaller prompt98.spec --clean --noconfirm
# 결과: dist\Prompt98.exe  → my_second_winapp\Prompt98.exe 로 복사
```

### 8-3. 배포 시 확인
- [ ] 파이썬이 없는 깨끗한 Windows 10/11 PC에서 실행된다.
- [ ] 첫 실행 시 `%APPDATA%\Prompt98\prompt98.db`가 생기고, 두 번째 실행 때 데이터가 남아 있다.
- [x] 둥근모꼴이 설치 없이 표시된다. (로그의 "사용 글꼴: 둥근모꼴"로 확인)
- [x] 125% 배율 화면에서 글자가 흐리지 않다. (16px 정수배 적용 후 확인)
- [ ] 백신 오탐이 나면 `--onefile` 대신 `--onedir` 빌드를 함께 제공.
- [x] 배포 폴더에 타사 저작물(예: Microsoft 시작음)이 들어 있지 않다. (exe 내부 목록으로 확인)
- [ ] **[1.1] 코드 서명.** Windows **스마트 앱 컨트롤**이 켜진 PC는 서명되지 않은 새 exe를 어느 폴더에서든 차단한다("An Application Control policy has blocked this file"). 개발 PC가 이 상태라 exe 직접 실행은 확인하지 못했다. 배포 전 `signtool sign /fd SHA256 /tr <타임스탬프 URL> /td SHA256 dist\Prompt98.exe`로 서명하거나, 스마트 앱 컨트롤이 꺼진 PC에서 시험한다. 같은 PC에서는 서명된 `pythonw.exe`를 쓰는 바로 가기로 실행한다.

---

## 9. 테스트 항목

| 영역 | 테스트 |
|---|---|
| builder | 값 있음·없음 치환, 공백 포함 `{{ 이름 }}`, 비활성 블록 제외, 제목 스타일 4종, **[1.1] 첫 문장 위치·끄기·빈 템플릿** |
| checks | 각 보안 정규식 탐지·오탐(날짜 `2026-11-25`는 계좌로 보지 않음), 마스킹 결과, 점수 계산, 점검 상세에 원문 없음 |
| repository | 저장→조회 동일성, 이름 변경 후 재저장, 삭제 시 CASCADE, 라이브러리 읽기 전용, 마이그레이션 재실행 안전, **[1.1] intro 저장, 버전 1 DB 업그레이드** |
| JSON | 웹판 내보내기 파일 가져오기(알 수 없는 블록·변수 버림), 잘못된 형식 거부, 왕복 |
| **[1.1] samples** | 파일 순서로 내 템플릿에 들어감, 같은 버전이면 다시 안 넣음, 고친 예시를 덮어쓰지 않음, 예시마다 빈 변수·미등록 변수·보안 경고 없음 |
| **[1.1] wizard** | 자주 쓰는 기능 저장·불러오기, 빈 목록 유지, 망가진 설정값 대체, 길이·개수 제한, 결과에 첫 문장 없음 |
| **[1.2] users** | 비밀번호 원문 미저장·솔트, 가입 규칙 6가지, 아이디 중복(대소문자), 로그인 성공·실패, 비밀번호 바꾸기, 잠금, 사용자별 템플릿·설정 분리, 사용자별 예시, 기존 자료를 첫 가입자에게, 사용자 블록 종류 등록·저장·지운 뒤 블록 보존, JSON `blockTypes` 왕복, 스키마 2→3 업그레이드 |
| GUI 스모크 (`tools\smoke_gui.py`) | **[1.2] 로그인 사용자, 블록 제목 입력칸 없음, 블록 종류 추가·삭제, 로그아웃→로그인 화면(진행 막대 없음), 틀린 비밀번호, 회원가입 후 자기 자료만,** 둥근모꼴 적용, 코레일 예시 열림, 변수 칸 표시·덩어리 편집, 드래그 순서 변경, 실행 취소 10회, 점검·마스킹, 저장·열기, 라이브러리, 마법사, 자주 쓰는 기능 편집, 첫 문장 끄기, 복사 완료 대화상자, 좁은 창 탭, 자동 저장 |
| 수동 | 강제 종료 후 복구, 부팅음 끄기·켜기·파일 변경, 다른 PC에서 exe 실행 |

---

## 10. 작업 순서 (마일스톤)

| 단계 | 내용 | 완료 기준 | 상태 |
|---|---|---|---|
| M1 | `model`, `builder`, `checks` + 테스트 | `pytest` 통과 | 완료 |
| M2 | `db`, `repository`, 스키마, 라이브러리 시드 | 메모리 DB 테스트 통과 | 완료 |
| M3 | 메인 창 골격(메뉴·툴바·3단·상태 표시줄), Win98 테마, 글꼴·DPI | 빈 창이 Win98 모양으로 뜸 | 완료 |
| M4 | 변수 패널, 블록 편집기(▲▼ 이동까지), 입력 양식, 미리보기, 복사 | 예시 템플릿 편집·복사 가능 | 완료 |
| M5 | 드래그 앤 드롭, 실행 취소, 자동 저장·복구 | 수동 테스트 통과 | 완료 |
| M6 | 열기·저장·내보내기·가져오기, 라이브러리, 점검, 마법사 | 10개 기능 모두 동작 | 완료 |
| M7 | 부팅 화면·부팅음 설정·시작 메뉴, 단일 실행, 로깅 | 로컬 완료 기준 충족 | 완료 |
| M8 | PyInstaller 빌드, 깨끗한 PC 검증 | 배포 체크리스트 충족 | 빌드 완료, **서명·다른 PC 검증 남음** |
| **M9 [1.1]** | 사용자 검토 반영(변경 이력 참고) | 테스트 80개·스모크 48개 통과 | 완료 |
| **M10 [1.2]** | 로그인·회원가입, 사용자별 자료, 블록 종류 추가, 제목 입력칸 삭제 | 테스트 98개·스모크 62개 통과 | 완료 |
| **M11 [1.3]** | 기간 변수·달력, 툴바 사용자 칸, 예시 10종·라이브러리 정비 (웹판 포함) | 테스트 120개·스모크 71개 통과 | 완료 |

---

## 부록 A. 블록 종류

| type | 이름 | 입력 안내 예시 |
|---|---|---|
| role | 역할 | 당신은 10년 차 행정 전문가입니다. |
| context | 상황·배경 | 다음 주 신규 직원 30명 대상 교육이 있습니다. |
| task | 지시사항 | 아래 내용을 바탕으로 안내문을 작성해 주세요. |
| constraint | 조건·제약 | 300자 이내 / 입력에 없는 사실은 지어내지 말 것 |
| format | 출력 형식 | 제목 / 본문 / 요약 3줄 순서의 표 |
| example | 예시 | 원하는 결과물의 예시 |
| text | 자유 텍스트 | 자유롭게 작성 |

## 부록 B. 기본 라이브러리 17종 (`library.json`, 버전 3 **[1.3]**)

| 분류 | 템플릿 |
|---|---|
| 문서 작성 | 주간 업무 보고서, 공문 초안, 회의록 정리, 안내 이메일·공지문 |
| 데이터·분석 | 엑셀 데이터 분석, 설문 결과 요약 |
| 고객·민원 | 민원 답변 초안, 자주 묻는 질문(FAQ) 작성 |
| 교육·홍보 | 교육 홍보 이미지 *(첫 문장 꺼짐)*, 교육 과정 설계 |
| 기획·아이디어 | 아이디어 브레인스토밍, 의사결정 장단점 비교 |
| 아티팩트 제작 | 아티팩트 제작 프롬프트 요청 *(첫 문장 꺼짐)*, 업무 관리 도구 바로 제작 |
| 안전·현장 | 안전점검 체크리스트 |
| 요약·번역 | 긴 문서 요약, 번역 및 다듬기 |

> 각 템플릿의 변수·블록 내용은 웹판 아티팩트의 `LIB` 배열과 동일하게 옮긴다. 첫 문장을 끄는 템플릿은 항목에 `"intro": false`.

**[1.3] 버전 3에서 고친 것** (라이브러리는 읽기 전용이라 버전이 오르면 통째로 바뀐다)

| 템플릿 | 고친 내용 |
|---|---|
| 주간 업무 보고서 | `보고기간`을 글 → **기간** 형식(`2026-11-23 ~ 2026-11-27`). 지시문을 "부서: … / 보고 기간: …" 항목으로 |
| 회의록 정리 | `일시`(글) → **`회의일`(날짜)** |
| 설문 결과 요약 | **`조사기간`(기간)** 변수 추가 |
| 교육 과정 설계 | "{{대상}}을 위한" → "교육 대상: {{대상}}" (값에 따라 을/를이 달라지는 문제) |
| 긴 문서 요약 | "{{독자}}이(가) … {{분량}}로" → "읽을 사람: … / 분량: …" ("한 문단로"처럼 깨지던 문제) |

- 변수 바로 뒤에 붙어도 되는 것은 값과 상관없는 말뿐이다: 단위(건·개·명·시간·분), 에서·에게·에. `{{언어}}로`는 선택지(영어·일본어·중국어)가 모두 모음으로 끝나서 그대로 둔다.
- 웹판 `LIB`·`SAMPLES`는 `tools/sync_web.py`로 JSON에서 다시 만든다(손으로 고치지 않음).

## 부록 C. 아티팩트 마법사 결과 템플릿 구조
- 변수: `요청방식`(select: "제작하기 위한 프롬프트를 만들어줘." / "제작해줘."), `아티팩트이름`, `아티팩트목적`, `아티팩트기능`, 선택적으로 `사용대상`, `화면스타일`, `추가요청`
- 블록 1(지시사항): `아래의 지시에 따라 아티팩트를 {{요청방식}}`
- 블록 2(자유 텍스트, 제목 "요청 내용"): `1. 아티팩트 이름:\n{{아티팩트이름}}\n2. 아티팩트 목적:\n{{아티팩트목적}}\n3. 아티팩트 기능:\n{{아티팩트기능}}` + 선택 항목은 번호를 이어 붙임
- 제목 스타일: `none`, **[1.1] `intro = False`(첫 문장 없음)**
- 기능 목록은 `1) …` 형식으로 줄바꿈해 `아티팩트기능` 값에 넣음
- **[1.1] 자주 쓰는 기능 바로 넣기**
  - 기본 8개: 비밀번호로 접속 제한, 관리자/일반 사용자 권한 구분, 새로고침해도 데이터 유지, 처음 열면 예시 데이터 표시, 검색·필터, 그래프로 시각화, 엑셀(CSV)로 내보내기, 인쇄용 화면
  - 4단계의 **[편집…]** 또는 **도움말 > 설정 > 아티팩트 마법사 > [자주 쓰는 기능 편집…]**에서 추가·고치기·삭제·▲▼ 순서 변경·기본값으로 되돌리기
  - 한 항목 40자, 최대 20개, 빈 칸·중복은 막음. `settings.wizard_quick_features`에 JSON으로 저장
  - 버튼은 창 폭에 맞춰 줄바꿈, 이미 넣은 기능의 버튼은 흐리게(중복 방지)

## 부록 D. [1.3] 코레일 업무 예시 10종 (`samples.json`, 버전 2)

처음 로그인할 때 **내 템플릿**으로 들어가며, 값이 모두 채워져 있어 바로 미리보기·복사가 된다. 모든 이름·일정·수치는 연습용 가상 자료이고 전화번호·이메일 같은 민감 정보는 넣지 않는다. 날짜는 **날짜**, 기간은 **기간** 형식을 쓰고, 첫 문장은 켜져 있다.

| 템플릿 | 분류 | 미리 채운 내용 · 쓰인 형식 |
|---|---|---|
| 열차 지연 안내문 *(첫 로그인 때 열림)* | 고객·민원 | 발생일(날짜), KTX 015 서울→부산, 25분(숫자), 지연 사유·안내 채널(선택) |
| 역 안내방송 문안 **(새)** | 고객·민원 | 대전역 승강장 변경, 국문·영문 방송문, **예시 블록** 사용 |
| 승차권 반환 민원 답변 | 고객·민원 | 접수일(날짜), 반환 위약금 민원, 답변 방향·어조(선택) |
| 명절 특별수송 대책 회의록 | 문서 작성 | 회의일(날짜), 특별수송기간(기간), 회의 메모 |
| 영업팀 주간 업무 보고 **(새)** | 문서 작성 | 보고기간(기간), 완료·진행·이슈·차주 계획 |
| 출장 결과 보고서 **(새)** | 문서 작성 | 출장기간(기간), 부산 현장 점검 내용·후속 조치 |
| 역 안전점검 결과 보고 | 안전·현장 | 점검일·조치기한(날짜), 수원역 점검 메모 |
| 신규 직원 교육 안내 공지 | 교육·홍보 | 교육기간(기간), 인재개발원(의왕) 120명 |
| 보도자료 초안 | 교육·홍보 | 배포일(날짜), 운행기간(기간), '눈꽃열차' |
| KTX 고객 만족도 설문 요약 | 데이터·분석 | 조사기간(기간), 응답 수(숫자), 주관식 응답 8건 |

- 변수 뒤에 값에 따라 달라지는 조사를 붙이지 않는다. 예: `(안내 채널: {{안내채널}})`, `분량: {{분량}}`.
- **업그레이드 규칙** (`TemplateRepo.seed_samples`, 웹판 `seedSamples`):
  - 사용자의 `samples_version`이 낮으면 없는 예시는 넣는다.
  - 이미 있는 예시는 **내용 지문이 예전에 배포한 그대로일 때만** 새 내용으로 바꾼다. 한 글자라도 고친 예시는 그대로 둔다.
  - 예전 지문은 `resources/samples_history/v*.json`에서 `tools/build_samples.py`가 계산해 `samples.json`의 `previousFingerprints`(데스크톱, SHA-1)와 `previousWebFingerprints`(웹, FNV-1a)에 적는다.
  - 웹판은 지금 열어 둔 작업(`ptg.cur`)이 손대지 않은 예전 예시이면 그것도 새 내용으로 바꾼다.
- 예시를 고쳐 새 버전을 낼 때: 지금 `samples.json`을 `samples_history/vN.json`으로 복사 → 내용 수정·`version` 올리기 → `build_samples.py` → `sync_web.py`.

## 부록 E. [1.2] 웹판(`프롬프트_템플릿_생성기.html`)과의 차이

| 항목 | 데스크톱판 | 웹판 |
|---|---|---|
| 계정·자료 저장 | 이 PC의 SQLite DB | 이 브라우저의 localStorage (`ptg.users`, 사용자 자료는 `ptg.u.<아이디>.<키>`) |
| 비밀번호 해시 | PBKDF2-SHA256 200,000회 (`hashlib`) | PBKDF2-SHA256 150,000회 (Web Crypto). 보안 연결(https·localhost·내 PC 파일)이 아니면 로그인 불가 안내 |
| 사용자별 키 | `last_template_uuid`, `wizard_quick_features`, `custom_block_types`, `samples_version`, `first_run_done` | `ptg.cur`, `ptg.saved`, `ptg.quick`, `ptg.samplesV`, `ptg.blockTypes` |
| 기존 자료 넘기기 | 첫 가입자에게 (`claim_legacy_data`) | 첫 가입자에게 (위 키를 사용자 자리로 복사) |
| 잠금 | 5회 실패 → 30초 (프로그램 실행 중) | 5회 실패 → 30초 (페이지를 연 동안) |
| 블록 종류 추가·삭제, 제목 입력칸 삭제, JSON `blockTypes` | 같음 | 같음 (서로 내보내기·가져오기 호환) |

> 브라우저 저장소는 그 PC를 쓰는 사람이 개발자 도구로 볼 수 있으므로, 웹판 로그인은 "사람마다 작업을 나누는 용도"이지 강한 보안 장치가 아니다. 비밀번호 원문은 어디에도 저장하지 않는다.

---

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| 1.0 | 2026-11-25 | 최초 작성 |
| 1.1 | 2026-11-25 | 1차 구현 후 사용자 검토 반영: ① 둥근모꼴 한국어 이름("둥근모꼴") 처리와 16px 정수배 픽셀 글꼴 ② 창이 작업 표시줄에 가리지 않게 ③ 프로젝트 폴더에 실행 바로 가기·exe 사본, 스마트 앱 컨트롤·코드 서명 안내 ④ 변수 `{{ }}`를 화면에서 색 칸으로 표시(2-5) ⑤ "마법사" → "아티팩트 마법사" 이름 통일 ⑥ 코레일 업무 예시 7종(부록 D) ⑦ 자주 쓰는 기능 편집(부록 C) ⑧ 첫 문장 "아래의 지시사항에 따라 결과물을 생성해줘." 기본 삽입과 스키마 2판(6-1, 5-2-1) ⑨ 복사 완료 대화상자(6-4) ⑩ GUI 스모크 테스트 도구 |
| 1.2 | 2026-11-25 | ① 시작 화면의 진행 막대를 없애고 로그인 화면으로(2-6) ② 회원가입·로그아웃·비밀번호 바꾸기, PBKDF2 해시 저장, 5회 실패 시 30초 잠금 ③ 내 템플릿·자동 저장·사용자 설정·코레일 예시를 사용자별로, 기존 자료는 첫 가입자에게 ④ 블록 머리줄의 제목 입력칸 삭제 ⑤ [+ 종류 추가]로 블록 종류 만들기·오른쪽 클릭으로 지우기(2-7) ⑥ 스키마 3판(5-2-2) ⑦ `--no-boot`·`show_boot_screen` 없앰 ⑧ 웹판에도 같은 내용 반영(부록 E) |
| 1.3 | 2026-11-25 | ① 변수 형식 「기간」(시작일 ~ 종료일, 일수 표시, 1일·1주·2주·한 달 빠른 버튼, 거꾸로 된 기간 안내) ② 날짜·기간 칸의 달력 팝업(데스크톱판; 웹판은 브라우저 달력) ③ 스키마 4판 ④ 툴바 오른쪽에 로그인 사용자 칸(이름·아이디·[로그아웃]), 작업 표시줄의 이름은 뺌 ⑤ 데스크톱판·웹판 동시 반영 ⑥ 코레일 예시를 10종(버전 2)으로 다시 만듦: 날짜·기간 형식, 조사 문제 정리, 새 예시 3종(안내방송·주간 보고·출장 보고), 손대지 않은 예전 예시만 자동 갱신(부록 D) ⑦ 라이브러리 버전 3: 날짜·기간 형식과 조사 문제 5곳 수정(부록 B) ⑧ `tools/build_samples.py`·`tools/sync_web.py` |
| 1.4 | 2026-11-25 | 배포: ① GitHub 비공개 저장소 `261125_KORAIL`, 데스크톱 exe 는 Release(`desktop-v1.3`) ② 웹판을 Vercel 프로젝트 `261125_korail` 로 배포(`vercel.json`, GitHub 푸시 시 자동 배포) ③ 웹판 로그인·자료를 Supabase 프로젝트 `261125_KORAIL` 로: Auth(아이디 → `<아이디>@users.prompt98.app` 가상 이메일, 이메일 확인 끔, 비밀번호 8자 이상·영문+숫자) + `user_data` 표(사용자별 cur·saved·quick·samplesV·blockTypes, RLS 로 자기 것만) ④ 이 브라우저에만 있던 예전 계정은 같은 아이디·비밀번호로 처음 로그인할 때 클라우드로 옮김 ⑤ Supabase 에 닿지 않으면 예전처럼 브라우저 저장(오프라인 모드) ⑥ `tools/patch_web_cloud.py`, `supabase/` 마이그레이션·설정. 데스크톱판 자료는 지금처럼 PC 안 sqlite 에 둠 |
| 1.5 | 2026-11-25 | 데스크톱판 블록 AI 추천(6-5): 블록마다 [AI 추천] 단추·`Ctrl+Space`, 이 PC의 Ollama `gemma4` 가 3개 추천 → 넣기/뒤에 붙이기/바꾸기/다시 추천, 실행 취소 가능. 설정에 AI 추천 묶음(켜기·주소·모델·연결 확인)과 settings 키 `ai_enabled`·`ai_url`·`ai_model`. 테스트 `tests/test_ai.py`(가짜 Ollama 서버 13개), GUI 스모크 76개. 빠져 있던 기본 부팅음 `boot_default.wav` 를 `tools/make_assets.py` 로 다시 만듦 |
