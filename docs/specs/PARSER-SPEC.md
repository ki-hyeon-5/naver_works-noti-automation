# Grafana 13필드 파싱·포맷 상세 계약

## 1. 입력 및 파싱 실패
- 1차는 Grafana. SCP는 미지원 안내만 제공하며 SCP 실제 샘플이 없으므로 임의 포맷 파서 구현 금지.
- 클립보드는 **탭/줄바꿈을 우선 보존**하고 공백/빈 줄만 정규화. 라벨 없는 다음 13개 순서를 처리: Status, Resolved, NoData, StartAt, Duration, Target, AlertName, Detail, InitValue, LastValue, Severity, LastActor, FingerPrint.
- `Firing`, datetime `YYYY-MM-DD HH:mm:ss`, Duration `4h 30m 29s` 등 교차 앵커를 이용해 개별 알람 후보 찾기. Detail이 다중 라인일 수 있으므로 고정 n번째 줄로 필드 결론 내리지 않는다.
- 완전히 합쳐진 단일 문자열에서 필드 경계가 증명 불가능하면 임의 분해하지 않고 `PARSE_AMBIGUOUS`와 원문 구간·수동 수정 필요 플래그 반환. 값 누락도 NoData로 간주하지 않는다.
- `NoData == NoData` 또는 `AlertName == DataSourceNoData` (대소문자 무시 정규화)일 때만 `is_no_data=True`, 검토/등록 제외. 단순 Detail `$xxx`는 제외 근거 아님.
- Target `-`/누락 → `[확인필요: 대상없음]`; 시간 포맷 및 실제 유효 날짜 오류 → `[확인필요: 시간오류]`; 둘 다 등록 전에 실제값으로 교정 필요.

## 2. 클러스터 및 템플릿
- Detail **시작 위치**에서 `namespace | meaningful detail` 형태이며 namespace가 `[A-Za-z0-9_-]{2,64}`일 때만 후보로 검출. 일반적인 pipe가 Detail 본문에 있거나 좌측 단순 영어 문장인 경우에는 클러스터로 자동 확정하지 않는다.
- 기계적으로 정규식만 충족한 경우라도 오탐 가능성이 있으므로 불확실 패턴은 `cluster_candidate`와 수동 확인 표시.
- 알람 본문:
```text
클러스터 : {namespace}      # 유효한 클러스터 있을 때만 출력

서비스명 : {Target}

장애현상 : {Detail에서 클러스터 접두어 제거한 값}

발생시간 : {YY-MM-DD HH:mm}
```
- 클러스터 없는 경우 `클러스터` 줄과 다음 빈 줄을 함께 제거. Duration, InitValue, LastValue, Severity는 본문 자동 출력에서 제외.
- 선행 `[Linux][CRITICAL]` 등 연속 bracket 토큰 제거, 후행 `(critical|warning|info|error|fatal|warn|crit)` 하나 제거(대소문자 무시). 중간 대괄호 유지.
- Jira Summary: 단건 `[247][TAG] Target, cleanName` (태그 없으면 `[247] Target, cleanName`); 묶음 동일 정제 AlertName `[247][TAG] firstTarget 외 N-1건, cleanName`; 묶음 서로 다른 `[247][TAG] firstTarget, firstCleanName 외 N-1건`.
- 묶음 본문은 각 알람 단건 본문을 빈 줄로 연결하고 데이터 누락 금지.

## 3. 출력 API 및 경고
`ParseBatchResult`는 `alarms`, `no_data_count`, `errors`를 별도로 제공. `ParsedAlarm`은 `raw_span`, `raw_fields`, `start_at`, `target`, `alert_name`, `detail`, `cluster`, `needs_review`, `warnings`, `fingerprint`를 포함.
- 파서 자체에 Jira 네트워크 호출·UI·담당자 조회 넣지 않는다. 정확한 로그에는 원문 대신 건수와 오류코드만 남긴다.
