# 📅 Day 2 — 2026-08-24

Day 2 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 2 작업 |
|---|---|---|
| **A** | - | 작성 예정 |
| **B** | Automation / Troubleshooting | Network/OS/Service 자동 진단 Role 구현 + 상태 판정 + Evidence JSON 자동 생성 |
| **C** | - | 작성 예정 |

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

# 👤 C — Day 2

> 작성 예정
