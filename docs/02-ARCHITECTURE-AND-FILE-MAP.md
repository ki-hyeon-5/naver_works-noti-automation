# 02. 시스템 아키텍처 및 모듈 내비게이션 맵

본 문서는 시스템 모듈 구조와 계층별 의존성 규칙을 정의합니다.

---

## 1. 아키텍처 계층 다이어그램

```text
+-----------------------------------------------------------------+
|                         PySide6 GUI                             |
|  (main_window, auth_dialog, admin_dialog, settings_dialog)      |
+--------------------------------+--------------------------------+
                                 | 이벤트 호출 (QThread 비동기)
                                 v
+-----------------------------------------------------------------+
|                    Application Service Layer                    |
|             (workflow_controller, background_workers)           |
+--------------------------------+--------------------------------+
                                 | 순수 Python 호출
                                 v
+-----------------------------------------------------------------+
|                       Core Domain Engine                        |
|  - parsers (GrafanaParser, BaseParser)                          |
|  - formatter (NotiFormatter, JiraSummaryBuilder)                |
|  - matcher (MappingMatcher, DuplicateDetector)                  |
|  - jira (JiraClient, JiraStateTracker)                          |
|  - storage (CryptoStore, ExcelImporter, AccountManager)         |
|  - logging (FileLogger, PathResolver)                           |
+-----------------------------------------------------------------+
```

---

## 2. 패키지 및 모듈 배치 구조

아래 트리는 전체 목표 구조이다. Task 1에서 생성된 파일은 `src/__init__.py`,
`src/core/__init__.py`, `src/core/constants.py`, `src/core/models.py`,
`src/core/logger.py`이다. Task 2에서 `src/core/crypto_store.py`,
`src/core/auth_manager.py`를 생성했다. 나머지 모듈은 후속 Task 범위에 속한다.
현재 `FileLogger`는 `LogRecord`를 받아 `LogWriteResult`로 저장 여부와 경고를 반환한다.
`LogRecord`는 허용된 이벤트 코드와 정형 필드만 포함하며, 예외 메시지는 기록하지 않는다.
`CryptoStore`는 `%LOCALAPPDATA%/NotiAutomation/data/`의 두 암호화 DB에 AES-GCM으로
저장하고, DEK는 현재 Windows 사용자 DPAPI로 보호한다. `AuthManager`는
`%LOCALAPPDATA%/NotiAutomation/config/` 아래 계정 해시와 보호된 토큰을 관리한다.
macOS 테스트는 경로와 보호자 객체를 명시적으로 주입한다. AES-GCM은
`requirements.txt`의 `cryptography`에 의존한다.
Task 3에서 `src/core/parsers/` 패키지와 `src/core/formatter.py`를 생성하고
`src/core/models.py`에 파싱 결과 모델을 추가했다. 파서는 Qt·Jira I/O 없이
원문 문자 범위와 오류코드를 반환한다.
Task 4에서 `src/core/excel_importer.py`, `src/core/matcher.py`,
`src/core/bundle_planner.py`를 생성했다. Excel 읽기와 암호화 저장은
`ExcelImporter.submit_import()`로 호출자 소유 Worker에 제출할 수 있다.
매칭은 담당자 표시명과 Jira 계정 식별자를 구분하고, 묶음은 모든 구성원 쌍의
적합성을 확인한다. Excel 읽기는 `requirements.txt`의 `openpyxl`에 의존한다.
Task 5에서 `src/application/workflow.py`와 PySide6 입력·검토 화면을 추가했다.
Workflow는 검토·중복·묶음·등록 차단 상태를 Qt 없이 관리한다. 루트 `main.py`는
명시적으로 Mock 발신기만 연결하며 실 Jira I/O는 수행하지 않는다.
Task 6에서 `src/core/mapping_admin.py`와 `src/core/settings_store.py`를 추가했다.
전자는 관리자 비밀번호 승인 후 암호화 매핑 CRUD를 수행하고, 후자는 로그인 세션별
설정을 원자적으로 저장한다. 토큰은 설정 JSON이 아니라 기존 `AuthManager`의
DPAPI 보호 파일에 보관한다. `src/ui/auth_dialog.py`, `admin_dialog.py`,
`settings_dialog.py`는 Windows 진입점과 메인 메뉴에 연결된다. Excel 가져오기는
호출자 소유 Executor에서 실행하며 실 Jira 필드는 여전히 Mock 상태다.
Task 7에서 `src/core/jira_client.py`의 Mock 어댑터·상태 머신과
`src/core/registration_journal.py`의 원자적 등록 장부를 연결했다. 실제 Jira
필드 검증 전에는 Mock만 실행한다. `src/ui/workers.py`는 Jira 등록을 QThread에서
실행하며, `packaging/noti-automation.spec`는 Windows onedir 빌드 정의다.

```text
src/
├── __init__.py
├── application/
│   ├── __init__.py
│   └── workflow.py                # 검토 상태, 묶음 승인, 중복/전송 게이트
├── main.py                          # 앱 부트스트랩 및 GUI 진입점
├── core/
│   ├── __init__.py
│   ├── constants.py                 # 정규식, 에러코드, 경로 상수 집중
│   ├── models.py                    # ParsedAlarm, JiraIssue, Account 등 데이터 클래스
│   ├── logger.py                    # 3단계 Fallback 날짜별 TXT 로거
│   ├── crypto_store.py              # AES-GCM 파일 암호화 및 DPAPI 래핑 키
│   ├── auth_manager.py              # 회원가입, 로그인, 토큰 초기화형 비밀번호 재설정
│   ├── mapping_admin.py             # 관리자 승인 게이트와 암호화 매핑 CRUD
│   ├── settings_store.py            # 세션별 비밀값 제외 설정 JSON 저장
│   ├── registration_journal.py      # Jira 요청 전후 상태 원자적 장부
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base_parser.py           # 파서 추상 인터페이스
│   │   ├── grafana_parser.py        # 13필드 앵커 기반 Grafana 파서
│   │   └── scp_parser.py            # 추후 확장용 스켈레톤 (미지원 예외 반환)
│   ├── formatter.py                 # 노티 본문 및 Jira Summary 생성기
│   ├── matcher.py                   # Grafana/N3R 매칭, 충돌 감지, set 기반 중복 탐지
│   ├── excel_importer.py            # openpyxl 기반 Excel Append 및 중복 검증
│   └── jira_client.py               # Mock 어댑터, Jira 상태 머신·실서버 게이트
└── ui/
    ├── __init__.py
    ├── workers.py                   # QThread 비동기 작업 래퍼
    ├── auth_dialog.py               # 로그인 / 회원가입 / 비밀번호 재설정 다이얼로그
    ├── main_window.py               # 메인 워크플로우 화면 (붙여넣기, 검토, 승인)
    ├── admin_dialog.py              # 관리자 인증 및 2탭 매핑 테이블 관리
    ├── settings_dialog.py           # 토큰, 에픽, 로그 경로 환경설정
    └── widgets/
        ├── alarm_input_pane.py      # 알람 텍스트 입력 및 통계 표시
        └── noti_review_pane.py      # 노티 미리보기, 수정, 개별/묶음 토글
main.py                            # 루트 실행 진입점
packaging/noti-automation.spec      # Windows PyInstaller onedir 설정
```

---

## 3. 기능 변경 시 AI 내비게이션 타겟 맵

| 작업 시나리오 | 1차 수정 대상 파일 | 참조 스펙 문서 |
| :--- | :--- | :--- |
| **로그 경로 정책 또는 Fallback 변경** | `src/core/logger.py` | `docs/specs/LOGGING-AND-SETTINGS.md` |
| **비밀번호 재설정 또는 토큰 암호화** | `src/core/auth_manager.py`, `src/core/crypto_store.py` | `docs/specs/AUTH-AND-SECURITY.md` |
| **Grafana 파싱 앵커 또는 소괄호 정제** | `src/core/parsers/grafana_parser.py`, `src/core/formatter.py` | `docs/specs/PARSER-SPEC.md` |
| **Excel 컬럼 매핑 또는 충돌 로직** | `src/core/matcher.py`, `src/core/excel_importer.py` | `docs/specs/DATA-MODEL-AND-MATCHING.md` |
| **단일 승인 모드 및 Enter 키 처리** | `src/ui/main_window.py`, `src/ui/widgets/noti_review_pane.py` | `docs/specs/UI-WORKFLOW.md` |
| **Jira 상태 머신 또는 타임아웃 처리** | `src/core/jira_client.py` | `docs/specs/JIRA-INTEGRATION.md` |
| **HTML 사용설명서 내용 갱신** | `docs/manual/MANUAL-SPEC.md`, `docs/manual/index.html` | `docs/manual/MANUAL-SPEC.md` |


## 4. 배포 및 파일 경로 계약 (개정)
- `main.py`는 저장소 루트 진입점이며 `src/main.py`의 `main()`을 호출한다. PyInstaller 진입점은 **루트 `main.py`**로 통일한다.
- `src/core`는 Qt를 import하지 않는다. `src/ui`는 core의 공개 인터페이스를 호출한다. 작업 조합/상태 관리는 `src/application/workflow.py`에 둔다. Qt worker는 `src/ui/workers.py`에 둔다.
- 리소스(매뉴얼, 아이콘)는 `importlib.resources`/패키지 경로 또는 PyInstaller resource locator로 찾으며, 쓰기 데이터는 PyInstaller `_MEIPASS`에 절대 저장하지 않는다.
- 설정/암호화 매핑/계정/토큰 메타/중복 캐시/등록 시도 장부 기본 저장 위치는 `%LOCALAPPDATA%/NotiAutomation/` 아래 분리 디렉터리이다. 배포폴더 교체 시 데이터는 보존된다. 각 PC 독립 저장. portable 앱은 무설치 배포를 뜻하며 배포 디렉터리에 무조건 데이터를 저장한다는 뜻이 아니다.
- 사용자가 명시적으로 포터블 데이터 폴더를 선택하는 기능은 초기 범위 밖이며 향후 검토한다. 로그만 사용자가 위치를 설정한다.
- 관리자 비밀번호를 재설정/변경해도 기존 사용자 계정의 로그인 비밀번호 재설정과 매핑 DB 암호화 키의 생명주기는 독립적이어야 한다.
- 책임 파일: `src/core/registration_journal.py` (Jira 요청 장부), `src/core/settings_store.py`, `src/application/workflow.py`, `src/core/bundle_planner.py`를 명세상 필요 모듈로 추가한다.
