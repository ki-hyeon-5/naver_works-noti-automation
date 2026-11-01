# 00. 초기 환경 및 Git 세팅 가이드

Codex CLI 실행 전 Windows 11 환경에서 로컬 저장소와 Python 가상환경을 구축하는 순서입니다.

---

## Step 1. 프로젝트 폴더 생성 및 이동
```powershell
mkdir C:\workspace\noti-automation
cd C:\workspace\noti-automation
```

## Step 2. Git 저장소 초기화
```powershell
git init
git branch -M main

# 로컬 사용자 설정 (필요 시 수정)
git config user.name "NotiDev"
git config user.email "dev@local.internal"

# Windows 줄바꿈 및 한글 파일명 설정
git config core.autocrlf true
git config core.quotepath false
```

## Step 3. `.gitignore` 생성
민감 정보(API 토큰, 암호화 DB, 로그)가 커밋되지 않도록 프로젝트 루트에 `.gitignore`를 생성합니다.
```gitignore
# Python & venv
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/

# PyInstaller 빌드 산출물
build/
dist/
*.spec

# 로컬 영속 데이터 및 보안 파일 (절대 커밋 금지)
data/*.dat
data/*.enc
data/*.bak
config/accounts.dat
logs/
*.log
C_noti_log_test/
```

## Step 4. 가상환경 생성 및 패키지 설치
```powershell
python -m venv .venv
.\.venv\Scripts\activate

python -m pip install --upgrade pip
pip install PySide6 openpyxl cryptography requests pytest
pip freeze > requirements.txt
```

## Step 5. 설계 패키지 배치 및 최초 커밋
압축 해제된 설계 문서들을 프로젝트 루트에 배치한 후 첫 커밋을 생성합니다.
```powershell
git add README.md AGENTS.md 00-INITIAL-SETUP.md TASK_PROGRESS.md docs/ samples/ .gitignore
git commit -m "chore: initial project design package baseline"
```

## 개정: 실행/검증 및 자격증명 위생
- 공식 개발 진입점은 저장소 루트 `main.py`, 런타임 애플리케이션 부트스트랩은 `src/main.py`. onedir spec도 루트 `main.py` 지정.
- `.gitignore`에 `.venv/`, `__pycache__/`, `.pytest_cache/`, `build/`, `dist/`, `*.dat`, `*.bak`, `*.tmp`, `*.log`, `logs/`, `data/`, `config/`, `*.token`, `.env`, `!samples/*.json` 및 실제 알람 원본 파일 경로를 적용한다.
- 프로젝트의 docs/는 설계 산출물이고 이 ZIP에는 실제 완성된 Python 코드가 없다. pytest는 Task 진행 후 실행한다.
- 영속 설정/데이터 경로는 `%LOCALAPPDATA%\NotiAutomation` 기본. 사내 Jira 토큰과 실제 Excel 원본을 ZIP에 포함하지 않는다.
