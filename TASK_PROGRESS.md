# 개발 진행 현황판 (TASK_PROGRESS.md)

- **최종 업데이트:** 2026-11-02
- **현재 진행 단계:** Task 8 자동 검증 통과, Task 1~8 Windows 수동 검증은 완성본에서 진행 예정
- **규칙:** 각 Task는 자동 테스트 통과 후 `검토 대기`, 사용자 수동 검증 승인 후 `✅ 완료`로 변경한다. 실패/미검증을 완료로 표시하지 않는다.
- **수동 검증 계획:** `docs/task별-수동-테스트-명세서.md`의 Task별 체크리스트를 완성본 기준으로 실행한다. 현재 macOS에서는 Task 1 core 로거 간편 확인을 별도로 수행할 수 있다. Task 5 Mock GUI는 Windows 전용 기본 중복 캐시 경로로 macOS 시작이 불가능하여 최종 Windows 11 환경에서 판정한다.
- **사용자 확정 운영 방식:** 각 Task 종료 후 자동 테스트·체크리스트 갱신·명시적 `git add`·`git commit`·`git push`를 수행한다. Windows 11 수동 검증은 전체 Task 완성 후 사용자가 체크리스트를 실행해 결과를 전달한다. 그 전까지 상태는 `검토 대기`로 두고, 오류가 있으면 전달된 결과를 바탕으로 디버깅한다. macOS에서 바로 확인 가능한 부분은 별도로 안내한다.

---

## 📊 Task 진행 요약표

| Task ID | 작업 명칭 | 선행 조건 | 상태 | 자동 검증 (pytest) | 수동 검증 | 차단/비고 |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **TASK-01** | 상수, 데이터 모델 및 날짜별 TXT 로거 | - | 🔎 검토 대기 | 11 통과 | ⬜ | 3단계 Fallback, 마스킹; Windows 11 실검증 대기 |
| **TASK-02** | 암호화 저장소 및 계정 관리 (위험수용) | TASK-01 | 🔎 검토 대기 | 9 통과 | ⬜ | Windows DPAPI 실검증·복구 정책 승인 대기 |
| **TASK-03** | 앵커 기반 Grafana 알람 파서 및 포맷터 | TASK-01 | 🔎 검토 대기 | 12 통과 | ⬜ | 합성 입력 검증, 실제 클립보드 원문 검증 대기 |
| **TASK-04** | Excel 2종 임포터 및 담당자 매칭 엔진 | TASK-02, 03 | 🔎 검토 대기 | 13 통과 | ⬜ | 합성 Excel 검증, Windows GUI 수동 검증 대기 |
| **TASK-05** | UI 레이아웃 및 확인 후 등록 워크플로우 | TASK-03, 04 | 🔎 검토 대기 | 7 통과 | ⬜ | Mock 전송만 지원, Windows GUI 수동 검증 대기 |
| **TASK-06** | 관리자 2탭 매핑 테이블 GUI 및 환경 설정 | TASK-02, 04 | 🔎 검토 대기 | 9 통과 | ⬜ | Windows DPAPI·GUI 수동 검증 대기 |
| **TASK-07** | Jira 연동 클라이언트 (Mock/실서버) & 패키징 | TASK-05, 06 | 🔎 검토 대기 | 12 통과 | ⬜ | Mock 상태머신·장부, Windows onedir 실검증 대기 |
| **TASK-08** | 오프라인 HTML 기능명세 및 사용설명서 | TASK-07 | 🔎 검토 대기 | 3 통과 | ⬜ | file:// 브라우저·Windows onedir 실검증 대기 |

---

## 🔍 Task별 상세 실행 로그

### [TASK-01] 상수, 데이터 모델 및 날짜별 TXT 로거
- **상태:** 🔎 검토 대기
- **상세 지시서:** `docs/tasks/TASK-01.md`
- **검증 명령:** `pytest tests/test_task1_logger.py -v`
- **자동 검증:** TC-01A~TC-01E 포함 11개 통과; 전체 `pytest -v` 11개 통과 (macOS, Python 3.10.20, pytest 9.2.0). 시스템 Python에 pytest가 없어 `uv run --with pytest`로 임시 환경에서 실행.
- **수정 파일:** `src/__init__.py`, `src/core/__init__.py`, `src/core/constants.py`, `src/core/models.py`, `src/core/logger.py`, `tests/test_task1_logger.py`, `docs/02-ARCHITECTURE-AND-FILE-MAP.md`, `TASK_PROGRESS.md`.
- **자가 수정 내역:** 테스트 실패 없음. 전체 회귀 전 쿠키 마스킹 범위와 폴백 경계 테스트를 보강.
- **미해결 위험/범위:** Windows 11 실제 경로·권한 동작 미검증. 설정 UI는 후속 Task 범위이므로 현재는 `FileLogger` 생성자 인자로 경로/자동 폴더 여부를 지정. 로그 실패 경고는 반환값과 stderr로 제공하며 UI 상단 표시는 UI Task에서 연결 필요.
- **수동 검증 방법:** Windows 11에서 `FileLogger`의 지정 경로/미지정 경로와 `auto_year_month_folder=True/False`를 각각 호출하여 실제 TXT 위치·내용·append 확인. 지정 경로와 `C:\noti-log`를 쓰기 불가로 만들어 `%LOCALAPPDATA%\NotiAutomation\logs` 폴백 및 경고 확인. 모든 후보 실패 시 비영구 기록 경고와 기존 업무 결과 유지 확인.
- **수동 검증 결과:** macOS 간편 확인 명령 실행 통과 (지정 경로 append·연/월 ON·OFF). 사용자 수동 체크리스트 및 Windows 11 실검증은 완성본까지 보류; 완료 승인 전.

### [TASK-02] 암호화 저장소 및 계정 관리
- **상태:** 🔎 검토 대기
- **상세 지시서:** `docs/tasks/TASK-02.md`
- **검증 명령:** `pytest tests/test_task2_auth_crypto.py -v`
- **자동 검증:** TC-02A~TC-02E 포함 9개 통과; 전체 `pytest -v` 20개 통과 (macOS, Python 3.10.20, pytest 9.2.0, cryptography 50.0.2). Windows DPAPI 경계는 테스트용 보호자 객체로 검증.
- **수정 파일:** `src/core/crypto_store.py`, `src/core/auth_manager.py`, `tests/test_task2_auth_crypto.py`, `requirements.txt`, `docs/02-ARCHITECTURE-AND-FILE-MAP.md`, `TASK_PROGRESS.md`.
- **신규 의존성:** `cryptography` (AES-GCM 인증 암호화; 표준 라이브러리에 해당 기능 없음).
- **자가 수정 내역:** 테스트 실패 없음. 전체 회귀 전 손상된 계정 형식 처리와 `%LOCALAPPDATA%` 기본 경로 테스트를 보강.
- **미해결 위험/범위:** ID만으로 재설정하는 계정 탈취·서비스 방해 위험은 사용자 수용 상태로 유지. 별도 복구 키/백업의 실운영 정책(OQ-08)과 사내 정보보호 적합성 승인 필요. Windows DPAPI, 다른 프로필, onedir 동작은 macOS에서 실제 검증하지 않음. Task 2는 core 구현이며 UI 경고·화면 연결은 후속 Task 범위.
- **수동 검증 방법:** `docs/task별-수동-테스트-명세서.md`의 TASK-02 TC-02A~E를 완성본 Windows 11에서 수행. 합성 계정 가입·로그인·ID 재설정·토큰 초기화·세션 무효화, 관리자 비밀번호 변경 후 매핑 읽기, 다른 Windows 프로필의 복구 제약 확인.
- **수동 검증 결과:** 완성본에서 사용자 확인 예정. 완료 승인 전.

### [TASK-03] 앵커 기반 Grafana 알람 파서 및 포맷터
- **상태:** 🔎 검토 대기
- **상세 지시서:** `docs/tasks/TASK-03.md`
- **검증 명령:** `pytest tests/test_task3_parser_formatter.py -v`
- **자동 검증:** TC-03A~TC-03F 포함 12개 통과; 전체 `pytest -v` 32개 통과 (macOS, Python 3.10.20). 합성 3건에서 NoData 1건 제외·정상 2건, 노티·제목 기대값 비교.
- **수정 파일:** `src/core/models.py`, `src/core/parsers/__init__.py`, `src/core/parsers/base_parser.py`, `src/core/parsers/grafana_parser.py`, `src/core/parsers/scp_parser.py`, `src/core/formatter.py`, `tests/test_task3_parser_formatter.py`, `docs/02-ARCHITECTURE-AND-FILE-MAP.md`, `TASK_PROGRESS.md`.
- **자가 수정 내역:** 테스트 실패 없음. 전체 회귀 전 명시적 빈 탭 Target 처리와 테스트를 보강.
- **미해결 위험/범위:** 실제 Grafana 클립보드 원문 미제공. 합성 예시로만 검증했고, 경계를 확정할 수 없는 입력은 `PARSE_AMBIGUOUS`로 반환. SCP는 미지원. UI 붙여넣기·경고 표시·Jira 차단 연결은 후속 Task 범위.
- **수동 검증 방법:** `docs/task별-수동-테스트-명세서.md`의 TASK-03 TC-03A~F를 완성본 GUI에서 확인. 합성 입력 3건의 제외·노티·제목을 확인하고 실제 클립보드 형식에서는 모호한 입력이 경고와 수동 수정 요청으로 표시되는지 확인.
- **수동 검증 결과:** 완성본에서 사용자 확인 예정. 완료 승인 전.

### [TASK-04] Excel 2종 임포터 및 담당자 매칭 엔진
- **상태:** 🔎 검토 대기
- **상세 지시서:** `docs/tasks/TASK-04.md`
- **검증 명령:** `pytest tests/test_task4_matcher_excel.py -v`
- **자동 검증:** TC-04A~TC-04G 포함 13개 통과; 전체 `pytest -v` 45개 통과 (macOS, Python 3.10.20, openpyxl 3.1.5). 암호화 키는 테스트 전용 보호자로 주입했고 Windows DPAPI를 검증한 것은 아님.
- **수정 파일:** `src/core/excel_importer.py`, `src/core/matcher.py`, `src/core/bundle_planner.py`, `tests/test_task4_matcher_excel.py`, `requirements.txt`, `docs/02-ARCHITECTURE-AND-FILE-MAP.md`, `docs/task별-수동-테스트-명세서.md`, `TASK_PROGRESS.md`.
- **신규 의존성:** `openpyxl` (읽기 전용 Excel 워크북 처리; 매크로 실행 없음).
- **자가 수정 내역:** 테스트 실패 없음. 손상된 Excel·중복 캐시와 저장 실패 반환을 보강.
- **미해결 위험/범위:** 실제 사내 Excel 열·Jira 계정 ID 미검증. 표시명만으로는 승인 가능 상태가 되지 않음. 관리자 인증 GUI·Worker 연결은 후속 UI Task에서 수행하고 현재 `submit_import()`는 호출자 소유 Executor에 제출하는 core API.
- **수동 검증 방법:** `docs/task별-수동-테스트-명세서.md`의 TASK-04 합성 Excel 준비 및 TC-04A~G를 완성본 Windows 11 GUI에서 확인. 원본 파일 무변경·충돌 선택·재시작 후 저장·묶음 분할을 확인.
- **수동 검증 결과:** 완성본에서 사용자 확인 예정. 완료 승인 전.

### [TASK-05] UI 레이아웃 및 확인 후 등록 워크플로우
- **상태:** 🔎 검토 대기
- **상세 지시서:** `docs/tasks/TASK-05.md`
- **검증 명령:** `pytest tests/test_task5_ui_workflow.py -v`
- **자동 검증:** TC-05A~TC-05E 및 묶음 분할·배치 내 중복 7개 통과; 전체 `python -m pytest -q` 52개 통과 (macOS, PySide6 6.12.0, Qt offscreen).
- **수정 파일:** `main.py`, `src/main.py`, `src/application/__init__.py`, `src/application/workflow.py`, `src/ui/__init__.py`, `src/ui/main_window.py`, `src/ui/widgets/__init__.py`, `src/ui/widgets/alarm_input_pane.py`, `src/ui/widgets/noti_review_pane.py`, `tests/test_task5_ui_workflow.py`, `requirements.txt`, `docs/02-ARCHITECTURE-AND-FILE-MAP.md`, `docs/manual/MANUAL-SPEC.md`, `docs/task별-수동-테스트-명세서.md`, `TASK_PROGRESS.md`.
- **신규 의존성:** `PySide6-Essentials` (Widgets, QtTest GUI 및 오프스크린 테스트; 전체 PySide6 패키지보다 작음).
- **자가 수정 내역:** Enter 테스트의 커서 위치를 명시하고, 같은 입력 배치의 중복 전송 및 묶음의 비연속 인덱스 처리 보강.
- **미해결 위험/범위:** 기본 실행은 `MOCK-` 키를 반환하는 로컬 Mock이며 실 Jira 연결·Worker·등록 장부는 Task 7 범위다. 현장 Jira 계정 ID 및 매핑 파일이 없어 수동 입력 기반 합성 검증만 가능하다. `UNKNOWN`·`PARTIAL_FAILED`는 자동 재등록을 차단하며 실제 수동 대조 절차는 Task 7에서 연결한다. macOS 기본 실행은 Windows 전용 중복 캐시 경로 때문에 `WINDOWS_REQUIRED`로 종료됨을 사용자 실행에서 확인했다. macOS 전용 제품 코드 변경은 적용하지 않고 Windows 11 실제 GUI/포커스 검증까지 보류한다.
- **수동 검증 방법:** `docs/task별-수동-테스트-명세서.md`의 TASK-05 TC-05A~E 및 05F를 완성본 Windows 11에서 실행. Enter 줄바꿈, 미검토 차단, NoData 통계, 적격 건만 Mock 요청, 명시적 중복 확인, 묶음 확인 게이트와 `MOCK-` 키를 확인한다.
- **수동 검증 결과:** 완성본에서 사용자 확인 예정. 완료 승인 전.

### [TASK-06] 관리자 2탭 매핑 테이블 GUI 및 환경 설정
- **상태:** 🔎 검토 대기
- **상세 지시서:** `docs/tasks/TASK-06.md`
- **검증 명령:** `pytest tests/test_task6_admin_settings.py -v`
- **자동 검증:** TC-06A~TC-06C 관련 9개 통과; 전체 `python -m pytest -q` 61개 통과 (macOS, Qt offscreen, 테스트 보호자 주입). 실제 Windows DPAPI 동작은 검증하지 않음.
- **수정 파일:** `src/core/mapping_admin.py`, `src/core/settings_store.py`, `src/ui/auth_dialog.py`, `src/ui/admin_dialog.py`, `src/ui/settings_dialog.py`, `src/ui/main_window.py`, `src/main.py`, `tests/test_task6_admin_settings.py`, `docs/02-ARCHITECTURE-AND-FILE-MAP.md`, `docs/manual/MANUAL-SPEC.md`, `docs/task별-수동-테스트-명세서.md`, `TASK_PROGRESS.md`.
- **신규 의존성:** 없음. 기존 PySide6-Essentials·openpyxl·cryptography 사용.
- **자가 수정 내역:** 설정 저장 후 토큰 저장 실패를 부분실패로 명시하고, Excel 충돌에 행별 결정 보류 선택지를 추가. UI 버튼 경로의 저장·검색·비동기 가져오기 테스트 보강.
- **미해결 위험/범위:** 실 Jira 필드 스키마·계정 ID는 확인되지 않아 설정의 환경 상태는 MOCK/UNVERIFIED만 허용한다. 관리자 비밀번호 최초 설정과 Windows DPAPI 보호 토큰은 실제 Windows 11에서 미검증. macOS에서 기본 앱 실행은 Windows 전용 경로 및 DPAPI로 불가. Excel 가져오기 Worker의 현장 Excel 형식과 대량 행 UI 응답성도 Windows 실측 대기.
- **수동 검증 방법:** `docs/task별-수동-테스트-명세서.md`의 TASK-06 TC-06A~C를 최종 Windows 11 배포본과 합성 계정·Excel에서 수행. 미승인 차단, 승인 후 두 탭 CRUD 재시작 유지, 충돌 선택, 설정·토큰 분리 저장과 UI 응답을 확인한다.
- **수동 검증 결과:** 최종 완성 후 사용자 확인 예정. 완료 승인 전.

### [TASK-07] Jira 연동 클라이언트 및 onedir 패키징
- **상태:** 🔎 검토 대기
- **상세 지시서:** `docs/tasks/TASK-07.md`
- **검증 명령:** `pytest tests/test_task7_jira_client.py -v`
- **자동 검증:** TC-07A~G 관련 12개 통과; 전체 `python -m pytest -q` 73개 통과 (macOS, uv 임시 환경). Windows onedir 실행은 미검증.
- **수정 파일:** `src/core/jira_client.py`, `src/core/registration_journal.py`, `src/application/workflow.py`, `src/ui/workers.py`, `src/ui/main_window.py`, `src/main.py`, `packaging/noti-automation.spec`, `tests/test_task7_jira_client.py`, `docs/02-ARCHITECTURE-AND-FILE-MAP.md`, `docs/manual/MANUAL-SPEC.md`, `docs/task별-수동-테스트-명세서.md`, `TASK_PROGRESS.md`.
- **신규 의존성:** 런타임 없음. Windows 배포 빌드에만 PyInstaller 필요.
- **미해결 위험/범위:** 실 Jira 종류·필드·권한 미확정으로 Mock만 전송 가능. HTTP 오류는 주입된 Mock 어댑터로 분류 검증했으며 실서버 통합 테스트를 수행하지 않았다. Windows onedir 빌드 및 DPAPI·재시작 유지 검증은 최종 Windows 11에서 사용자 확인 필요. 다른 PC의 독립 장부 간 전역 중복 방지는 보장하지 않는다.
- **수동 검증 방법:** `docs/task별-수동-테스트-명세서.md`의 TC-07A~G를 따른다. Mock 정상 GUI는 `MOCK-` 키와 재시작 후 중복·미확정 게이트를 확인한다. timeout·watcher 실패는 테스트 주입 시나리오로 확인한다. Windows에서 PyInstaller onedir 빌드 후 Python 없는 PC에서 실행하고 배포 폴더 교체 후 `%LOCALAPPDATA%/NotiAutomation/` 데이터 유지 확인.
- **수동 검증 결과:** 최종 완성 후 사용자 확인 예정. 완료 승인 전.

### [TASK-08] 오프라인 HTML 기능명세 및 사용설명서
- **상태:** 🔎 검토 대기
- **상세 지시서:** `docs/tasks/TASK-08.md`
- **검증 명령:** `pytest tests/test_task8_manual_docs.py -v`
- **자동 검증:** TC-08A~B 관련 3개 통과; 전체 `python -m pytest -q` 76개 통과 (macOS, uv 임시 환경). `node --check docs/manual/assets/manual.js` 통과. 브라우저 UI 접근 권한이 없어 실제 `file://` 화면 조작은 미검증.
- **수정 파일:** `docs/manual/index.html`, `docs/manual/assets/style.css`, `docs/manual/assets/manual.js`, `src/ui/main_window.py`, `packaging/noti-automation.spec`, `tests/test_task8_manual_docs.py`, `tests/test_task7_jira_client.py`, `docs/manual/MANUAL-SPEC.md`, `docs/02-ARCHITECTURE-AND-FILE-MAP.md`, `docs/task별-수동-테스트-명세서.md`, `TASK_PROGRESS.md`.
- **신규 의존성:** 없음. 기존 PySide6의 `QDesktopServices`로 로컬 매뉴얼을 연다.
- **미해결 위험/범위:** 실제 Windows 11 PyInstaller onedir 배포 폴더와 오프라인 브라우저 실행은 미검증. 실 Jira 연동은 여전히 Mock만 제공하며 현장 스키마 검증 전에는 실서버 성공을 표시하지 않는다.
- **수동 검증 방법:** `docs/task별-수동-테스트-명세서.md`의 TC-08A~B에 따라 네트워크를 차단하고 `file://` 또는 GUI `도움말` → `사용설명서 열기`로 열어 8개 목차, 검색 일치·결과 없음, 예시, 화면 문구, 배포 리소스를 확인한다.
- **수동 검증 결과:** 최종 Windows 11 사용자 확인 예정. 완료 승인 전.


## 9. 표준 경로 규약
- `docs/tasks/TASK-XX.md`를 Task 명세로 사용. 모든 테스트 경로는 위 표에 적힌 `tests/test_taskN_*.py` 형태로 통일.
- `main.py`(루트)를 프로그램·PyInstaller 실행 진입점으로 사용.
- 자동 테스트 완료 → 수동 검증 대기 → 사용자 확인 후 완료 및 다음 Task 승인.
