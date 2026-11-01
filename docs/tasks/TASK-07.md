# TASK-07 — Mock 기반 Jira 상태 머신, 등록 장부, 부분 실패, onedir Windows 빌드

## 작업 계약
- **상태:** 대기. 선행 Task는 `TASK_PROGRESS.md`를 따른다. 승인 없이 다음 Task로 넘어가지 않는다.
- **요구사항:** REQ-WF-03/04/07, REQ-JIRA-01, REQ-ENV-02/03
- **검증 ID:** TC-07A~TC-07G (`docs/tests/TEST-CASES.md`)
- **목표:** Mock 기반 Jira 상태 머신, 등록 장부, 부분 실패, onedir Windows 빌드
- **구현 범위:** 아래 파일과 이를 연결하는 최소 변경만 허용. 신규 의존성과 인터페이스 변경은 먼저 설명한다.

## 읽을 자료 (이 Task에만 필요한 문서)
- `docs/specs/JIRA-INTEGRATION.md`
- `docs/specs/LOGGING-AND-SETTINGS.md`

## 생성·수정할 파일
- `src/core/jira_client.py`
- `src/core/registration_journal.py`
- `src/ui/workers.py`
- `packaging/noti-automation.spec`
- `tests/test_task7_jira_client.py`

## 입력 및 출력 계약
- 입력: 위 참조 스펙의 구조화된 입력 모델/호출 값 및 합성 픽스처. 직접 네트워크 호출이 필요한 외부 API는 Task 7 전까지 금지.
- 출력: 해당 스펙에 정의된 성공 결과 + 오류코드/경고/부분실패 상태를 구분하는 타입 또는 명시적 반환. 정상 결과로 실패를 숨기지 않는다.
- 데이터 파일 변경 시 실패 원자성(임시 파일→교체) 검증. 모든 네트워크·파일 오류에 사용자에게 필요한 상태/조치를 표시.

## 구현 및 실패 처리 체크리스트
1. Task 담당 기능과 인터페이스를 먼저 계획으로 출력하고 사용자에게 주요 모호성이 없는지 확인한다.
2. 성공 경로와 TC-07A~TC-07G 전 항목에 해당하는 실패·경계 경로를 테스트 코드로 작성한다.
3. 구현 시 기존 요구사항을 바꾸거나 테스트 기대 결과를 낮춰 통과시키지 않는다.
4. 모든 pytest를 실행하고 관련 test 파일/명령이 `TASK_PROGRESS.md`와 일치하는지 확인한다.
5. 바이너리 저장/엑셀 파일을 텍스트로 취급하지 않고, 실제 Git 스테이징 파일을 확인한다.

## 완료 조건(Definition of Done)
- TC-07A~TC-07G 항목의 기대 결과가 통과하고 전체 `pytest` 회귀 검사가 통과.
- 미해결 Jira 현장 정보는 Mock 성공만 표시하고 실연동 완료를 선언하지 않는다.
- 사용자 수동 테스트: Mock timeout 및 watcher 실패에서 create 재호출 없음; 재시작 복원 확인; Windows onedir 실행 확인.
- `TASK_PROGRESS.md`에 테스트 수, 검증 결과, 수정 파일, 미해결 위험, 사용자 수동 검증 방법을 기록. **자동 테스트 통과만으로는 사용자 승인 전까지 Task 상태를 완료로 변경하지 않는다.**
