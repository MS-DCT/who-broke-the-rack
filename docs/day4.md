# 📅 Day 4 — 2026-08-26

Day 4 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 4 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | Blackhole Route 기반 Network Fault 재현 및 Cisco SVI·Data Plane·OPNsense 장애 범위 검증, 수동 복구 검증 |
| **B** | Automation / Troubleshooting | NET-ROUTE-01 기반 Network Recovery Role 및 Runner 구현 + 복구 후 Evidence 재수집·상태 검증|
| **C** | Platform / Visualization | 작성 예정 |

---

# 👤 A — Day 4

> Blackhole Route 기반 Network Fault 재현 및 Evidence 연동, Cisco SVI·Data Plane·OPNsense 관점 장애 범위 확인, 수동 Network Recovery 검증

## 1. Network Fault 전 정상 상태 Baseline 확인

### Development
- Network Fault 재현 대상 `dca-target02 (192.168.100.207)` 선정
- Data Plane Interface `eno49` 및 IP `192.168.100.207/24` 상태 확인
- Default Gateway `192.168.100.200` Route 확인
- PXE/Data Plane 대상 `192.168.100.60` 정상 통신 여부 확인

### 검증
- `eno49` Interface UP 확인
- Default Route `via 192.168.100.200 dev eno49` 확인
- `.207 → .200` Ping `0% packet loss` 확인
- `.207 → .60` Ping `0% packet loss` 확인

### Outcome
- Network Fault 주입 전 NIC / IP / Gateway / PXE 통신 정상 상태 Baseline 확보
- 장애 발생 전 Route 및 통신 상태 비교 기준 확보

---

## 2. Blackhole Route 기반 Network Fault 재현

### Development
- SSH 및 Default Gateway 연결을 유지하면서 특정 목적지 통신만 차단할 수 있는 Route Fault 방식 선정
- 장애 대상 경로를 `.207 → 192.168.100.60`으로 제한
- Fault 주입 전 `192.168.100.60` 목적지 Route 확인

```bash
ip route get 192.168.100.60
```

- 임시 Blackhole Route 주입

```bash
sudo ip route add blackhole 192.168.100.60/32
```

### 검증
- Fault 주입 후 Gateway `192.168.100.200` Ping 정상 확인
- PXE `192.168.100.60` 통신 실패 확인
- NIC / IP / Default Gateway 연결을 유지한 상태에서 특정 목적지 Route 장애 재현 확인

### Outcome
- 서버 전체 Network 연결을 차단하지 않는 안전한 Network Fault 시나리오 확보
- `.207 → .60` 경로에 한정된 실제 Route Fault 재현 완료
- 시연 중 SSH 관리 연결을 유지할 수 있는 장애 방식 확정

---

## 3. Network Evidence 및 Diagnosis Engine 연동 검증

### Development
- Blackhole Route Fault 유지 상태에서 Incident Runner 실행

```bash
python3 -m automation.diagnosis.incident_runner \
  --incident-id INC-DAY4-NET-001 \
  --host dca-target02
```

- 실제 Network Evidence 수집 및 Diagnosis Engine 전달 결과 확인

### 검증
- `nic_link = PASS` 확인
- `ip_address = PASS` 확인
- `gateway = PASS` 확인
- `routes = FAIL` 확인
- Route Evidence Detail에서 `blackhole 192.168.100.60` 확인
- `pxe_reachability = WARN` 확인
- Diagnosis 결과 `rule_id = NET-ROUTE-01` 확인
- `severity = HIGH` 확인
- `diagnosis_status = MATCHED` 확인

### Outcome
- 실제 Blackhole Route가 `routes = FAIL` Evidence로 수집되는 흐름 검증
- NIC / IP / Gateway 정상 상태와 Route 장애 상태 분리 검증
- 주입한 Network Fault가 `NET-ROUTE-01` Root Cause로 판별되는 Diagnosis 연동 검증 완료

---

## 4. Route Fault 중 Target 관리 접근 정상 여부 검증

### Development
- Blackhole Route 유지 상태에서 Management Server `dca-mgmt01 (.206)` 기준 Target `.207` 접근 상태 확인
- Ping 및 SSH Port를 이용한 관리 연결 검증

### 검증
- `.206 → .207` Ping `0% packet loss` 확인
- `.207:22` SSH Port 연결 성공 확인

### Outcome
- 특정 Route Fault 발생 중에도 Target Server 자체 접근 정상 확인
- 장애 시 SSH 기반 관리 및 Recovery 수행 가능 상태 확인
- `.207` 전체 Network 단절이 아닌 특정 목적지 Route 장애임을 추가 검증

---

## 5. Cisco Nexus VLAN100 SVI / Data Plane 검증

### Development
- Cisco Nexus L3 Switch에서 VLAN100 SVI 상태 확인
- Target `.207` ARP 학습 상태 확인
- Cisco Nexus 기준 `.207` Data Plane 통신 확인

### 검증
- `Vlan100 = 192.168.100.200` 확인
- `protocol-up / link-up / admin-up` 확인
- ARP Table에서 `192.168.100.207` 및 MAC Address 학습 확인
- Interface `Vlan100` 연결 확인
- Cisco Nexus → `.207` Ping `0.00% packet loss` 확인

### Outcome
- Network Fault 발생 중 VLAN100 SVI / Gateway 정상 상태 검증
- Cisco Nexus에서 Target `.207` 정상 인식 확인
- Cisco/Data Plane → `.207` 통신 정상 확인
- VLAN100 전체 또는 SVI 장애가 아닌 Target 내부 특정 Route 장애로 범위 분리

---

## 6. OPNsense Data Plane 관점 장애 범위 검증

### Development
- OPNsense `DATA_PLANE (192.168.100.90/24)` 기준 Target 및 PXE 통신 상태 확인
- `.207`과 `.60` 각각에 대한 Ping 수행

### 검증
- OPNsense `.90 → .207` Ping `0.0% packet loss` 확인
- OPNsense `.90 → .60` Ping `0.0% packet loss` 확인

### Outcome
- OPNsense/Data Plane 관점 Target `.207` 접근 정상 확인
- PXE `.60` 자체 통신 정상 확인
- Data Plane 전체 또는 PXE Server 장애 가능성 제외
- `.207 → .60` 통신 실패 원인을 `.207`에 주입한 Blackhole Route로 범위 분리

---

## 7. Manual Network Recovery 및 정상화 검증

### Development
- 시연 직후 Network Fault를 즉시 제거할 수 있는 수동 Recovery 명령 확정

```bash
sudo ip route del blackhole 192.168.100.60/32
```

- Blackhole Route 제거 후 Route 및 통신 상태 재검증

### 검증
- `192.168.100.60 dev eno49 src 192.168.100.207` 정상 Route 복구 확인
- `.207 → .60` Ping `0% packet loss` 확인
- `.207 → .200` Ping `0% packet loss` 확인

### Outcome
- Blackhole Route 제거 후 정상 Route 즉시 복구 확인
- PXE `.60` 통신 정상화 확인
- Default Gateway `.200` 정상 상태 유지 확인
- 시연 후 즉시 적용 가능한 Manual Network Recovery 방법 확보 및 실제 복구 검증 완료

---

## Day 4 A 최종 결과

- `dca-target02 (.207)` 기반 안전한 Network Route Fault 시나리오 확정
- Blackhole Route를 이용한 `.207 → .60` 선택적 통신 장애 재현
- 장애 전 정상 Baseline 및 장애 발생 후 Network Evidence 확보
- 실제 Evidence `routes = FAIL` 수집 확인
- Diagnosis Engine `NET-ROUTE-01 / HIGH / MATCHED` 판별 확인
- Route Fault 중 Target Ping / SSH 관리 접근 정상 확인
- Cisco Nexus VLAN100 SVI / ARP / Data Plane 정상 상태 검증
- OPNsense 기준 Target `.207` 및 PXE `.60` 정상 통신 검증
- VLAN100 전체 장애 및 PXE Server 장애 가능성 제외
- Blackhole Route 수동 제거 및 `.60` 통신 정상 복구 검증
- **Day 4 A — Hardware / Infrastructure Network Fault 재현·진단 연동·장애 범위 분리·수동 복구 검증 완료**

---

## 👤 B — Day 4

> `NET-ROUTE-01` 진단 결과를 기준으로 네트워크 복구를 수행하고, 최신 Evidence를 다시 수집하여 복구 여부를 검증하도록 구성했습니다.

### Network Recovery

- Network Interface, Gateway, Route 입력값 검증
- 기본 `PLAN_ONLY` 모드 제공
- 명시적인 실행 요청이 있을 때만 복구 수행
- Default Route 및 SSH 경로 변경 안전장치 적용
- Ansible `network_recovery` Role을 통한 Route 복구
- 정확한 `/32` blackhole Route의 존재 여부를 확인하고, 존재할 때만 해당 Route를 제거하는 멱등 복구 지원

### Recovery 검증

- NIC Link
- IP Address
- Gateway
- Route
- PXE Reachability
- SSH Process
- TCP 22 Port
- HTTP Health는 Endpoint가 설정된 경우에만 검증

복구 후 최신 Evidence를 다시 수집하며, 필수 항목이 모두 정상일 경우 `VERIFIED`, 실패·누락·UNKNOWN 상태가 있으면 `ESCALATION_REQUIRED`로 판정합니다.

### 처리 흐름

`NET-ROUTE-01 진단 → 복구 계획 확인 → Network Recovery 실행 → Evidence 재수집 → 상태 검증`

### 실제 E2E 검증 결과

- 대상: `dca-target02` (`192.168.100.207`), Interface `eno49`
- 장애 주입: `blackhole 192.168.100.60/32`
- 장애 상태에서도 SSH와 Gateway 통신은 정상 유지되고 PXE 목적지 `192.168.100.60`만 실패
- 장애 Evidence에서 `nic_link`, `ip_address`, `gateway`는 PASS, `routes`는 FAIL
- Diagnosis Engine에서 `NET-ROUTE-01` 매칭 확인
- 공개 Recovery 인터페이스의 명시적 execute 모드로 정확한 blackhole `/32` Route만 제거
- 복구 후 `nic_link`, `ip_address`, `gateway`, `routes`, `pxe_reachability`, SSH Process, TCP 22 Listening Port PASS
- 미설정 HTTP Health는 기존 정책에 따라 검증 대상에서 제외
- 최종 Recovery 상태 `VERIFIED`
- 종료 시 `blackhole 192.168.100.60/32` 잔존 없음
- Default Route, Gateway, IP, Interface, NetworkManager Connection은 변경하지 않음

### 테스트 결과

- Day 4 Recovery 테스트 35개 통과
- Day 3 Diagnosis 테스트 34개 통과
- 총 69개 테스트 통과
- Ansible Syntax Check 통과
- 실제 E2E Recovery 검증 완료

---

# 👤 C — Day 4

# Day 3 — Diagnosis & Incident Visualization 마무리

#### Root Cause / Suspect Card 연동
- Diagnosis Engine의 `rule_id`를 React Suspect Card와 연동
- `NET-ROUTE-01`, `HW-STORAGE-01`, `BOOT-OS-01`, `SVC-HTTP-01` 결과를 각 장애 영역에 매핑
- Root Cause가 확정되면 해당 Suspect Card를 강조하고 `CULPRIT FOUND` 상태를 표시하도록 구현
- `NET-ROUTE-01` 테스트를 통해 Network 카드 강조 UI 정상 동작 확인

#### Incident Evidence Timeline 검증
- Incident / Evidence / Diagnosis / Action 이벤트를 Timestamp 기준으로 Timeline에 표시
- `DETECTED → INVESTIGATING → ROOT_CAUSE_FOUND` 상태 흐름 및 Diagnosis 결과 표시 확인
- 실제 Incident 실행을 통해 Evidence 수집 및 Timeline 저장/렌더링 정상 동작 확인

### Day 3 Outcome
- Incident Timeline API/DB 및 React 연동 완료
- Root Cause와 Suspect Card 간 실시간 시각적 연동 완료
- Diagnosis 결과를 기반으로 최종 장애 영역을 강조하는 UI 구현 완료

### Day 4 — Network Recovery Platform Integration

#### Recovery API 연동
- 기존 Automation Recovery Runner를 FastAPI Backend와 연결
- `POST /incidents/{incident_id}/recovery` Endpoint 구현
- Recovery 요청 시 Incident와 최신 Diagnosis를 조회하여 Recovery Runner로 전달
- Recovery 결과를 `Action` 테이블에 저장하고 Incident Timeline에 포함하도록 구현

#### PLAN_ONLY Recovery
- 실제 인프라 변경 없이 Recovery 계획을 검증할 수 있도록 `PLAN_ONLY` 모드 연동
- `NET-ROUTE-01 → network_recovery` 매핑 정상 동작 확인
- Recovery 결과:
  - `mode = PLAN_ONLY`
  - `result = PLANNED`
  - `verification_status = NOT_RUN`
- Timeline에 `ACTION / network_recovery / PLANNED` 이벤트 저장 확인

#### Network Recovery UI
- React에 `NETWORK RECOVERY` Panel 추가
- Network 장애 진단 시 아래 Recovery 정보 표시
  - Recovery Type: `Remove Blackhole Route`
  - Target: `192.168.100.60/32`
- `Plan Recovery` 버튼 구현
- Recovery Plan 결과를 UI에서 `PLAN_ONLY / PLANNED` 상태로 표시
- 실제 Recovery를 실행할 수 있는 `Execute Recovery` 버튼 및 상태 UI 추가
- Recovery 성공 시 `CASE CLOSED`를 표시하도록 UI 로직 구현

#### Real Network Recovery E2E Test
- Target Server `dca-target02 (192.168.100.207)`에 실제 Network Fault 주입
- `blackhole 192.168.100.60/32` Route를 이용하여 PXE 목적지 통신만 선택적으로 차단
- 장애 상태에서:
  - NIC Link 정상
  - IP Address 정상
  - Gateway `192.168.100.200` 정상
  - Route 장애 감지
  - `NET-ROUTE-01` Root Cause 판별 확인
- FastAPI Recovery API를 통해 Ansible `network_recovery` 실행
- Blackhole Route 자동 제거 성공
- Recovery 후 Evidence 재수집 및 Verification 수행

#### Recovery Verification
- `nic_link = PASS`
- `ip_address = PASS`
- `gateway = PASS`
- `routes = PASS`
- `pxe_reachability = PASS`
- SSH Process / Listening Port = PASS
- 최종 결과:
  - `mode = EXECUTE`
  - `result = SUCCESS`
  - `verification_status = VERIFIED`
  - Incident Status = `CLOSED`

### Day 4 Outcome
- Network Fault → Diagnosis → Recovery Plan → Recovery Execution → Verification 흐름 연동 완료
- FastAPI / DB / Timeline / React / Ansible Recovery 간 통합 완료
- 실제 Network Route 장애를 자동 복구하고 Incident를 `CLOSED` 상태까지 전환하는 End-to-End Recovery 흐름 검증 완료
