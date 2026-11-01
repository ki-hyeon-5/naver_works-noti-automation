# AGENTS.md — Codex CLI 구현 규칙

## 우선순위와 읽기
1. `docs/01-REQUIREMENTS-SPEC.md`의 확정 업무 규칙을 최우선 준수한다. 이 문서에 추가된 `REQ-` ID를 기준으로 한다.
2. `TASK_PROGRESS.md`의 첫 대기 Task **하나만** 진행한다. `docs/tasks/TASK-XX.md`와 Task가 명시한 관련 spec, 해당 테스트 케이스만 읽는다. 다른 문서는 충돌 확인이 필요할 때 추가로 읽는다.
3. `docs/decisions/OPEN_QUESTIONS.md`는 미정 정보다. 임의로 확정하거나 Mock을 실연동이라고 보고하지 않는다.
4. 사용자 위험 수용: ID만으로 비밀번호 재설정 및 Jira 토큰 초기화 정책은 변경하지 않는다. 위험은 남아 있으므로 UI/문서에 경고한다.

## 구현과 검증
- 작업 전 변경 계획·검증 항목을 제시. 승인된 Task만 구현하고 다음 Task로 넘어가지 않는다.
- Core 모듈(`src/core`)에서 Qt import 금지. 비즈니스 로직/저장과 UI를 분리. Jira I/O·Excel 임포트는 비동기 Worker로 실행.
- 텍스트 파일은 UTF-8, 바이너리(.dat, Excel)에는 encoding 인자 강요 금지. 경로는 pathlib.
- 비밀정보, 토큰, 사용자 실제 데이터, 로그, 암호화 키, `.dat`, `.bak`는 Git에 올리지 않는다. `.gitignore`를 먼저 점검한다.
- 신규 의존성은 필요성을 먼저 제시하고 가벼운 라이브러리를 우선 사용. PySide6 UI 테마 상수는 UI 안에서 관리하며 core 상수는 도메인에 한정한다.
- 단일 파일 300줄 미만은 권장 가이드이며 책임 분리를 우선. 모듈의 역할은 상단 docstring으로 간결하게 설명.
- 관련 테스트 작성 후 `pytest` **전체 실행**. 실패 시 자가 수정 최대 3회. 테스트 assertion을 약화/삭제/skip 처리하여 성공처럼 만들지 않는다. 환경 문제로 검증 불가하면 미검증 명시.
- 변경 경로를 `git status`/`git diff --stat`로 확인하고 안전한 파일만 **명시적으로 스테이징**한다. `git add .`와 무조건 `git add src/ tests/ docs/` 금지. 커밋 실패 시 보고하고 성공을 주장하지 않는다.
- 각 Task의 자동 테스트와 문서 갱신 후 안전한 파일만 명시적으로 `git add`하고, 해당 Task를 `git commit`, `git push`까지 진행한다. 실패 시 어느 단계에서 실패했는지 보고하고 성공을 주장하지 않는다.
- Windows 11이 필요한 수동 검증은 최종 완성 후 사용자가 `docs/task별-수동-테스트-명세서.md` 체크리스트를 실행하고 결과를 제공한다. 각 Task 종료 시 이 문서에 실행 방법과 기대 결과를 갱신한다. macOS에서 별도 추가 설정 없이 검증 가능한 부분은 사용자에게 안내한다.
- 자동 테스트 완료 시 `TASK_PROGRESS.md`는 `검토 대기`로 기록한다. Windows 수동 검증 보류는 다음 승인된 Task의 구현을 막지 않지만, 사용자가 최종 수동 검증을 확인하기 전에는 `완료`로 갱신하지 않는다.
- 파일/모듈 구조 변경 시 `docs/02-ARCHITECTURE-AND-FILE-MAP.md` 동기화. UI 변경 시 매뉴얼·테스트 명세 동기화.
- 실 Jira 생성은 사용자가 실환경 승인한 뒤 테스트 프로젝트에서만. 제공된 API 토큰을 예시/로그/테스트 fixture에 넣지 않는다.
