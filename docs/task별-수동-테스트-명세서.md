# 노티 자동화 Task별 수동 테스트 명세서

## 사용 방법

- 이 문서는 **완성본 기준 검증 계획**이다. 현재 구현·통과 여부를 뜻하지 않는다. 각 Task가 끝날 때 해당 절차와 정상 판정 기준을 갱신하고, 최종 Windows 11 배포본에서 체크한다.
- 결과는 각 항목의 `[ ]`를 `[x]`로 바꾸고 실행 날짜, OS, 앱 버전/커밋, `통과·실패·미실행`, 실제 결과와 재현 절차를 별도 사본에 기록한다. 실패 항목은 기대 결과와 실제 결과를 함께 개발자에게 전달한다.
- 테스트에는 합성 계정·알람·매핑만 사용한다. 실제 토큰, 비밀번호, 사용자 데이터, 로그, `.dat`, `.bak`, Excel 파일을 Git에 올리지 않는다. 테스트용 데이터 폴더는 운영 데이터와 분리한다.
- Jira 항목은 명시된 **Mock**에서 먼저 확인한다. 실 Jira 생성은 별도 실환경 승인 후 테스트 프로젝트에서만 수행한다. Mock 통과를 실 Jira 연동 완료로 간주하지 않는다.
- Task 1의 core 로거는 macOS에서 일부 수동 확인이 가능하다. Task 3의 파서와 Task 5의 Mock GUI도 macOS에서 합성 입력으로 확인할 수 있다. Task 2의 Windows DPAPI와 Task 4의 관리자 Excel GUI는 최종 Windows 11 배포본에서 확인한다. Windows 기본 경로, `%LOCALAPPDATA%`, DPAPI·Credential Manager, `.exe` onedir 검증은 Windows 11에서만 판정한다.
- 각 Task의 자동 테스트·구현이 끝나면 해당 Task 변경만 명시적으로 스테이징·커밋·푸시한다. 체크리스트의 Windows 수동 검증은 최종 완성 후 사용자가 실행하고 결과를 제공한다. 실패 항목은 그 결과를 바탕으로 디버깅한다.
- `TASK_PROGRESS.md`의 `완료` 표시는 해당 Task의 자동 검증과 사용자 수동 검증 확인 후에만 변경한다. Windows 전용 항목이 미실행이면 이를 명시하고 완료로 표시하지 않는다.

## 공통 준비 및 기록

- [ ] 테스트 전 합성 데이터와 테스트용 저장 경로를 준비하고, 기존 데이터의 백업·복원 방법을 확인한다.
- [ ] 최종 배포본의 Windows 11 64bit 버전, 실행 파일 경로, 앱 버전/커밋, 테스트 날짜를 기록한다.
- [ ] 테스트 후 생성된 로그와 저장 파일에 실제 비밀값이나 개인정보가 없는지 확인한다.
- [ ] 각 Task의 대응 자동 테스트(`TASK_PROGRESS.md`의 명령)와 전체 `pytest` 결과를 기록한다.

## TASK-01 — 날짜별 TXT 로거 (TC-01A~E)

**현재 macOS에서 가능:** 지정한 임시 경로의 append·날짜 폴더·OFF 경로·폴백·오류 반환·마스킹을 core API로 확인할 수 있다. 설정 UI는 후속 Task 범위이다. **Windows에서 재검증:** `C:\noti-log`와 `%LOCALAPPDATA%` 실제 경로·권한.

- [ ] **01A** 지정 로그 경로와 연/월 폴더 ON으로 동일 이벤트를 두 번 기록한다. `<경로>/YYYY/MM/YYYY-MM-DD.txt`가 생기고 두 줄 모두 남는다. 각 줄은 `[날짜 시각] [LEVEL] [User: 이름(ID)] [모듈] 메시지` 형식이다.
- [ ] **01B** 연/월 폴더 OFF로 기록한다. `<경로>/YYYY-MM-DD.txt`가 생기고 연/월 하위 폴더에는 새 로그가 없다. 날짜 변경 후에는 새 날짜 파일에 기록된다.
- [ ] **01C** 사용자 경로를 쓰기 불가로 지정한다. Windows에서는 기본 경로 `C:\noti-log`를 먼저 시도하는지 확인한다. 기본 경로도 쓰기 불가이면 `%LOCALAPPDATA%\NotiAutomation\logs`에 기록되고 대체 경로 경고가 표시된다.
- [ ] **01D** 세 후보를 모두 쓰기 불가로 만든 테스트 환경에서 기록한다. 앱이 종료되지 않고 비영구 기록 실패 경고가 표시되며, 이미 받은 Jira 작업 결과는 바뀌지 않는다.
- [ ] **01E** 합성 토큰·비밀번호가 포함된 오류를 발생시킨다. TXT와 stderr에 비밀값 원문이 없고, 오류 종류만 남는다. 실제 자격증명은 사용하지 않는다.

### macOS에서 지금 실행할 수 있는 Task 1 간편 확인

프로젝트 루트에서 실행한다. 저장 경로는 macOS 임시 폴더이며 실행 후 자동 삭제된다. `uv`의 Python 3.10이 이미 설치된 현재 개발 환경에서는 추가 패키지가 필요 없다.

```bash
UV_CACHE_DIR=/private/tmp/noti-uv-cache uv run --offline --no-project --python 3.10 python - <<'PY'
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from src.core.constants import LogEvent, LogLevel
from src.core.logger import FileLogger
from src.core.models import LogActor, LogRecord, LogWriteStatus

with TemporaryDirectory() as directory:
    root = Path(directory)
    entry = LogRecord(LogLevel.INFO, LogActor('합성 사용자', 'tester'), 'manual', LogEvent.NODATA_EXCLUDED, count=1)
    common = dict(default_base_path=root / 'default', local_appdata=root / 'local', clock=lambda: datetime(2026, 11, 2, 9, 4, 5))
    folder = FileLogger(root / 'custom', True, **common)
    first, second = folder.write(entry), folder.write(entry)
    assert first.status is second.status is LogWriteStatus.WRITTEN
    assert first.path.read_text(encoding='utf-8').count('NoData 제외') == 2
    assert first.path.parts[-3:] == ('2026', '11', '2026-11-02.txt')
    flat = FileLogger(root / 'flat', False, **common).write(entry)
    assert flat.path == root / 'flat' / '2026-11-02.txt'
    print('Task 1 macOS 간편 확인 통과:', first.path.name, flat.path.name)
PY
```

이 확인은 01A·01B의 일부를 직접 보여준다. 01C~01E는 `tests/test_task1_logger.py`의 자동 테스트로 검증되며, Windows 실제 폴백과 UI 경고는 완성본에서 확인한다.

## TASK-02 — 계정·암호화 저장소 (TC-02A~E)

**실행 시점·환경:** 현재는 core 코드만 있으므로 macOS 수동 체크는 보류한다. 완성본 Windows 11에서 별도 테스트 계정·OS 사용자 프로필로 아래 순서대로 실행한다. ID만으로 재설정하는 정책은 계정 탈취·서비스 방해 위험이 남아 있다. 테스트 중에도 이 경고가 표시되어야 한다.

- [ ] **02A** 합성 계정으로 가입하고 로그인한다. 저장 파일에 비밀번호 평문이 없고, 잘못된 비밀번호는 거부된다.
- [ ] **02B** 계정 ID만으로 비밀번호를 재설정한다. 이전 비밀번호 로그인·기존 세션이 거부되고 개인 Jira 토큰이 초기화된다. 화면·문서에 미해결 위험 경고가 보인다.
- [ ] **02C** 테스트 환경에서 DPAPI 보호 토큰 파일 삭제 실패를 유발한다. 재설정 성공으로 표시하지 않고 실패 상태와 필요한 조치를 안내한다.
- [ ] **02D** 테스트용 `.dat` 사본의 암호문 1바이트를 변조해 읽는다. 인증 오류와 복구 안내가 보이고, 원본 데이터가 조용히 덮어써지지 않는다.
- [ ] **02E** 관리자 비밀번호 변경 전후 매핑 DB 읽기 정책을 확인한다. 다른 Windows 사용자 프로필에서 DPAPI 보호 데이터의 복구 제약을 확인하고 키 노출이 없는지 살핀다.

## TASK-03 — Grafana 파서·노티 포맷터 (TC-03A~F)

**실행 시점·환경:** macOS에서는 Task 5 Mock GUI에 `samples/grafana-synthetic-input.txt`를 붙여넣어 03A, 03C~03F의 화면 반응을 일부 확인할 수 있다. 로그 기록과 Windows 배포본 동작은 최종 Windows 11에서 판정한다. 실제 Jira 전송은 하지 않는다.

- [ ] **03A** 합성 입력 3건을 붙여넣는다. NoData 1건이 제외되고 정상 2건만 검토 목록과 노티에 남는다. 제외 건수·사유가 알림과 로그에 기록된다.
- [ ] **03B** `Detail`에 `$xxx`가 있으나 NoData 조건은 아닌 입력을 넣는다. 제외되지 않는다.
- [ ] **03C** `Target`이 `-`인 건과 `Start At=2026-02-30`인 건을 넣는다. 각각 확인필요 표시가 나오고 수정 전 등록이 차단된다.
- [ ] **03D** Detail 시작의 신뢰 가능한 `namespace | 내용`은 클러스터 줄로 분리된다. 본문 중간의 일반 `|`는 그대로 남는다.
- [ ] **03E** 선행 연속 `[]`와 후행 `(WARNING)`을 가진 Alert Name으로 제목을 만든다. 지정된 앞·뒤만 제거되고 내부 `[]`는 보존된다.
- [ ] **03F** 탭·빈 줄이 불규칙한 입력과 경계 없는 접합 문자열을 각각 넣는다. 확실한 건만 파싱하고 모호한 건은 `PARSE_AMBIGUOUS`로 표시한다.

## TASK-04 — Excel 매핑·묶음 계획 (TC-04A~G)

**실행 시점·환경:** 현재는 core 로직만 있으므로 macOS 수동 체크는 보류한다. 완성본 Windows 11의 관리자 Excel 가져오기·검토 화면에서 합성 데이터 전용 저장소를 사용한다. 아래 두 `.xlsx`를 직접 만들고 운영 Excel은 사용하지 않는다. N3R 열 `server_name, service_name, purpose, assignee`에 `bill-db-01, Billing, DB, 담당자A`와 `bill-db-02, Billing, DB, 담당자A`를 입력한다. Grafana 열 `service, assignee, alert_name, description`에 `Unrelated, 담당자C, Unrelated Alert, 가상 데이터`를 입력한다. 열 순서를 바꿔도 이름으로 찾아야 하며, 원본 파일은 변경되지 않아야 한다. 테스트 DB를 먼저 백업한다.

- [ ] **04A** 두 Excel을 가져온 뒤 `samples/grafana-synthetic-input.txt`를 붙여넣는다. NoData 제외 후 `bill-db-01`과 `bill-db-02`는 각각 `담당자A`·`N3R`로 매칭되고 `samples/expected-results.json`의 제목과 일치한다. 실제 Jira 계정 식별자가 미확정이면 등록 승인은 차단된다.
- [ ] **04B** 같은 N3R Excel을 다시 가져온다. 두 행이 중복으로 건너뛰어지고 저장 행 수는 2개 그대로다.
- [ ] **04C** `bill-db-01`의 담당자를 `담당자B`로 바꾼 별도 Excel을 가져온다. 충돌 1건이 표시되고 기존 `담당자A`는 관리자 선택 전까지 유지된다. `기존 유지`와 `신규 반영`을 각각 시험해 선택한 결과만 재시작 후 남는지 확인한다.
- [ ] **04D** Grafana에 동일 알람명을 추가해 양쪽 DB 매칭을 만든다. 서로 다른 담당자라면 담당자·출처 태그를 모두 고르기 전 승인 불가, 같은 담당자라도 출처 태그 선택 전 승인 불가다.
- [ ] **04E** 어느 DB에도 없는 Target/Alert Name을 넣는다. 유효한 기본 Jira 담당자가 있으면 건별 안내 1회와 수정 가능한 미리보기가 나오고 출처 태그는 없다. 기본 담당자가 없거나 Jira 계정 식별자가 없으면 이유를 표시하며 승인 차단된다.
- [ ] **04F** 묶음 모드에서 담당자·출처 태그가 동일한 두 알람의 Target만 같게, 다시 정제 Alert Name만 같게 만든다. 두 경우만 묶이고 담당자/태그가 다르거나 태그가 없는 건은 개별 이슈로 분리된다. 개별 모드에서는 항상 각각 독립 이슈다.
- [ ] **04G** 같은 담당자·태그의 A(`server-01`, `CPU high`), B(`server-01`, `Disk high`), C(`server-02`, `Disk high`)를 이 순서로 넣는다. 미리보기는 A+B와 C로 분할한다. 입력 순서를 바꾸면 그룹을 재계산하고 다시 확인을 요구한다.

## TASK-05 — 확인 후 등록 GUI (TC-05A~E)

**환경:** Mock Jira 모드와 합성 알람. 실서버 전송은 하지 않는다.

**실행:** 임시 Python 환경에서 `python main.py`를 실행하고, 매핑이 없는 합성 알람에는 확인된 테스트용 `Jira accountId`를 입력한 뒤 `수정·검토 저장`한다. 생성 키는 `MOCK-` 접두어인지 확인한다. 화면은 아직 실 Jira 연결을 제공하지 않는다.

**macOS 간편 확인:** 프로젝트 루트에서 아래 명령으로 Mock GUI를 실행한다. 앱 입력창에 `samples/grafana-synthetic-input.txt` 내용을 붙여넣고 `알람 분석`을 누른다. `입력 3건 · 검토 2건 · NoData 제외 1건`을 확인한다. 노티 편집창의 Enter는 줄바꿈만 해야 한다. 합성 `Jira accountId`를 입력하고 건별 `이 알람 검토 완료`를 체크한 뒤 `수정·검토 저장`과 `선택 등록`을 눌러 `MOCK-` 키를 확인한다. 실제 Jira 호출은 없다. Windows 포커스·배포본 동작은 최종 Windows 11에서 다시 판정한다.

```bash
UV_CACHE_DIR=/private/tmp/noti-uv-cache uv run --with PySide6-Essentials --with cryptography --with openpyxl python main.py
```

- [ ] **05A** 노티 편집창에 커서를 두고 Enter를 누른다. 줄바꿈만 일어나고 Jira 전송은 없다.
- [ ] **05B** 미검토 건에서 Ctrl+Enter를 누른다. 전송되지 않고 검토 필요 이유가 보인다.
- [ ] **05C** NoData와 정상 알람을 섞어 붙여넣는다. 제외 통계가 보이고 정상 건만 검토·등록 대상이 된다.
- [ ] **05D** 적격 2건과 부적격 1건으로 개별·전체 등록을 시험한다. 적격 2건은 별개 이슈 요청이며 부적격 건은 전송되지 않고 이유가 보인다.
- [ ] **05E** 같은 날짜·Target·정제 Alert Name·Start At 건을 다시 승인한다. 명시적 재등록 확인 전에는 API 호출이 없다. `UNKNOWN`·`PARTIAL_FAILED`는 별도 수동 대조 절차를 요구한다.
- [ ] **05F** 묶음 선택 후 A+B, C 분할을 확인하고 `묶음 구성 확인` 전에는 등록되지 않는지 확인한다. 구조화된 필드 정정 후 다시 검토한다.

## TASK-06 — 관리자·설정 GUI (TC-06A~C)

**환경:** 합성 관리자 계정과 별도 테스트 데이터. Windows 자격증명 저장은 Windows에서 판정한다.

- [ ] **06A** 관리자 인증 없이 Grafana/N3R 매핑을 수정·저장하려 한다. 거부되고 원본 데이터는 그대로다.
- [ ] **06B** 관리자 인증 후 두 탭에서 검색·추가·수정·삭제하고 재시작한다. 변경 사항이 암호화 저장되어 다시 표시된다.
- [ ] **06C** Excel 충돌 보고와 사용자별 로그 경로·폴더 ON/OFF·기본 담당자·에픽·참조자 설정의 재시작 유지 여부를 확인한다. 개인 토큰은 설정 JSON에 평문으로 남지 않는다.

## TASK-07 — Jira Mock 상태 머신·Windows 패키지 (TC-07A~G)

**환경:** Mock 응답 시나리오와 Windows 11 onedir 배포본. 실제 Jira 스키마 검증 전에는 Mock만 성공으로 표기한다.

- [ ] **07A** Mock create 201과 후속 담당자 지정 성공을 재현한다. 완료 상태가 표시되고 해당 건 create 호출은 1회다.
- [ ] **07B** create 성공 뒤 watcher 실패를 재현한다. 부분실패로 표시되고 생성된 이슈 키가 남으며 create 재호출은 없다.
- [ ] **07C** timeout/응답 유실을 재현한다. 생성여부불명으로 표시되고 자동 재전송되지 않으며 재시작 후에도 상태가 남는다.
- [ ] **07D** 401/403/400 및 지원하지 않는 필드를 각각 재현한다. 사용자에게 원인·조치가 표시되고 실제 API 성공으로 보이지 않는다.
- [ ] **07E** 테스트용 등록 요청 중 이슈 키 저장 전 강제 종료·재시작한다. 장부가 요청중/생성여부불명 상태를 복구하고 자동 중복 생성하지 않는다.
- [ ] **07F** 사용자별 기본 에픽, 복수 에픽, 기본·알람별 참조자를 설정한다. Mock payload에서 필드 값과 참조자 중복 제거를 확인한다.
- [ ] **07G** Windows 11에서 `NotiAutomation/` onedir의 `.exe`를 Python 미설치 환경에서 실행한다. 앱 재시작·배포 폴더 교체 후 데이터가 유지되고 외부 데이터 위치를 확인한다.

## TASK-08 — 오프라인 HTML 매뉴얼 (TC-08A~B)

- [ ] **08A** 네트워크를 끊고 완성본 매뉴얼을 `file://`로 연다. 외부 CDN/fetch 없이 8개 섹션, 목차, 검색, 사용 예시가 동작한다.
- [ ] **08B** 실제 GUI의 필드명·버튼명·경고 문구를 매뉴얼과 대조한다. 차이가 있으면 문서 갱신 후 문서 검사를 다시 실행한다.

## 최종 Windows 성능·운영 확인

- [ ] Windows 11 i9-12900, RAM 32GB, 메모리 사용 약 50% 조건에서 알람 20건과 Grafana/N3R 매핑 각 1,000행을 준비한다. 붙여넣기 완료부터 파싱·매칭·중복 검사·노티 표시 완료까지 반복 측정하고 최악값을 기록한다. 목표 1초, 최대 5초이며 Jira 네트워크 시간은 제외한다.
- [ ] 결과를 Task별로 개발자에게 전달한다. 실패 항목은 TC ID, 입력, 클릭 순서, 기대·실제 결과, 오류 문구, 앱 버전/커밋을 포함하되 비밀값은 제거한다.
