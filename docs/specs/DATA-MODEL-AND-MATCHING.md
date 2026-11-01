# 로컬 데이터·담당자 매칭 상세 계약

## 1. 저장 스키마
PC별 `%LOCALAPPDATA%/NotiAutomation/data/`의 암호화 파일 2개: `grafana_db.dat`, `n3r_db.dat`. 내부 JSON은 UTF-8 논리 레코드이고 파일 자체는 암호문이다.
- Grafana 행: `id`, `service`, `assignee`, `alert_name`, `description` (Excel 네 열만 추출).
- N3R 행: `id`, `server_name`, `service_name`, `purpose`, `assignee` (Excel 네 열만 추출).
- 추가 애플리케이션 관리 메타: `schema_version`, `updated_at`, `source_file`(파일 이름만), `jira_account_id`(추후 별도 매핑 필요; 이름만으로 계정 확정 금지).
- 매핑 JSON 구조와 암호화 `.dat` 물리 저장은 다르며, 일반 사용자가 JSON을 텍스트 편집기로 바로 수정하는 방식을 제공하지 않는다. 관리자 인증 후 GUI CRUD.

## 2. Excel 가져오기
- `openpyxl` 읽기 전용으로 지정 헤더 검색. 유효 컬럼, 대소문자/공백/밑줄 차이, `description` 오타는 정규화하여 허용하되 서로 다른 컬럼이 동일 별칭에 충돌하면 오류 표시. 매크로 실행 금지.
- 헤더가 누락된 행/빈 담당자/빈 기본키는 오류 목록으로 보내고 정상 행은 선택적으로 가져온다. 원본 Excel을 변경하지 않는다.
- 정규화: 양쪽 공백 제거, 연속 공백 정리, 대소문자 비교용 casefold. **표시 및 Jira 내용에는 원본 값 보존**.
- Grafana 키 `(normalized_service, normalized_alert_name)`; N3R 키 `normalized_server_name`.
- 같은 키·같은 필드값: 중복 skip; 같은 키·다른 담당자/설명: `CONFLICT`로 별도 검토, 자동 덮어쓰기/건너뛰기 금지. 관리자 선택은 기존 유지/신규 반영/행별 취소.
- 수동 편집 내용이 Excel 재가져오기에 자동 덮어써지지 않도록 변경 원천과 timestamp 메타를 추적한다. 변경 후 재색인 및 원자적 암호화 파일 저장. 저장 실패 시 UI 성공 표시 금지.

## 3. 조회/담당자 지정
- N3R: `Target == server_name`. Grafana: 정제한 `Alert Name == alert_name` 후보 검색, 가능하면 서비스 맥락까지 함께 검증. 알람 원문에 서비스가 없어 여러 서비스에서 동일 Alert Name이 나온 경우 후보를 자동 한 건으로 확정하지 않고 **선택 필요** 반환.
- Grafana와 N3R 모두 단건 매칭/같은 담당자: 사용자에게 태그 선택 요청. 서로 다른 담당자: 담당자와 태그 함께 사용자 선택 필요.
- 어느 쪽도 매칭 안 됨: 출처 태그 없음, 설정된 기본 담당자를 사용하고 건별 안내 1회. 미리보기 수정 가능; 기본 담당자가 지정되지 않았거나 Jira 계정으로 해석되지 않으면 등록 차단.
- 담당자명은 Jira accountId/username이 아니다. 실제 Jira 배포유형에 맞춰 검색·식별자 확인 후 등록. 이름이 중복되면 직접 선택하거나 등록 차단.
- 소스 선택 및 담당자 선택 결과는 UI 검토 모델에 보존해 이후 알람 선택 변경시에도 섞이지 않게 한다.

## 4. 묶음 등록과 중복 키
- 개별 선택은 항상 알람당 독립 이슈. 묶음 선택은 `(담당자 동일) AND (태그 동일이고 null 아님) AND (Target 동일 OR 정제 Alert Name 동일) AND 묶음선택`의 네 조건.
- A와 B, B와 C가 호환되더라도 A와 C가 호환되지 않을 수 있으므로 **모든 쌍이 호환되는 그룹만 허용**. 입력 순서에 따른 분할은 사용자에게 표시; 그룹 결과를 미리보기에서 승인하고 정렬 순서를 변경하면 그룹 재계산 후 재확인.
- 서로 다른 담당자·태그의 알람은 자동으로 각각 별도 이슈. 사용자 지정한 담당자는 해당 알람의 Jira 작업에만 적용.
- 중복 키 `(normalized_Target | normalized_clean_alert_name | StartAt ISO datetime)`을 당일 인덱스와 비교. FingerPrint 단독 금지. UTC/로컬 시간 변환은 입력 타임존이 없으므로 시간 원문을 로컬 벽시계로 취급해 재해석하지 않는다.
