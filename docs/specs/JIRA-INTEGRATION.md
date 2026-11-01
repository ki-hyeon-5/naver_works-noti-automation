# Jira REST API 계약·실패 복구 설계

## 1. 지원 범위와 사전 게이트
- 실서버 종류(Jira Cloud/Data Center/Server), API 버전, 인증 방식, 이슈 유형, 프로젝트 키, reporter 필드 허용 여부, assignee 지정 권한/식별자, 에픽/parent/Epic Link, 참조자(Watcher vs customfield), 필수 커스텀 필드 확인 **전까지 실제 등록 금지**. Mock으로 기능 테스트.
- Cloud 및 Data Center는 사용자 식별자와 필드 구조가 다를 수 있으므로 API 응답의 create metadata/field 목록, 사용자 검색, 권한·프로젝트 설정 확인 결과를 기반으로 어댑터를 선택한다. 존재하지 않는 필드 ID를 하드코딩하지 않는다.
- 개별 사용자 Jira 토큰 사용, 인증 계정 본인이 Reporter가 되는지 현장 검증. 임의 Reporter 설정은 API/권한 가능 시에만.
- 기본 에픽 키와 선택 가능한 다수 에픽 키, 기본 참조자 목록과 알람별 참조자 목록을 별도 설정으로 보존. 합집합 중복 제거 후 API에 전송하되 실제 watcher API와 customfield 중 무엇인지 확인 필요.

## 2. 등록 인터페이스 (추상 계약)
```python
from dataclasses import dataclass
@dataclass
class IssueDraft:
    local_attempt_id: str
    alarm_keys: tuple[str, ...]
    summary: str
    description: str
    project_key: str
    issue_type: str
    epic_key: str | None
    assignee_identity: str | None
    reporter_identity: str | None
    default_references: tuple[str, ...]
    per_alarm_references: tuple[str, ...]

class JiraAdapter:
    def validate_environment(self) -> dict: ...
    def create_issue(self, draft: IssueDraft) -> dict: ...
    def assign_issue(self, issue_key: str, user_identity: str) -> dict: ...
    def attach_references(self, issue_key: str, user_identities: tuple[str, ...]) -> dict: ...
    def query_existing(self, local_attempt_id: str, alarm_keys: tuple[str, ...]) -> list[dict]: ...
```
- 위 인터페이스는 **설계 계약**이지 실제 사내 API 호출의 성공 보장이 아니다. `query_existing`는 Jira 검색 정책·필드 접근이 허용될 때만 사용하고 불가능하면 수동 대조한다.

## 3. 영속 상태 머신
`PENDING → REQUESTING → CREATED → DONE` 또는 `CREATED → PARTIAL_FAILED`; 요청 중 응답이 유실되면 `UNKNOWN`; 명확한 생성 거절은 `FAILED`. 후속 필드 수정 실패는 새 이슈 생성으로 재시도하지 않는다.
- Jira 생성 API를 호출하기 **전** `REQUESTING` 상태와 local_attempt_id, 알람키, 요청시각, 승인 사용자/요약(민감정보 최소화)을 로컬 장부에 원자적 기록.
- 생성 성공 즉시 Jira issue key/id 기록한 뒤 후속 지정 작업. 성공/부분실패/UNKNOWN을 재시작 후에도 로딩.
- `UNKNOWN` 은 조회 또는 사용자 수동 Jira 확인 전까지 동일 알람 재등록 불허. 사용자에게 조회 결과 및 수동 확인 확인란/로그를 제공해야 한다.
- 새 issue 생성 이후 후속 필드만 실패하면 `PARTIAL_FAILED`로 표시하고 가능한 경우 **기존 issue만 수정**하도록 안내. 자동으로 create_issue 재호출 금지.
- HTTP 400/401/403/429/5xx 구분, 응답 오류 내용의 토큰 마스킹, 명확한 거부와 불확실한 오류의 구분. 5xx라도 생성 여부가 불명확하면 UNKNOWN으로 취급.
- 네트워크 작업은 백그라운드, 중복 클릭을 막는 per-issue 실행 잠금 사용. 여러 PC가 독립 캐시를 쓰므로 전역적으로 중복 등록을 막는다고 보장하지 않는다.

## 4. 당일 중복 재등록
- Key: `Target | clean_alert_name | StartAt`. 메모리 set + `YYYY-MM-DD` 일별 파일 또는 경량 인덱스를 원자적으로 갱신.
- **경고 뒤 명시적 재등록 승인 가능**은 이미 확정. 단 `REQUESTING`/`UNKNOWN`/`PARTIAL_FAILED` 상태의 동일 요청은 단순 재등록 버튼으로 우회하면 안 되고 조회/수동 대조 후 별도의 복구 흐름을 거쳐야 한다.
- 일반 중복 허용 시 신규 local_attempt_id 발급하고 재승인 사유·사용자를 로그에 남긴다.
- 종료 후 다시 실행해도 직전 요청 장부에서 `UNKNOWN`, `CREATED`, `PARTIAL_FAILED` 상태를 복원한다.

## 5. 테스트 게이트
- Mock: 정상 생성·담당자 실패·참조자 실패·인증거부·timeout 전/후·500 응답·중복 클릭·프로세스 강제종료 후 복원·신규 재등록 승인 테스트.
- 실서버: 사내 Jira 환경/필드/권한 정보가 주어진 뒤 **사용자 명시 승인 후** 비운영 프로젝트 또는 테스트 이슈로만 통합 테스트. 테스트 토큰을 패키지에 포함하지 않는다.
