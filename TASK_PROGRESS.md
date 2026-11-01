# 개발 진행 현황판 (TASK_PROGRESS.md)

- **최종 업데이트:** 2026-11-02
- **현재 진행 단계:** Task 1 자동 검증 통과, 사용자 수동 검토 대기
- **규칙:** 각 Task는 자동 테스트 통과 후 `검토 대기`, 사용자 수동 검증 승인 후 `✅ 완료`로 변경한다. 실패/미검증을 완료로 표시하지 않는다.

---

## 📊 Task 진행 요약표

| Task ID | 작업 명칭 | 선행 조건 | 상태 | 자동 검증 (pytest) | 수동 검증 | 차단/비고 |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **TASK-01** | 상수, 데이터 모델 및 날짜별 TXT 로거 | - | 🔎 검토 대기 | 11 통과 | ⬜ | 3단계 Fallback, 마스킹; Windows 11 실검증 대기 |
| **TASK-02** | 암호화 저장소 및 계정 관리 (위험수용) | TASK-01 | ⬜ 대기 | - | ⬜ | 토큰 초기화형 비밀번호 재설정 |
| **TASK-03** | 앵커 기반 Grafana 알람 파서 및 포맷터 | TASK-01 | ⬜ 대기 | - | ⬜ | NoData 제외, 소괄호/대괄호 정제 |
| **TASK-04** | Excel 2종 임포터 및 담당자 매칭 엔진 | TASK-02, 03 | ⬜ 대기 | - | ⬜ | Grafana/N3R 분리 DB, 충돌 감지 |
| **TASK-05** | UI 레이아웃 및 확인 후 등록 워크플로우 | TASK-03, 04 | ⬜ 대기 | - | ⬜ | 단일 모드, 포커스 분리, 묶음 선택 |
| **TASK-06** | 관리자 2탭 매핑 테이블 GUI 및 환경 설정 | TASK-02, 04 | ⬜ 대기 | - | ⬜ | 관리자 인증, Excel Append GUI |
| **TASK-07** | Jira 연동 클라이언트 (Mock/실서버) & 패키징 | TASK-05, 06 | ⬜ 대기 | - | ⬜ | 6단계 상태머신, onedir 패키징 |
| **TASK-08** | 오프라인 HTML 기능명세 및 사용설명서 | TASK-07 | ⬜ 대기 | - | ⬜ | file:// 호환, 검색, UI 동기화 |

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
- **수동 검증 결과:** 사용자 확인 대기

### [TASK-02] 암호화 저장소 및 계정 관리
- **상태:** ⬜ 대기
- **상세 지시서:** `docs/tasks/TASK-02.md`
- **검증 명령:** `pytest tests/test_task2_auth_crypto.py -v`

### [TASK-03] 앵커 기반 Grafana 알람 파서 및 포맷터
- **상태:** ⬜ 대기
- **상세 지시서:** `docs/tasks/TASK-03.md`
- **검증 명령:** `pytest tests/test_task3_parser_formatter.py -v`

### [TASK-04] Excel 2종 임포터 및 담당자 매칭 엔진
- **상태:** ⬜ 대기
- **상세 지시서:** `docs/tasks/TASK-04.md`
- **검증 명령:** `pytest tests/test_task4_matcher_excel.py -v`

### [TASK-05] UI 레이아웃 및 확인 후 등록 워크플로우
- **상태:** ⬜ 대기
- **상세 지시서:** `docs/tasks/TASK-05.md`
- **검증 명령:** `pytest tests/test_task5_ui_workflow.py -v`

### [TASK-06] 관리자 2탭 매핑 테이블 GUI 및 환경 설정
- **상태:** ⬜ 대기
- **상세 지시서:** `docs/tasks/TASK-06.md`
- **검증 명령:** `pytest tests/test_task6_admin_settings.py -v`

### [TASK-07] Jira 연동 클라이언트 및 onedir 패키징
- **상태:** ⬜ 대기
- **상세 지시서:** `docs/tasks/TASK-07.md`
- **검증 명령:** `pytest tests/test_task7_jira_client.py -v`

### [TASK-08] 오프라인 HTML 기능명세 및 사용설명서
- **상태:** ⬜ 대기
- **상세 지시서:** `docs/tasks/TASK-08.md`
- **검증 명령:** `pytest tests/test_task8_manual_docs.py -v`


## 9. 표준 경로 규약
- `docs/tasks/TASK-XX.md`를 Task 명세로 사용. 모든 테스트 경로는 위 표에 적힌 `tests/test_taskN_*.py` 형태로 통일.
- `main.py`(루트)를 프로그램·PyInstaller 실행 진입점으로 사용.
- 자동 테스트 완료 → 수동 검증 대기 → 사용자 확인 후 완료 및 다음 Task 승인.
