# TXT 로그와 사용자 설정 계약

## 1. 경로 및 쓰기
- 초기 기본 로그 경로 `C:\noti-log`; 사용자 설정 경로 사용 가능. 연/월 폴더 생성 ON은 `<base>/YYYY/MM/YYYY-MM-DD.txt`, OFF는 `<base>/YYYY-MM-DD.txt`. 폴더가 존재하면 생성하지 않고 파일 append.
- 경로 후보 순서: (설정된 경로가 있다면) 설정경로 → `C:/noti-log` → `%LOCALAPPDATA%/NotiAutomation/logs`. 동일 경로 중복 시 한 번만 시도. 각 후보는 실제 생성·파일 append 테스트까지 수행해 성공 확인.
- **모든 경로 실패**: 로거는 비치명적 `LogWriteFailure` 상태 반환, UI 상단에 로그 기록 실패 경고, 표준 에러(가능하면)로 최소 표시. Jira 응답 상태를 실패로 바꾸지 않는다. 실패 로그를 무한 재호출하지 않는다.
- 핸들은 매 쓰기 닫고 과거 로그는 메모리에 상시 적재하지 않는다. 날짜/연도/월이 변경되면 동적으로 경로 계산. 자동 삭제 없음.
- `Path`로 경로 생성. 텍스트만 UTF-8, 바이너리 암호화/Excel에 encoding 인자 강요 금지.

## 2. 로그 내용과 비밀정보
- `[YYYY-MM-DD HH:mm:ss] [INFO|WARN|ERROR] [User: 이름(ID)] [모듈] 메시지` 형식. 비밀번호/API 토큰/Authorization 헤더/쿠키/암호화 키/원문 민감 데이터는 기록 금지.
- 정규식 마스킹에만 의존하지 말고 호출자가 허용된 구조화 필드만 넘기도록 설계하고, 최종 redact 필터 추가.
- 저장 실패, NoData 제외 건수·사유, 담당자 미매칭, 중복 경고, 생성성공/부분실패/UNKNOWN 이벤트 기록.

## 3. 설정
- 사용자별 설정 JSON은 `%LOCALAPPDATA%/NotiAutomation/config/`; `log_base_path`, `auto_year_month_folder`, `default_assignee_identity`, `epic_options`, `default_epic`, `default_watchers`, `jira_environment_status` 등. Jira 토큰은 설정 JSON에 저장하지 않는다.
- 설정 파일도 원자적 쓰기 및 파손 시 복구·오류 안내. 사용자 데이터 삭제/초기화 없이 onedir 버전 업그레이드할 수 있도록 schemaVersion 관리.
