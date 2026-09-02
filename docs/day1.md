# 📅 Day 1 — 2026-08-23

Day 1 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 1 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | #5~#8 서버 Hardware / iLO / NIC·Network Baseline 및 역할 매핑 완료, PXE Server .60 물리 연결 문제 후속 해결·Reachability 재검증 완료 |
| **B** | Automation / Troubleshooting | Ansible 대상 서버 구성 + QSFP/네트워크 Baseline 수동 검증 + 수동 Evidence 확보 |
| **C** | Platform / Visualization | `.206` / `.207` 서버 환경 구성 + FastAPI + SQLite + React Dashboard + GitHub 구성 |

---

# 👤 A — Day 1

> #5~#8 서버의 실제 하드웨어, iLO, 운영체제, 40GbE NIC 및 네트워크 상태를 점검하고 프로젝트의 Hardware / Infrastructure Baseline 확정

### Development / Infrastructure

- #5~#8 물리 서버의 iLO 접속, 전원 및 System Health 상태 확인
- 서버별 CPU, RAM, Storage, NIC 및 운영체제 정보 기록
- 서버별 Data Plane IP, NIC 이름, Gateway 및 VLAN 100 연결 상태 확인
- QSFP+ 40GbE NIC의 실제 장치 모델과 Kernel Driver 확인
- Mellanox `mlx4_core`, `mlx4_en` 모듈 및 ELRepo `kmod-mlx4` 설치 상태 확인
- Cisco Nexus L3 스위치의 VLAN 100, SVI 및 서버 연결 상태 점검
- ZT Storage PXE Server, Cisco SVI, Load Balancer 및 관리 인터페이스 연결 구조 확인
- iLO에서 Hardware / POST Evidence로 활용 가능한 항목 조사
- #5~#8 물리 서버의 프로젝트 역할 최종 매핑

### Implementation

- #5~#8 서버의 하드웨어 및 네트워크 정상 상태를 공통 Baseline으로 기록
- 서버별 Data Plane 구성 확인
  - #5: `192.168.100.205/24`
  - #6: `192.168.100.206/24`
  - #7: `192.168.100.207/24`
  - #8: `192.168.100.208/24`
  - Day 1 기준 Data NIC: `eno49`
  - Gateway / Cisco SVI: `192.168.100.200`
  - VLAN: `100`
- `lspci -nnk`와 `ethtool -i eno49`를 이용한 Mellanox NIC 및 `mlx4_en` Driver 확인
- `ethtool eno49`를 이용한 40Gbps, Full Duplex 및 Physical Link UP 상태 확인
- Rocky Linux 서버에서 ELRepo `kmod-mlx4` 설치 및 다음 모듈의 정상 로드 상태 확인
  - `mlx4_core`
  - `mlx4_en`
  - `mlx4_ib`
- #8 서버에서 별도의 강제 모듈 로드 설정 없이 NIC 장치 인식에 따라 `mlx4_en`이 정상 로드되는 상태를 Baseline으로 기록
- Cisco SVI `.200`과 LB Data Plane `.90`을 기준으로 Data Plane 통신 경로 확인
- iLO Hardware Evidence 후보 목록 정리
  - iLO Event Log
  - Integrated Management Log (IML)
  - POST Message
  - Diagnostics
  - Server Power
  - System Health
  - Remote Console
- 물리 서버 역할 최종 매핑
  - #5 / `dca-target01` → Target A
  - #6 / `dca-mgmt01` → Management
  - #7 / `dca-target02` → Target B
  - #8 / `dca-spare01` → Spare

### Test / Verification

- #5~#8 서버의 iLO 접속 및 HTML5 Remote Console 동작 확인
- 서버별 Power ON 및 System Health `OK` 확인
- CPU, RAM, Storage 및 NIC 장착 상태 확인
- 장착된 Memory의 `Good, In Use` 상태 확인
- Storage Controller, Logical Drive 및 Physical Drive 상태 확인
- `eno49`의 Data Plane IP 및 Gateway 설정 확인
- #5~#8 서버의 QSFP+ 40GbE Physical Link UP 확인
- #5~#8 서버에서 Cisco SVI `192.168.100.200` 통신 상태 확인
- #5~#8 서버에서 VLAN 100 Data Plane 통신 상태 확인
- LB Data Plane `192.168.100.90` 통신 확인
- OPNsense `.250` 및 Citrix NetScaler LOM `.251` 관리 인터페이스 확인
- iLO IML 및 POST 관련 기록 확인
- Remote Console을 통한 운영체제 Boot 상태 수동 확인
- 서버별 Hostname을 이용한 Management / Target A / Target B / Spare 역할 매핑 검증

### Baseline Result

| Server | Hostname | Operating System | Data Plane IP | Role |
| ------ | -------- | ---------------- | ------------- | ---- |
| #5 | `dca-target01` | Ubuntu 26.04 LTS | `192.168.100.205` | Target A |
| #6 | `dca-mgmt01` | Rocky Linux 10 | `192.168.100.206` | Management |
| #7 | `dca-target02` | Rocky Linux 10 | `192.168.100.207` | Target B |
| #8 | `dca-spare01` | Rocky Linux 10 | `192.168.100.208` | Spare |

### Issue & Resolution

#### 1. #8 Data NIC 자동 활성화 문제

- #8 서버에서 재부팅 후 `eno49` 연결이 자동 활성화되지 않는 현상 확인
- NetworkManager 연결 프로파일의 `connection.autoconnect` 값이 `no`로 설정된 것을 원인으로 확인
- `connection.autoconnect yes`로 수정
- `.208/24`, Gateway `.200` 설정이 NetworkManager 연결 프로파일에 저장된 상태 확인
- 재부팅 이후 Data NIC 및 Data Plane 설정 유지 상태 확인

**판정: NetworkManager Auto Connect 설정 수정 후 해결 완료**

#### 2. ZT Storage / PXE Server `.60` 통신 장애

- ZT Storage PXE Server `192.168.100.60` 통신 불가 현상 확인
- #8 서버의 `eno49` 40GbE Physical Link 및 `192.168.100.208/24` 설정 정상 확인
- #8 기준 Cisco SVI `.200` 및 LB Data Plane `.90` 통신 정상 상태에서 PXE Server `.60`만 통신 실패 확인
- `.208 → .60` Ping 실패 및 ARP Neighbor `FAILED` 확인
- 동일 VLAN 100 내부의 `.200`, `.90` 통신 정상 상태를 근거로 #8 NIC 및 Data Plane 전체 장애 가능성 배제
- Nexus에서 ZT Storage 연결 후보 포트 및 VLAN 100 상태 추가 점검
  - `Eth1/47`: QSFP-40G-CR4 Transceiver 인식 / Physical Link Down
  - `Eth1/48`: Transceiver 미인식
  - `.60` ARP 정보 미확인
  - Storage 측 MAC Address 미학습
- 초기 점검 결과 Server #8의 Boot Order, NIC Driver, 40GbE Link 및 VLAN 100보다 ZT Storage / PXE 측 물리 연결 구간으로 장애 범위 축소
- 후속 현장 점검에서 ZT Storage / PXE 측 물리 포트 연결 문제 확인
- 물리 포트 연결 수정 후 PXE Server `192.168.100.60` Reachability 정상화 확인

**판정: ZT Storage / PXE 측 물리 연결 문제 확인 및 후속 조치 후 해결 완료**

#### 3. Server #8 PXE 후속 검증

- 후속 단계에서 C 담당자의 Server #8 Rocky Linux 9.8 PXE 재설치 수행
- 재설치 이후 운영체제에서 기존 `eno49`가 아닌 `pxe0` 인터페이스명으로 40GbE NIC 인식 확인
- A 담당 영역에서 재설치된 Server #8의 NIC 및 Data Plane 상태 별도 검증
  - Interface: `pxe0`
  - IP: `192.168.100.208/24`
  - Driver: `mlx4_en`
  - Speed: `40000Mb/s`
  - Duplex: `Full`
  - Link detected: `yes`
  - PXE Server `192.168.100.60` Reachability: `PASS`
- PXE 재설치 작업과 재설치 이후 Hardware / Network 검증 작업을 담당 영역에 따라 분리 기록

**판정: Rocky Linux 9.8 PXE 재설치 이후 Server #8 40GbE NIC 및 PXE Server 통신 정상 상태 검증 완료**

### Day 1 Result

- #5~#8 서버의 Hardware / iLO / OS / NIC / Network Baseline 확정 완료
- 4대 물리 서버의 Management / Target A / Target B / Spare 역할 매핑 완료
- QSFP+ 40GbE NIC, `mlx4_en`, Data Plane 및 VLAN 100 동작 상태 검증 완료
- 세 파트가 공통으로 사용할 Hardware / POST Evidence 후보 항목 정리 완료
- #8 NetworkManager Auto Connect 문제 원인 확인 및 설정 수정 완료
- ZT Storage PXE Server `.60` 통신 장애를 Storage / PXE 측 물리 연결 구간으로 분리
- 후속 현장 점검을 통한 물리 포트 연결 문제 수정 및 `.60` Reachability 정상화 확인
- C 담당자의 Server #8 Rocky Linux 9.8 PXE 재설치 이후 A 담당 영역에서 `pxe0` 40Gbps Link 및 `.60` 통신 정상 상태 최종 검증

---

# 👤 B — Day 1

> 실제 물리 서버를 Ansible 관리 대상으로 구성하고, Data Plane·QSFP+ NIC·Driver·Kernel Module·Route·PXE 접근성을 수동 검증하여 Day 2 자동 진단의 Baseline을 준비

### Development / Infrastructure

- 실제 물리 서버 기반 Ansible Inventory 구성
  - `dca-target01`: `192.168.100.205` / Ubuntu / Managed Target
  - `dca-mgmt01`: `192.168.100.206` / Management + Ansible Controller
  - `dca-target02`: `192.168.100.207` / Rocky Linux / Managed Target
  - `dca-spare01`: `192.168.100.208` / Rocky Linux / Spare-Rebuild Target
- `dca-mgmt01 (.206)`을 기준으로 `.205`, `.207`, `.208`을 Ansible managed node로 구성
- Managed node SSH 연결 및 `ansible ping` 검증
- Managed node Ansible facts 수집
- iLO Management Plane과 Linux OS Data Plane 주소를 분리하여 관리
- 서버 OS 및 Ansible 통신은 Data Plane `192.168.100.0/24` 기준으로 구성

### Implementation

- Day 2 자동 진단에 사용할 공통 Baseline 및 변수 정의
  - Data Interface: `eno49`
  - Data Network: `192.168.100.0/24`
  - Gateway / SVI: `192.168.100.200`
  - PXE Server: `192.168.100.60`
  - Expected Driver: `mlx4_en`
  - Expected Kernel Modules: `mlx4_core`, `mlx4_en`
- 노드별 Data Plane IP, Gateway, Route, DNS 기준값을 Inventory / Vars에 반영
- Day 2 자동 진단에 사용할 NIC / QSFP+ / Driver / Kernel Module / Link State 검사 기준 정의
- 수동 검증 결과와 자동 진단 결과를 비교할 수 있도록 공통 Evidence 구조 준비
- Day 1 수동 Evidence를 `evidence/day1/manual/`에 저장하여 이후 자동 진단의 기준선으로 활용

### Test / Verification

- 3개 managed node의 `eno49` Data Plane 인터페이스 상태 확인
- Mellanox ConnectX-3 Pro QSFP+ NIC 인식 확인
- `mlx4_en` Driver 확인
- `mlx4_core`, `mlx4_en` Kernel Module 로드 확인
- QSFP+ Link 상태 검증
  - `Speed: 40000Mb/s`
  - `Duplex: Full`
  - `Link detected: yes`
- 노드별 Data Plane IP 정상 적용 확인
  - `dca-target01`: `192.168.100.205/24`
  - `dca-target02`: `192.168.100.207/24`
  - `dca-spare01`: `192.168.100.208/24`
- Route 및 Gateway `192.168.100.200` 정상 구성 확인
- 각 managed node에서 `192.168.100.200` Ping 성공 확인
- 각 managed node에서 PXE Server `192.168.100.60` Ping 실패 확인
- 3개 managed node의 Day 1 수동 Evidence 확보

### Issue & Resolution

- Data Gateway `192.168.100.200`은 정상 통신되었지만 PXE Server `192.168.100.60`은 3개 managed node 모두에서 `Destination Host Unreachable` 상태 확인
- NIC / Link / Data Plane 자체는 정상인 상태에서 PXE 경로만 분리된 장애로 판단하여 미해결 인프라 이슈로 Evidence에 기록
- PXE 접근 실패를 단순 네트워크 장애로 처리하지 않고, Day 2 자동 진단에서 별도 `pxe_reachability` 항목으로 판정할 수 있도록 진단 기준에 포함
- 하드웨어 관련 점검 항목이 분산되지 않도록 NIC / QSFP+ / Driver / Kernel Module / Link State를 Day 2 `network_diagnostic`에서 자동화할 수 있도록 Baseline을 통일

### Day 1 Outcome

Day 1에서는 각 managed node의 NIC, Driver, Kernel Module, Link, IP, Route, Gateway 및 PXE 접근성을 수동으로 검증하여 정상 Baseline을 확보했다. 이 Baseline을 기준으로 Day 2에서는 동일 항목을 Ansible Diagnostic Role로 자동화하고, 결과를 JSON Evidence로 표준화한다.

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
