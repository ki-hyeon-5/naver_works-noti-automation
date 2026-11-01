# 노티 자동화 (Noti Automation) — 최종 설계 명세 패키지

24/7 클라우드 모니터링/관제 근무자가 Grafana(및 추후 SCP) 알람을 복사해 붙여넣으면, 표준 노티 문구와 Jira 이슈 제목을 생성하고 담당자 매칭 및 Jira 이슈 등록을 지원하는 Windows 11 데스크톱 애플리케이션 설계 패키지입니다.

---

## 1. 프로젝트 핵심 개요
- **대상 환경:** Windows 11 (Intel i9-12900, 32GB RAM, 다중 모니터링 툴 상시 구동 환경). 낮은 CPU/RAM 점유율 유지.
- **개발 언어 및 UI:** Python 3.10+ / PySide6 (UI 레이어와 코어 비즈니스 로직 완전 분리).
- **배포 방식:** **PyInstaller onedir** 폴더 압축 배포 (`NotiAutomation.zip`). 무설치 포터블 실행 지원. 영속 데이터(`data/`, `config/`)는 실행 파일과 분리 보존.
- **성능 목표:** 복사/붙여넣기 후 전체 로컬 처리(파싱, 담당자 매칭, 중복 검사, 노티 생성) **목표 1초 / 최대 5초 이내** (20건 알람, 각 매핑 1,000행 기준 권장 벤치마크).
- **개발 범위:** **1차 Grafana 알람 우선 지원**. (SCP 알람은 추후 확장 대상이며 현재는 미지원 안내 표시).

---

## 2. 문서 체계 및 디렉터리 구조
Codex CLI는 아래 문서 체계를 Single Source of Truth로 참조하여 구현을 진행합니다.

```text
noti-automation-design/
├── README.md                          # 프로젝트 종합 개요 및 문서 색인
├── AGENTS.md                          # Codex CLI 개발·검증·유지보수 12대 골든 룰 및 지침
├── 00-INITIAL-SETUP.md                # Git 초기화, 가상환경, 필수 패키지 설치 가이드
├── TASK_PROGRESS.md                   # 8단계 Task 진행 현황 및 검증 기록판
├── docs/
│   ├── 01-REQUIREMENTS-SPEC.md        # 확정된 상세 비즈니스 요구사항 명세서
│   ├── 02-ARCHITECTURE-AND-FILE-MAP.md# 모듈 구조, 의존성 규칙, AI 파일 타겟 맵
│   ├── decisions/
│   │   ├── DECISIONS.md               # 확정된 아키텍처 및 업무 결정 기록 (ADR)
│   │   └── OPEN_QUESTIONS.md          # 미정 사항, 현장 검증 필요 항목 및 임시 완화책
│   ├── specs/
│   │   ├── PARSER-SPEC.md             # 13개 필드 앵커 파싱, 대괄호/소괄호 정제, NoData 처리
│   │   ├── DATA-MODEL-AND-MATCHING.md # Grafana/N3R 분리 암호화 DB, Excel Append, 매칭 규칙
│   │   ├── JIRA-INTEGRATION.md        # Jira REST API, 6단계 상태 머신, 부분 실패/중복 제어
│   │   ├── UI-WORKFLOW.md             # 확인 후 등록 단일 모드, 포커스/단축키, 미리보기/수정
│   │   ├── AUTH-AND-SECURITY.md       # 계정 관리, 위험 수용 정책(토큰 초기화), 암호화 키 관리
│   │   └── LOGGING-AND-SETTINGS.md    # 날짜별 TXT 로거, 3단계 Fallback, 경로 설정
│   ├── tests/
│   │   └── TEST-CASES.md              # 8대 Task별 입력-기대출력 골든 테스트 매트릭스
│   ├── tasks/                         # Task별 상세 작업 지시서 (TASK-01 ~ TASK-08)
│   │   ├── TASK-01.md
│   │   ├── TASK-02.md
│   │   ├── TASK-03.md
│   │   ├── TASK-04.md
│   │   ├── TASK-05.md
│   │   ├── TASK-06.md
│   │   ├── TASK-07.md
│   │   └── TASK-08.md
│   └── manual/
│       └── MANUAL-SPEC.md             # 오프라인 HTML 사용설명서/기능명세서 구조 설계
└── samples/
    ├── README.md                      # 샘플 데이터셋 설명
    ├── grafana-synthetic-input.txt    # 가상 알람 원문 테스트 픽스처
    └── expected-results.json          # 파싱 및 노티 생성 기대 결과 JSON
```

---

## 3. 구현 착수 가이드
1. `00-INITIAL-SETUP.md`를 참조하여 로컬 Git 및 Python 가상환경을 구축합니다.
2. `AGENTS.md`의 규칙에 따라 `TASK_PROGRESS.md`의 Task를 순서대로 진행합니다.

## 수정본(v2) 핵심 안내
- 이 패키지는 **개발용 설계 문서 패키지**이며, 실제 실행 코드 또는 사내 Jira 연동 검증 결과를 포함하지 않는다.
- 한 번에 `docs/tasks/TASK-XX.md` 하나씩 진행하고 각 Task의 테스트 ID를 `docs/tests/TEST-CASES.md`에서 찾는다.
- 각 PC 사용자별 영속 저장 기본 위치: `%LOCALAPPDATA%/NotiAutomation` (로그는 기본 `C:\noti-log`, 사용자 설정 가능).
- `samples/*`는 가상 데이터만 포함. 실제 Jira/Excel/알람을 Git에 넣지 않는다.
- 우선 현장 검증: 실제 Grafana 복사 원문, Jira Cloud/Data Center·필드/사용자 식별자, 개인 계정/DB 데이터 보안 정책.
