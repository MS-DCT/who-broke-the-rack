 # 📅 Day 1 — 2026-08-24

Day 1 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 1 작업 |
|---|---|---|
| **A** | - | 작성 예정 |
| **B** | - | 작성 예정 |
| **C** | Platform / Visualization | FastAPI + SQLite + React Dashboard + GitHub 구성 |

---

# 🅰️ A — Day 1

> 작업 내용 작성 예정

### Development / Infrastructure
- 

### Implementation
- 

### Test / Verification
- 

### Issue & Resolution
- 

---

# 🅱️ B — Day 1

> 작업 내용 작성 예정

### Development / Infrastructure
- 

### Implementation
- 

### Test / Verification
- 

### Issue & Resolution
- 

---

# 🅲 C — Day 1

## 1. Development Environment

Management Server `.206`에서 개발환경 구성

```text
Hostname : dca-mgmt01
IP       : 192.168.100.206

Python   : 3.12.9
Git      : 2.52.0
Node.js  : v22.23.1
npm      : 10.9.8
```

### 작업

- Python / Git 환경 확인
- Node.js 설치
- npm 설치
- Node.js / npm 정상 실행 확인

### Issue

Node.js 설치 후 OpenSSL / c-ares 관련 Library Symbol 오류 발생

### Resolution

```bash
sudo ldconfig
```

Linker Cache 갱신 후 Node.js / npm 정상 실행 확인

---

## 2. Project Structure

프로젝트 Root 구성

```text
~/who-broke-the-rack/
├── backend/
└── frontend/
```

Python Virtual Environment 구성

```bash
python3 -m venv venv
source venv/bin/activate
```

Backend Package 설치

```text
FastAPI
Uvicorn
SQLAlchemy
```

---

## 3. SQLite + SQLAlchemy

`backend/database.py` 구성

### 구성

- SQLite 연결
- SQLAlchemy Engine 구성
- `SessionLocal` 구성
- SQLAlchemy `Base` 구성

Database

```text
backend/rack.db
```

---

## 4. Database Models

`backend/models.py` 생성

### Incident

```text
incident_id
server_id
status
root_cause
started_at
ended_at
```

### Evidence

```text
incident_id
server_id
layer
check_name
result
severity
details
timestamp
```

### Action

```text
incident_id
action_type
status
details
timestamp
```

Table 생성 확인

```text
incidents
evidence
actions
```

---

## 5. FastAPI Backend

`backend/main.py` 구성

### API

| Method | Endpoint | 기능 |
|---|---|---|
| GET | `/` | Backend 상태 확인 |
| GET | `/servers` | Server 정보 조회 |
| GET | `/incidents` | Incident 조회 |
| GET | `/evidence` | Evidence 조회 |
| GET | `/actions` | Action 조회 |

FastAPI 실행

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

접속

```text
API     : http://192.168.100.206:8000
Swagger : http://192.168.100.206:8000/docs
```

---

## 6. CORS

React Frontend에서 FastAPI 호출 가능하도록 CORS 구성

```text
http://192.168.100.206:5173
```

허용

```text
Credentials
All Methods
All Headers
```

---

## 7. Server API

`/servers`에 4대 Server 정보 구성

```text
server-205
server-206
server-207
server-208
```

Server 정보

```text
server_id
hostname
role
ip
status
```

초기 상태

```text
UNKNOWN
```

---

## 8. Mock Incident / Evidence

`backend/seed.py` 생성

### Mock Incident

```text
Incident ID : MOCK-001
Server      : server-207
Status      : INVESTIGATING
```

### Mock Evidence

| Layer | Check | Result | Severity |
|---|---|---|---|
| HARDWARE | `system_health` | PASS | INFO |
| POST_BOOT | `boot_status` | PASS | INFO |
| NETWORK | `gateway_reachability` | FAIL | HIGH |
| OS | `ssh_reachability` | UNKNOWN | WARN |

Scenario

```text
HARDWARE
  PASS
   ↓
POST_BOOT
  PASS
   ↓
NETWORK
  FAIL
   ↓
OS
 UNKNOWN
```

### 중복 방지

- 기존 `MOCK-001` 존재 여부 확인
- 기존 Evidence 존재 여부 확인
- 기존 데이터 존재 시 추가 생성 제외

---

## 9. API Test

테스트

```bash
curl http://127.0.0.1:8000/incidents
curl http://127.0.0.1:8000/evidence
curl http://127.0.0.1:8000/actions
```

결과

```text
MOCK-001 Incident 정상 반환
Mock Evidence 4개 정상 반환
Actions 빈 배열 정상 반환
```

---

## 10. Port 8000 충돌 해결

기존 Uvicorn Process로 Port 충돌 발생

```text
Address already in use
```

Process 확인

```bash
sudo ss -ltnp | grep :8000
```

기존 Process 정리 후 FastAPI 재실행

---

## 11. React + Vite

`frontend/` React Project 구성

```text
React
Vite
Oxlint
```

실행

```bash
npm run dev -- --host 0.0.0.0
```

접속

```text
http://192.168.100.206:5173
```

---

## 12. Rack Overview

`/servers` API 연동

4대 Server Card 구성

### 표시 정보

```text
Hostname
Server ID
Role
Data Plane IP
Status
```

Server

```text
dca-target01
dca-mgmt01
dca-target02
dca-spare01
```

---

## 13. Evidence Timeline

`/evidence` API 연동

`Promise.all()`을 이용하여 다음 API 동시 조회

```text
/servers
/evidence
```

Evidence Card 구성

```text
Layer
Check Name
Result
Incident ID
Server ID
Severity
Details
```

---

## 14. Evidence Status UI

Result별 UI 구성

```text
PASS
FAIL
WARN
UNKNOWN
```

Dashboard 결과

```text
HARDWARE  → PASS
POST_BOOT → PASS
NETWORK   → FAIL
OS        → UNKNOWN
```

---

## 15. Dashboard CSS

Vite 기본 CSS와 Dashboard CSS 충돌 발생

### 수정

- `index.css` 정리
- `App.css` 수정
- Dark Dashboard 구성
- Server Card Style 구성
- Evidence Card Style 구성
- Result별 Style 구성

최종 화면

```text
WHO BROKE THE RACK?

Rack Overview
 ├─ dca-target01
 ├─ dca-mgmt01
 ├─ dca-target02
 └─ dca-spare01

Evidence Timeline
 ├─ HARDWARE  / PASS
 ├─ POST_BOOT / PASS
 ├─ NETWORK   / FAIL
 └─ OS        / UNKNOWN
```

---

## 16. FastAPI ↔ React

최종 데이터 흐름 연결 확인

```text
SQLite
   ↓
FastAPI
   ↓
HTTP API
   ↓
React
   ↓
Dashboard
```

DB → Backend API → Frontend Dashboard 연동 확인

---

## 17. Firewall

FastAPI Port

```text
8000/tcp
```

Vite Port

```text
5173/tcp
```

확인

```bash
sudo firewall-cmd --list-ports
```

결과

```text
5173/tcp
8000/tcp
```

Backend / Frontend 별도 SSH Session 실행 후 Browser 접근 확인

---

# 🌿 Git / GitHub

## 18. Local Git

프로젝트 Root에서 Git 초기화

```bash
git init
```

Branch

```text
main
```

---

## 19. `.gitignore`

Root `.gitignore` 구성

```text
backend/venv/
backend/__pycache__/
*.pyc

backend/rack.db

frontend/node_modules/
frontend/dist/

.env
*.env

.vscode/
.DS_Store
```

Git 제외

- Virtual Environment
- Python Cache
- SQLite DB
- Node Modules
- Build File
- Environment Secret
- Editor 설정

---

## 20. Initial Commit

Stage

```bash
git add .
git status
```

`.gitignore` 정상 적용 확인

Git Author 설정 후 최초 Commit 생성

```text
60449ee
feat: initialize platform dashboard and evidence API
```

결과

```text
21 files changed
1967 insertions
```

---

## 21. GitHub Repository

Organization

```text
MS-DCT
```

Repository

```text
who-broke-the-rack
```

Remote

```bash
git remote add origin https://github.com/MS-DCT/who-broke-the-rack.git
```

---

## 22. GitHub Authentication

공유 서버 인증을 위해 Deploy Key 방식 우선 확인

GitHub Organization 정책

```text
Deploy keys
Disabled by MS-DCT
```

Deploy Key 사용 불가 확인

Fine-grained PAT 방식으로 변경

Permission

```text
Contents : Read and write
Metadata : Read-only
```

최초 인증 오류

```text
Invalid username or token.
Password authentication is not supported for Git operations.
```

GitHub Account Password 대신 PAT 사용 후 인증 해결

---

## 23. First Push

```bash
git push -u origin main
```

Push 성공

```text
[new branch] main -> main
branch 'main' set up to track 'origin/main'
```

GitHub에서 다음 구조 확인

```text
.gitignore
backend/
frontend/
```

---

## 24. Secret Check

Public 전환 전 Secret 검사

```bash
git grep -inE 'password|passwd|secret|token|private.?key|BEGIN.*PRIVATE'
```

결과

```text
.gitignore:13:# Secrets
```

Private Key 파일 검사

```bash
git ls-files | grep -E '\.pem$|\.key$|id_rsa|id_ed25519|who_broke_the_rack'
```

결과

```text
출력 없음
```

실제 Secret / Private Key Git 미포함 확인

---

## 25. Repository Public 전환

GitHub Repository Visibility 변경

```text
Private → Public
```

Repository 접근 확인

```text
https://github.com/MS-DCT/who-broke-the-rack
```

---

# ✅ C — Day 1 Result

| Category | 완료 내용 |
|---|---|
| Development | Python / Node.js / npm 개발환경 구성 |
| Backend | FastAPI + SQLite + SQLAlchemy |
| Database | Incident / Evidence / Action |
| API | `/servers`, `/incidents`, `/evidence`, `/actions` |
| Mock Data | `MOCK-001` + Evidence 4개 |
| Frontend | React + Vite |
| Dashboard | Rack Overview + Evidence Timeline |
| Integration | FastAPI ↔ React |
| Runtime | `8000/tcp`, `5173/tcp` |
| Git | Local Repository + `.gitignore` |
| GitHub | Organization Repository + `main` Push |
| Security | Secret / Private Key 검사 |
| Repository | Public 전환 |

---

## Day 1 Final Flow

```text
SQLite
 │
 ├─ Incident
 ├─ Evidence
 └─ Action
 │
 ▼
FastAPI :8000
 │
 ├─ /servers
 ├─ /incidents
 ├─ /evidence
 └─ /actions
 │
 ▼
React / Vite :5173
 │
 ├─ Rack Overview
 └─ Evidence Timeline
 │
 ▼
Web Dashboard
```

---

## C — Initial Commit

```text
60449ee
feat: initialize platform dashboard and evidence API
```

## Repository

```text
https://github.com/MS-DCT/who-broke-the-rack
```
