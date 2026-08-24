# 📅 Day 1 — 2026-08-24

Day 1 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 1 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | #8 서버(5,6,7 진행 예정) / iLO / NIC·네트워크 Baseline 구성 |
| **B** | - | 작성 예정 |
| **C** | Platform / Visualization | `.206` / `.207` 서버 환경 구성 + FastAPI + SQLite + React Dashboard + GitHub 구성 |

---

# 👤 A — Day 1

> #8 서버를 기준으로 하드웨어·iLO·NIC 및 네트워크 상태를 점검하고, 이후 장애 탐지·복구 자동화를 위한 정상 상태(Baseline)를 정리

### Development / Infrastructure
- #8 물리 서버를 Spare 서버로 선정하고 기본 하드웨어 및 네트워크 환경 점검
- iLO 관리망 접속 및 Remote Console 정상 동작 확인
- Rocky Linux의 40GbE NIC 인식을 위한 ELRepo 및 `kmod-mlx4` 설치 상태 확인
- `mlx4_core`, `mlx4_en` 등 Mellanox NIC 드라이버 모듈 로드 상태 확인
- Cisco Nexus L3 스위치의 VLAN 100 및 서버 연결 포트 상태 확인
- ZT Storage PXE Server 및 NetScaler/OPNsense 등 기존 인프라 연결 구조 확인

### Implementation
- #8 서버의 `mlx4_en` 기반 NIC 정상 인식 상태를 Baseline으로 기록
- Cisco Nexus VLAN 100의 MAC Address Table을 조회하여 #8 서버 NIC와 스위치 포트 매핑 확인
- Cisco SVI 및 관리망을 기준으로 서버 네트워크 통신 경로 확인
- iLO에서 향후 Hardware Evidence로 활용할 수 있는 항목 사전 조사
  - iLO Event Log
  - Integrated Management Log (IML)
  - Diagnostics
  - Server Power
  - Remote Console
- OPNsense 및 Citrix NetScaler 관리 인터페이스 접속 상태 확인

### Test / Verification
- #8 서버 iLO 접속 및 HTML5 Remote Console 동작 확인
- `kmod-mlx4`, `mlx4_en` 설치 및 로드 상태 확인
- #8 서버 NIC의 Link 상태 및 VLAN 100 통신 확인
- Cisco Nexus MAC Address Table에서 #8 서버 MAC 학습 상태 확인
- Cisco SVI 및 주요 관리 인터페이스 접근 상태 확인
- OPNsense `.250`, NetScaler LOM `.251` 관리 페이지 접속 확인

### Issue & Resolution
- ZT Storage PXE Server `.60` 통신 불가 현상 확인
- Nexus의 Storage 연결 포트 `Eth1/47`, `Eth1/48` 상태 점검
  - `Eth1/47`: QSFP-40G-CR4 Transceiver 인식 / Physical Link Down
  - `Eth1/48`: Transceiver 미인식
- VLAN 100 MAC Address Table에서 Storage 측 MAC이 학습되지 않는 상태 확인
- IP/라우팅보다 하위 계층인 Storage–Nexus 간 물리 링크 문제 가능성으로 원인 범위 축소
- 미해결 상태로 기록하고 추후 PXE 통신 복구 후 재검증 예정

---

# 👤 B — Day 1

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

# 👤 C — Day 1

## 1. Server Environment

Day 1 C 서버 구성 대상: `.206`, `.207`

| Server | Hostname | IP | 작업 |
|---|---|---|---|
| `.206` | `dca-mgmt01` | `192.168.100.206` | NIC / Data Plane 구성 및 SSH 확인 |
| `.207` | `dca-target02` | `192.168.100.207` | NIC / Data Plane 구성 및 `.206 → .207` SSH 확인 |

- ConnectX-3 Pro NIC용 `mlx4_core`, `mlx4_en` 구성
- NetworkManager 기반 네트워크 설정
- `.206 ↔ .207` 통신 확인

---

## 2. Development Environment

`.206` Management Server에서 Platform 개발환경 구성

```text
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

## 3. Project Structure

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

## 4. SQLite + SQLAlchemy

`backend/database.py` 구성

### 구성

- SQLite 연결
- SQLAlchemy Engine 구성
- `SessionLocal` 구성
- SQLAlchemy `Base` 구성
- SQLite Thread 설정

Database

```text
backend/rack.db
```

---

## 5. Database Models

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

## 6. FastAPI Backend

`backend/main.py` 구성

<img width="1919" height="1078" alt="스크린샷 2026-08-24 145740" src="https://github.com/user-attachments/assets/eced05ca-4d59-4fa1-a7dc-6b87db784ce3" />

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

Browser 및 Swagger UI 정상 접근 확인

---

## 7. CORS

React Frontend에서 FastAPI 호출 가능하도록 CORS 구성

허용 Origin

```text
http://192.168.100.206:5173
```

허용 항목

```text
Credentials
All Methods
All Headers
```

---

## 8. Server API

Dashboard 테스트용 `/servers` API 구성

등록 서버

```text
server-205
server-206
server-207
server-208
```

각 Server 정보

```text
server_id
hostname
role
ip
status
```

초기 Status

```text
UNKNOWN
```

> `/servers`의 4대 정보는 Dashboard/API 표시용 데이터이며 실제 Day 1 C 서버 구성 대상은 `.206`, `.207`임.

---

## 9. Mock Incident / Evidence

Frontend / API 테스트용 `backend/seed.py` 생성

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

Mock Scenario

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

## 10. API Test

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

## 11. Port 8000 충돌 해결

기존 Uvicorn Process가 Port 8000 사용 중이어서 충돌 발생

```text
Address already in use
```

Process 확인

```bash
sudo ss -ltnp | grep :8000
```

기존 Process 확인 및 정리 후 FastAPI 정상 재실행

---

## 12. React + Vite

`frontend/` React Project 구성

```text
React
Vite
Oxlint
```

Frontend 실행

```bash
npm run dev -- --host 0.0.0.0
```

접속

```text
http://192.168.100.206:5173
```

---

## 13. Rack Overview

`/servers` API 연동

프로젝트 대상 4대 Server Card 구성

### 표시 정보

```text
Hostname
Server ID
Role
Data Plane IP
Status
```

Dashboard 표시 대상

```text
dca-target01
dca-mgmt01
dca-target02
dca-spare01
```

---

## 14. Evidence Timeline

`/evidence` API 연동

`Promise.all()`을 이용한 `/servers`, `/evidence` 동시 조회

```text
/servers
/evidence
```

Evidence Card 표시 정보

```text
Layer
Check Name
Result
Incident ID
Server ID
Severity
Details
```

Mock Evidence 4개 정상 표시 확인

---

## 15. Evidence Status UI

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

## 16. Dashboard CSS

Vite 기본 CSS와 Dashboard CSS 충돌 발생

### 수정

- `index.css` 정리
- `App.css` 수정
- Dark Dashboard 구성
- Server Card Style 구성
- Evidence Card Style 구성
- Result별 Style 구성

최종 화면 구성

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

## 17. FastAPI ↔ React Integration

최종 데이터 흐름 연결 확인

<img width="1918" height="1079" alt="스크린샷 2026-08-24 145748" src="https://github.com/user-attachments/assets/3c7ff29a-14fa-4e3e-b7b3-88c1d121fd6e" />

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

## 18. Firewall

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

Backend / Frontend 별도 SSH Session에서 동시 실행 후 Browser 접근 확인

---

# 🌿 Git / GitHub

## 19. Local Git

프로젝트 Root에서 Git 초기화

```bash
git init
```

Branch

```text
main
```

---

## 20. `.gitignore`

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

Git 제외 대상

- Python Virtual Environment
- Python Cache
- SQLite Local DB
- Node Modules
- Frontend Build File
- Environment Secret
- Editor 설정

---

## 21. Initial Commit

Stage 및 상태 확인

```bash
git add .
git status
```

`.gitignore` 정상 적용 확인

최초 Commit

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

## 22. GitHub Repository

Organization

```text
MS-DCT
```

Repository

```text
who-broke-the-rack
```

Remote 연결

```bash
git remote add origin https://github.com/MS-DCT/who-broke-the-rack.git
```

Remote 등록 확인

```bash
git remote -v
```

---

## 23. GitHub Authentication

공유 서버에서 GitHub 인증을 위해 SSH Deploy Key 방식 우선 확인

Organization 정책

```text
Deploy keys
Disabled by MS-DCT
```

Deploy Key 사용 불가 확인

Fine-grained Personal Access Token 방식으로 변경

Permission

```text
Contents : Read and write
Metadata : Read-only
```

초기 인증 오류

```text
Invalid username or token.
Password authentication is not supported for Git operations.
```

GitHub Account Password 대신 Fine-grained PAT 사용 후 인증 해결

---

## 24. First Push

```bash
git push -u origin main
```

Push 성공

```text
[new branch] main -> main
branch 'main' set up to track 'origin/main'
```

Local `main` → `origin/main` Tracking 구성

GitHub 업로드 확인

```text
.gitignore
backend/
frontend/
```

---

## 25. Secret Check

Repository Public 전환 전 Secret 검사

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

Secret / Private Key Git 미포함 확인

---

## 26. Repository Public 전환

GitHub Repository Visibility 변경

```text
Private → Public
```

Repository 접근 확인

```text
https://github.com/MS-DCT/who-broke-the-rack
```

---

## 27. Documentation

- GitHub Root `README.md` 구성
- `docs/day1.md` 생성
- A / B / C Day 1 작업 기록 영역 구성
- C Day 1 실제 작업 내용 정리
- README 요약 / Day별 상세 Work Log 분리

---

# ✅ C — Day 1 Result

| Category | 완료 내용 |
|---|---|
| Server | `.206`, `.207` NIC / Data Plane / SSH 환경 구성 |
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
| Documentation | README + `docs/day1.md` |
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
