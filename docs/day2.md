# 📅 Day 2 — 2026-08-24

Day 2 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 2 작업 |
|---|---|---|
| **A** | - | 작성 예정 |
| **B** | Automation / Troubleshooting | Network/OS/Service 자동 진단 Role 구현 + 상태 판정 + Evidence JSON 자동 생성 |
| **C** | Platform / Visualization | Diagnostic Evidence DB 연동 + Suspect Card + Evidence Timeline 구현 |

---

# 👤 A — Day 2

> 작성 예정

---

# 👤 B — Day 2

> Day 1에서 수동으로 확인한 서버 Baseline을 기준으로 Network / OS / Service 상태를 Ansible로 자동 진단하고, 각 결과를 `PASS / WARN / FAIL / UNKNOWN / SKIP` 상태와 JSON Evidence로 표준화

### Development / Infrastructure

- Day 1 수동 점검 항목을 자동화하기 위해 Ansible Diagnostic Role을 3개 영역으로 분리
  - `network_diagnostic`: NIC, Data Plane, Route, PXE 및 Port Reachability 진단
  - `os_diagnostic`: systemd, filesystem, firewall, CPU / Memory 진단
  - `service_diagnostic`: process, listening port, HTTP health 진단
- Ansible Controller인 `dca-mgmt01 (.206)`에서 3개 managed node를 대상으로 진단 수행
  - `dca-target01 (.205)`
  - `dca-target02 (.207)`
  - `dca-spare01 (.208)`
- Diagnostic Playbook은 서버 설정을 변경하지 않는 read-only 방식으로 구성
  - 진단 명령은 가능한 한 `changed_when: false` 적용
  - 개별 진단 실패가 Ansible Play 자체의 실패로 이어지지 않도록 구성
- 진단 결과 상태를 다음 5개로 표준화
  - `PASS`: 정상 상태
  - `WARN`: 현재 서비스는 가능하지만 이상 또는 위험 요소 존재
  - `FAIL`: Critical 장애 또는 해당 기능 수행 불가
  - `UNKNOWN`: 권한 부족 또는 조회 실패로 상태 판단 불가
  - `SKIP`: 검사 대상이 설정되지 않았거나 해당 서비스에 적용되지 않는 검사
- Category 및 Host 전체 상태 집계 우선순위 적용
  - `FAIL > UNKNOWN > WARN > PASS > SKIP`
- SSH를 초기 Baseline Service로 지정하여 실제 process / listening port / TCP reachability 검증 수행

### Implementation

#### 1. Network Diagnostic

`network_diagnostic` Role에서 물리 NIC부터 Data Plane, 외부 의존성까지 단계별로 진단하도록 구성

- NIC Link 상태
  - 대상 인터페이스 `eno49` 존재 여부 및 UP 상태 확인
- QSFP+ NIC 존재 여부
  - Mellanox ConnectX-3 Pro NIC 인식 여부 확인
- Kernel Driver
  - Expected Driver인 `mlx4_en` 적용 여부 확인
- Kernel Module
  - `mlx4_core`
  - `mlx4_en`
  - 필수 Module 로드 여부 확인
- Link State
  - 물리 Link Up / Down 확인
- IP Address
  - Inventory에 정의한 노드별 Data Plane IP와 실제 IP 비교
- Gateway
  - Data Gateway / SVI `192.168.100.200` 경로 확인
- Route
  - Default Route 및 Data Plane Route 확인
- DNS
  - Resolver 설정 여부 확인
- PXE Reachability
  - PXE Server `192.168.100.60`에 ICMP 통신 가능한지 확인
- TCP Port Reachability
  - 각 managed node에서 `.205`, `.207`, `.208`의 TCP 22번 포트 접근 가능 여부 확인

단순 Ping 성공 여부만 확인하는 것이 아니라,
`NIC → IP → Route → Gateway → Port` 순서로 진단할 수 있도록 구성하여 이후 장애 원인 분리에 활용할 수 있도록 함.

#### 2. OS Diagnostic

`os_diagnostic` Role에서 서버 운영 상태와 OS 수준의 이상 여부를 확인

- systemd failed unit 확인
- Filesystem 사용량 확인
- Firewall 상태 확인
- CPU Load 확인
- Memory 사용 상태 확인

systemd는 모든 failed unit을 동일하게 장애로 처리하지 않고 중요도에 따라 분리

- Critical Unit 실패 → `FAIL`
- Non-critical Unit 실패 → `WARN`
- Failed Unit 없음 → `PASS`
- 진단 자체 실패 → `UNKNOWN`

Critical Unit 목록은 `group_vars/all.yml`에서 변경 가능하도록 변수화하여,
향후 Docker / containerd / kubelet 등 프로젝트 핵심 서비스가 추가될 경우 확장 가능하도록 구성

#### 3. Service Diagnostic

`service_diagnostic` Role에서 애플리케이션 또는 시스템 서비스 상태를 다음 단계로 확인

1. Process가 실제 실행 중인지 확인
2. 지정된 Port가 LISTEN 상태인지 확인
3. HTTP 서비스의 경우 Health Endpoint 응답 확인

초기 Baseline Service는 SSH로 설정

- Process: `sshd`
- Port: `22`

현재 실제 HTTP Application은 아직 배포되지 않았기 때문에
HTTP Health Check 로직은 구현하되 Day 2에서는 `SKIP` 처리

추후 실제 DC:SURVIVE API가 배포되면 `/health` Endpoint를 연결하여
Process → Port → HTTP Response까지 이어지는 서비스 진단으로 확장 가능

#### 4. Evidence JSON

각 managed node의 진단 결과를 Host별 JSON Evidence로 자동 생성

- `evidence/day2/diagnostic/dca-target01.json`
- `evidence/day2/diagnostic/dca-target02.json`
- `evidence/day2/diagnostic/dca-spare01.json`

Evidence에는 다음 정보가 포함됨

- Host
- Ansible Host IP
- 생성 시각
- Network / OS / Service Category
- 개별 Check Name
- Check Detail
- `PASS / WARN / FAIL / UNKNOWN / SKIP`
- Category 상태
- Host 전체 상태
- Spare / Rebuild 역할 여부

이를 통해 터미널 출력에만 의존하지 않고 이후 Rule Engine, Recovery Logic, Dashboard에서 재사용할 수 있는 구조로 표준화

### Test / Verification

#### SSH Baseline Service 검증

3개 managed node 모두 다음 항목 정상 확인

- `sshd` Process → `PASS`
- TCP `22` Listening Port → `PASS`
- 노드 간 TCP `22` Reachability → `PASS`

즉,

- 서버 프로세스가 실행 중인지
- 실제 포트가 열려 있는지
- 다른 노드에서 해당 포트까지 접근 가능한지

를 각각 분리하여 자동 확인 가능함을 검증

HTTP Health Check는 실제 HTTP Application이 아직 배포되지 않았으므로 `SKIP`

#### PXE Reachability 검증

Day 1 수동 Evidence에서 확인된 실제 장애인 PXE Server `192.168.100.60` unreachable 상태를 자동 진단에 반영

- `dca-target01` → `WARN`
- `dca-target02` → `WARN`
- `dca-spare01` → `FAIL`

같은 PXE 장애라도 서버 역할에 따라 다르게 판정

- Target Server
  - 현재 서비스는 수행 가능
  - 단, 재설치 / Rebuild 경로 사용 불가
  - 따라서 `WARN`
- Spare / Rebuild Target
  - PXE가 동작하지 않으면 Spare Rebuild 역할 자체를 수행할 수 없음
  - 따라서 `FAIL`

이를 통해 단순 Up / Down 판정이 아니라 서버 Role과 복구 가능성을 포함한 상태 판정 구현

#### OS 상태 검증

`dca-target01`

- `systemd-networkd-wait-online.service` failed 상태 확인
- 현재 NIC / IP / Gateway 통신은 정상이며 Critical Service가 아니므로 `WARN` 처리
- UFW 상태 `inactive` 확인 → `WARN`

`dca-target02`

- Critical systemd failed unit 없음 → `PASS`
- firewalld `active` → `PASS`

`dca-spare01`

- Critical systemd failed unit 없음 → `PASS`
- firewalld `active` → `PASS`

### Issue & Resolution

#### 1. Ubuntu Firewall 조회 시 Ansible Become Timeout

**Issue**

Ubuntu `dca-target01`에서 firewall 상태 조회를 위해 Ansible `become: true`를 사용했을 때 다음 오류 발생

- Privilege escalation prompt timeout
- Ansible Play 자체가 `failed=1`로 종료

**Resolution**

- 전체 Playbook의 `become` 사용 제거
- Root 권한이 필요한 UFW 조회에만 최소 권한 적용
- `sudo -n` 기반 read-only 조회 방식으로 변경
- 권한 상승이 불가능한 경우 Play 자체를 실패시키지 않고 `UNKNOWN`으로 기록하도록 수정

이후 필요한 UFW status 조회만 NOPASSWD로 허용하여 정상 상태 조회 가능하도록 구성

#### 2. Rocky Linux Firewall 조회 시 Polkit Authorization 오류

**Issue**

일반 계정에서 `firewall-cmd --state` 실행 시 Polkit Authorization 오류 발생

**Resolution**

Firewall 상태 확인 목적에 불필요한 권한 상승을 제거하고

`systemctl is-active firewalld`

기반으로 변경

- active → `PASS`
- inactive → `WARN`
- 조회 실패 → `UNKNOWN`

#### 3. 모든 systemd Failed Unit이 Host FAIL로 처리되는 문제

**Issue**

초기 구현에서는 `systemctl --failed` 결과가 하나라도 존재하면 OS 전체가 `FAIL`로 판정됨

예:
- `systemd-networkd-wait-online.service`
- `dnf-makecache.service`

현재 서비스 운영에 Critical하지 않은 Unit까지 장애로 처리되는 문제 발생

**Resolution**

Critical / Non-critical Unit을 구분

- Critical → `FAIL`
- Non-critical → `WARN`
- 없음 → `PASS`

Critical Unit 목록을 변수화하여 향후 프로젝트 핵심 서비스 추가 시 확장 가능하도록 개선

#### 4. PXE 장애가 자동 Evidence에 포함되지 않던 문제

**Issue**

Day 1에서 `192.168.100.60` unreachable을 수동으로 확인했지만 초기 자동 Evidence에는 PXE 상태가 포함되지 않음

**Resolution**

`pxe_reachability` Check를 추가하고 서버 역할 기반 정책 적용

- Target → `WARN`
- Spare / Rebuild → `FAIL`

이를 통해 단순 네트워크 상태뿐 아니라 Recovery Capability 저하까지 Evidence에 반영

#### 5. Port / Service 진단이 SKIP 처리되는 문제

**Issue**

초기에는 `diagnostic_port_targets`, `diagnostic_services` 대상이 설정되지 않아 실제 진단 없이 `SKIP` 처리됨

**Resolution**

SSH를 Baseline Service로 지정

- `sshd` Process
- TCP `22` Listening
- `.205 / .207 / .208:22` Port Reachability

를 실제 진단 대상으로 설정하여 Role 동작 검증 완료

### Day 2 Outcome

Day 2에서는 Day 1에서 수동으로 확인했던 물리 NIC, Driver, Kernel Module, Link, IP, Route, Gateway, PXE 상태를 Ansible Diagnostic Role로 자동화했다.

또한 OS와 Service 상태까지 진단 범위를 확장하여 단순 서버 Up / Down이 아니라

`Network → OS → Service`

계층별 상태를 구분할 수 있도록 구성했다.

진단 결과는 `PASS / WARN / FAIL / UNKNOWN / SKIP`으로 표준화하고 Host별 JSON Evidence로 저장하여, 이후 Day 3에서 구현할 Diagnosis Decision Tree와 Rule Engine이 장애 원인 및 Recovery Action을 선택할 수 있는 입력 데이터 기반을 마련했다.

---

👤 C — Day 2

담당: Platform / Visualization

주요 작업
- Diagnostic Evidence JSON → SQLite DB 연동
- 실제 Evidence FastAPI 연동 확인
- 최신 Evidence 재수집 시 기존 데이터 갱신 처리
- PASS / WARN / FAIL / UNKNOWN / SKIP 상태 처리
- React Suspect Card 구현
- 실제 Incident 기준 Evidence Timeline 구현
- 최신 B Diagnostic Evidence 반영

1. Day 2 Evidence Integration

B가 생성한 Ansible Diagnostic JSON을 Platform에서 사용할 수 있도록 Evidence Import 구조 구성

연동 대상
evidence/day2/diagnostic/dca-target02.json

Platform 대상
Host: dca-target02
Server ID: server-207
Incident ID: DAY2-207

전체 데이터 흐름

Ansible Diagnostic
↓
Diagnostic JSON
↓
import_day2.py
↓
SQLite
↓
FastAPI /evidence
↓
React Dashboard


2. Evidence Importer 구현

backend/import_day2.py 구현

Diagnostic JSON의 데이터를 기존 Evidence DB 구조에 맞춰 변환

JSON → DB Mapping

category → layer
name → check_name
status → result
detail → details
generated_at → timestamp

Evidence DB 구조

incident_id
server_id
layer
check_name
result
severity
details
timestamp


3. Diagnostic Status 처리

B Diagnostic에서 사용하는 상태값을 Platform에서도 동일하게 유지

PASS
WARN
FAIL
UNKNOWN
SKIP

초기 구현에서는 SKIP을 UNKNOWN으로 변환했으나,
최신 Diagnostic Schema에 맞춰 SKIP을 별도 상태로 유지하도록 수정

Severity Mapping

PASS → INFO
WARN → WARN
FAIL → HIGH
UNKNOWN → WARN
SKIP → INFO


4. 최신 Evidence 갱신 처리

초기 Import에서는 동일한 Evidence가 존재하면 중복 삽입을 제외하도록 구성

하지만 Diagnostic이 재실행되면서 기존 Check 결과가 변경되는 경우
기존 DB 값이 갱신되지 않는 문제 확인

실제 변경 사례

port_reachability
SKIP → PASS

firewall_state
UNKNOWN → PASS

Service Diagnostic
process → PASS
listening_port → PASS
http_health → SKIP

해결

기존 DAY2-207 Evidence 삭제
↓
최신 Diagnostic JSON Parsing
↓
최신 Evidence 재저장

결과

기존 Evidence: 17개
최신 Evidence: 19개


5. FastAPI Evidence 연동 확인

SQLite에 저장된 실제 Diagnostic Evidence가 FastAPI를 통해 정상 조회되는지 확인

API
GET /evidence

확인 결과

Incident ID: DAY2-207
Server ID: server-207
NETWORK / OS / SERVICE Evidence 정상 반환
최신 Evidence 19개 정상 반환


6. Suspect Card 구현

React Dashboard에 실제 Evidence를 기반으로 상태를 표시하는 Suspect Card 추가

구성 영역

Power
Memory
Storage
Network
OS
Service

상태

조사 전
정상
의심

상태 판정 기준

FAIL 존재 → 의심
WARN 존재 → 의심
UNKNOWN 존재 → 조사 전
전체 PASS → 정상
Evidence 없음 → 조사 전
SKIP → 상태 판정 제외

SKIP은 장애가 아니라 검사 대상이 설정되지 않았거나
해당 검사에 적용되지 않는 상태이므로 장애 판정에서 제외


7. 현재 Suspect 상태

DAY2-207 / server-207 기준

Power → 조사 전
- Hardware Power Evidence 미수집

Memory → 정상
- memory = PASS

Storage → 조사 전
- Storage Hardware Evidence 미수집

Network → 의심
- pxe_reachability = WARN

OS → 정상
- OS Diagnostic PASS

Service → 정상
- SSH Process PASS
- TCP 22 Listening PASS
- HTTP Health SKIP

Network가 의심으로 표시되는 이유는
NIC / IP / Gateway 자체 장애가 아니라
PXE Server 192.168.100.60 Reachability가 WARN 상태이기 때문


8. Evidence Timeline 구현

기존에는 Mock Evidence와 실제 Evidence가 함께 표시됨

Day 2에서는 현재 Incident인 DAY2-207만 필터링하여
실제 Diagnostic Evidence만 표시하도록 수정

현재 Timeline
19 Evidence

각 Evidence Card 표시 정보

Layer
Check Name
Result
Incident ID
Server ID
Severity
Detail

SKIP 상태도 별도 Result Badge로 표시


9. Dashboard 구성

Rack Overview
↓
Suspect Cards
↓
Evidence Timeline

Rack Overview
- dca-target01
- dca-mgmt01
- dca-target02
- dca-spare01

Suspect Cards
- 현재 Incident Evidence를 요약하여 장애 의심 영역 표시

Evidence Timeline
- 실제 Diagnostic Check 결과와 Detail 표시

Raw JSON이나 터미널 로그를 직접 확인하지 않아도
Dashboard에서 현재 Incident 상태와 실제 Evidence 확인 가능


10. Test / Verification

Backend
- 최신 dca-target02.json Parsing 확인
- 기존 DAY2-207 Evidence 삭제 확인
- 최신 Evidence 19개 저장 확인
- PASS / WARN / FAIL / UNKNOWN / SKIP 저장 확인
- FastAPI /evidence 정상 반환 확인

Frontend
- DAY2-207 Evidence 필터링 확인
- Suspect Card 6개 표시 확인
- Memory 정상 확인
- Network 의심 확인
- OS 정상 확인
- Service 정상 확인
- SKIP 상태 판정 제외 확인
- Evidence Timeline 19개 표시 확인


11. 수정 파일

Backend
backend/import_day2.py
- Diagnostic JSON Parsing
- Evidence DB 저장
- Status / Severity Mapping
- 최신 Evidence Refresh 처리

Frontend
frontend/src/App.jsx
- DAY2-207 Incident 필터링
- Suspect Card 상태 계산
- 실제 Evidence Timeline 표시

frontend/src/App.css
- Suspect Card UI
- 정상 / 의심 / 조사 전 상태 디자인
- SKIP Result Badge 디자인


12. Day 2 Outcome

Ansible에서 생성된 실제 Diagnostic JSON을
Platform의 SQLite DB와 FastAPI에 연동하여
자동 진단 결과가 Backend에서 Frontend까지 전달되는 흐름 구성

Ansible
↓
Evidence JSON
↓
SQLite
↓
FastAPI
↓
React Dashboard

실제 Evidence를 기반으로

Power / Memory / Storage / Network / OS / Service

영역을 Suspect Card로 구성하고

조사 전 → 정상 → 의심

상태를 Dashboard에서 확인할 수 있도록 구현

현재 dca-target02에서는 PXE Reachability 문제로 Network가 의심 상태,
OS와 SSH Service는 실제 Diagnostic 결과를 기반으로 정상 상태 표시

Day 3 Diagnosis Engine과 Incident Evidence Timeline 구현에 사용할
실제 Platform 데이터 연동 기반 마련
