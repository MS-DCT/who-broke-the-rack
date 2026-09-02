# 📅 Day 7 — 2026-08-31

Day 7 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 7 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | Node Failure 재현 및 Target 격리·Spare #4 Physical Recovery 검증, Backend 연계·3개 Recovery Scenario 통합 |
| **B** | Automation / Troubleshooting | 공통 Incident/Recovery/Escalation Workflow 구현 |
| **C** | Platform / Visualization | 작성 예정 |

---

# 👤 A — Day 7

> Target #3 Node Failure 재현 및 Spare #4 Physical Recovery 검증, Backend 연계와 Network·Service·Node 3개 Recovery Scenario 통합

## 1. Day 7 목표

Day 7에서는 기존 Network / Service 장애 복구 범위를 넘어  
**물리 서버 자체가 정상적으로 서비스를 수행할 수 없는 Node Failure 상황에서 Spare Server로 전환하기 위한 Physical Recovery 흐름 검증** 진행.

기존 Software Recovery와 Physical Recovery 역할을 다음과 같이 구분.

- Network Fault → Software Network Recovery
- Service Fault → Software Service Recovery
- Node Failure → Escalation → Physical Recovery
- Physical Recovery 이후 Spare Server의 Hardware / OS / Network / PXE 경로 검증
- Physical Recovery 결과를 Backend Action 구조에 저장하여 Platform에서 조회 가능한 형태로 전달
- Day 4 Network / Day 5 Service / Day 7 Node Failure를 하나의 Recovery Policy로 통합

Day 7 Physical Recovery 대상 구성.

| 구분 | Server | Hostname | Data Plane |
| --- | --- | --- | --- |
| 장애 Target | Server #3 | `dca-target02` | `192.168.100.207` |
| Spare | Server #4 | `dca-spare01` | `192.168.100.208` |
| PXE Server | ZT Storage | - | `192.168.100.60` |

---

## 2. Target #3 / Spare #4 정상 상태 확인

Node Failure 재현 전 Target #3의 OS 상태 확인.

Target #3에서 기존 `systemd-suspend.service` Failed 상태 초기화 후  
System State 정상 상태 확인.

```bash
sudo systemctl reset-failed systemd-suspend.service
systemctl is-system-running
systemctl --failed
```

Spare #4에서는 Physical Recovery 투입 가능 여부 확인.

확인 항목:

- Hostname `dca-spare01`
- System State `running`
- Data Plane Interface `pxe0`
- IP `192.168.100.208/24`
- Default Gateway `192.168.100.90`
- QSFP+ NIC Driver `mlx4_en`
- Speed `40000Mb/s`
- Full Duplex
- Link detected `yes`
- PXE Server `192.168.100.60` Reachability 정상

**결과: Target #3 정상 상태 및 Spare #4 OS / Network Baseline 확보**

---

## 3. Target #3 Node Failure 재현

Physical Recovery가 필요한 장애 상황을 만들기 위해  
Target #3의 iLO 상태를 먼저 확인.

장애 발생 전 상태:

- iLO Reachability 정상
- System Health `OK`
- Server Power `ON`

iLO Virtual Power Button의 **Hold** 기능을 사용하여 Target #3 강제 Power OFF 수행.

Power OFF 이후 Data Plane 및 OS 접근 상태 확인.

- `192.168.100.207` Ping 실패
- SSH 접근 실패
- OS / Data Plane 서비스 불가 상태 확인

**결과: iLO는 접근 가능하지만 Target OS / Data Plane이 중단된 Node Failure 상태 재현**

---

## 4. Node Failure Hardware Evidence 수집

Target #3 Power OFF 상태에서 Hardware Collector 실행.

```bash
python automation/hardware/hardware_collector.py \
  --server-id server-207 \
  --incident-id DAY7-NODE-01
```

주요 Hardware Evidence:

| Check | Result | Value |
| --- | --- | --- |
| `ilo_reachability` | PASS | REACHABLE |
| `power_state` | WARN | Off |
| `system_health` | FAIL | OK / State Disabled |
| `post_state` | SKIP | PowerOff |
| `boot_os_state` | UNKNOWN | NOT_VERIFIED |
| Storage | PASS | 정상 |
| Controller | PASS | 정상 |
| Logical Drive | PASS | 정상 |
| Physical Drive | PASS | 정상 |

Power OFF 상태에서도 Storage 계층 자체의 Health는 정상으로 확인.

**결과: Storage 장애가 아닌 Node Power / Boot 계층 장애 상태 분리 확인**

---

## 5. Target 격리 및 Spare #4 Ready 검증

Target #3 장애 상태와 Spare #4 정상 상태 비교.

- Target #3 `.207` → Ping 실패
- Spare #4 `.208` → Ping 정상
- Spare Hostname → `dca-spare01`
- System State → `running`
- `pxe0` → UP
- `192.168.100.208/24` 정상
- 40Gbps / Full Duplex / Link detected yes 확인

Spare #4 Hardware Collector를 통해 iLO / POST / Hardware Health 추가 확인.

주요 결과:

- iLO Reachability PASS
- Power State PASS / On
- System Health PASS
- POST State PASS / FinishedPost
- Memory Health PASS
- Storage Health PASS
- Controller Health PASS
- Logical Drive Health PASS
- Physical Drive Health PASS

**결과: 장애 Target #3 격리 상태 및 Spare #4 Physical Recovery 투입 조건 확보**

---

## 6. Physical Recovery 자동 검증 구현

기존 Software Recovery와 분리된 Physical Recovery 검증 모듈 구현.

구현 파일:

```text
automation/physical_recovery/
├── __init__.py
└── physical_recovery.py
```

Physical Recovery 모듈에서 다음 항목 자동 검증.

1. Target Node Failure Evidence 확인
2. Spare Hardware Ready 확인
3. Spare Data Plane Reachability 확인
4. Spare Network Interface / Link 확인
5. Spare OS Ready 확인
6. Spare → PXE Server Reachability 확인
7. Physical Recovery 최종 Ready 판정

자동 검증 결과:

```text
target_node_failure       PASS     NODE_FAILURE_CONFIRMED
spare_hardware_ready      PASS     READY
spare_reachability        PASS     REACHABLE
spare_network_ready       PASS     UP
spare_os_ready            PASS     RUNNING
pxe_server_reachability   PASS     REACHABLE
pxe_provisioning_ready    UNKNOWN  PENDING
physical_recovery_ready   PASS     READY

PHYSICAL_RECOVERY=READY
```

현재 Incident에서 PXE 재설치를 다시 수행하지 않았으므로  
`pxe_provisioning_ready`는 실제 상태에 맞게 `UNKNOWN / PENDING` 유지.

따라서 Physical Recovery Ready는 **Spare Server의 Hardware / OS / Network 및 PXE Server 접근 가능 상태**를 기준으로 판정.

**결과: Spare #4 Physical Recovery 투입 가능 상태 자동 검증 완료**

---

## 7. Physical Recovery Evidence 공통 포맷 검증

Physical Recovery 결과를 기존 Evidence 구조와 동일한 방식으로 전달할 수 있도록 JSON 생성.

생성 Evidence:

```text
evidence/day7/hardware/DAY7-NODE-01-target.json
evidence/day7/hardware/DAY7-PHYSICAL-RECOVERY-01-spare.json
evidence/day7/physical_recovery/DAY7-PHYSICAL-RECOVERY-01.json
```

공통 필드 검증:

```text
incident_id
server_id
host
timestamp
category
source
evidence
```

각 Evidence Item:

```text
result
value
detail
source
```

검증 결과:

```text
C_HANDOFF_FORMAT READY
```

**결과: Physical Recovery 결과의 Backend / Platform 전달용 공통 JSON 포맷 검증 완료**

---

## 8. Backend Incident / Physical Recovery Action 연계

실제 Backend Incident 생성.

```text
Incident ID : INC-20260902-095643-FA80
Server      : server-207
Host        : dca-target02
Status      : DETECTED
```

Physical Recovery 결과를 기존 Backend Action 구조에 저장하기 위해  
다음 Service Layer 구현.

```text
backend/physical_recovery_service.py
```

Physical Recovery Evidence의 최종 Ready 상태 확인 후 Backend에 다음 정보 저장.

```text
action_type = physical_recovery
status      = READY
mode        = PHYSICAL
action      = physical_recovery
result      = READY
```

Incident 상태는 Physical Recovery 단계로 Escalation된 상태를 표현하기 위해 `ESCALATED` 유지.

실제 Backend 연계 결과:

```text
incident_id              INC-20260902-095643-FA80
target                   server-207 / dca-target02
incident_status          ESCALATED
action_type              physical_recovery
action_status            READY
spare                    server-208 / dca-spare01
physical_recovery_ready  PASS / READY
pxe_provisioning_ready   UNKNOWN / PENDING

BACKEND_PHYSICAL_RECOVERY READY
```

**결과: Physical Recovery 결과의 기존 Backend Action DB 구조 연계 완료**

---

## 9. Platform 전달 API 검증

Backend에 저장된 Physical Recovery Action을 기존 API를 통해 조회.

`/actions`에서 확인된 주요 정보:

- `action_type = physical_recovery`
- `status = READY`
- Physical Recovery Evidence 포함
- Spare Server 정보 포함
- `mode = PHYSICAL`

Incident Timeline에서도 Physical Recovery Action 확인.

```text
Incident Status : ESCALATED
Recovery Action : physical_recovery
Action Status   : READY
Mode            : PHYSICAL
```

별도의 Physical Recovery 전용 API를 추가한 것이 아니라,  
**Physical Recovery 결과를 Backend Service Layer를 통해 기존 Action DB 구조에 저장하고 기존 Action / Timeline API를 통한 Platform 전달 경로 검증**.

**결과: Physical Recovery 결과의 Platform 전달 경로 확인 완료**

---

## 10. Load Balancer 전환 검토

Physical Recovery 이후 Spare #4를 서비스 Backend로 전환하는 절차 검토.

OPNsense Data Plane Gateway `192.168.100.90` Reachability 정상 확인.

다만 현재 프로젝트 Repository 및 실제 환경에서 Target #3 `.207`과 Spare #4 `.208`을 연결하는 프로젝트 전용 Load Balancer Backend 구성을 확인할 수 없었으며, 일반 서비스 포트에서도 해당 LB Listener 확인 불가.

또한 OPNsense는 다른 팀과 공유하는 Infrastructure이므로 근거 없는 Backend 설정 변경 미수행.

**결과: Load Balancer Backend 전환 N/A / 공유 Infrastructure 불필요 변경 미수행**

---

## 11. Network / Service / Node Recovery 통합

Day 4 Network Fault, Day 5 Service Fault, Day 7 Node Failure 결과를 하나의 Recovery Matrix로 정리.

생성 파일:

```text
evidence/day7/integration/three-scenario-recovery-matrix.json
```

### Scenario A — Network Fault

```text
Fault        : Blackhole Route 192.168.100.60/32
Target       : server-207
Diagnosis    : NET-ROUTE-01
Severity     : HIGH
Recovery     : Software Network Recovery
Verification : PASS
```

### Scenario B — Service Fault

```text
Fault        : Nginx Service Stop
Target       : server-207
Diagnosis    : SVC-HTTP-01
Recovery     : Software Service Recovery
Verification : HTTP 200 Restored
```

### Scenario C — Node Failure

```text
Fault             : Target #3 Forced Power OFF
Target            : server-207
iLO               : PASS
OS / Data Plane   : FAIL
Recovery           : Physical Recovery
Spare              : server-208
Physical Ready     : PASS / READY
PXE Provisioning   : UNKNOWN / PENDING
Backend Incident   : ESCALATED
Backend Action     : physical_recovery / READY
```

최종 Recovery Policy:

```text
Network Fault
    ↓
Software Network Recovery

Service Fault
    ↓
Software Service Recovery

Node Failure
    ↓
ESCALATED
    ↓
Physical Recovery
    ↓
Spare #4 Ready
```

통합 검증 결과:

```text
THREE_SCENARIO_MATRIX      : VALID
THREE_SCENARIO_INTEGRATION : READY
```

**결과: Network / Service / Physical Recovery 3개 장애 유형별 Recovery 경로 통합 완료**

---

## 12. Day 7 최종 결과

| 항목 | 결과 |
| --- | --- |
| Target #3 Node Failure 재현 | ✅ 완료 |
| Power OFF Hardware Evidence 수집 | ✅ 완료 |
| Target 격리 상태 확인 | ✅ 완료 |
| Spare #4 Hardware Ready 검증 | ✅ 완료 |
| Spare #4 OS / Network Ready 검증 | ✅ 완료 |
| PXE Server Reachability 검증 | ✅ 완료 |
| Physical Recovery 자동 검증 | ✅ `READY` |
| Physical Recovery 공통 Evidence 생성 | ✅ 완료 |
| Backend Action DB 연계 | ✅ `physical_recovery / READY` |
| Platform Action / Timeline 전달 | ✅ 완료 |
| LB Backend 전환 | ➖ N/A |
| 3개 Recovery Scenario 통합 | ✅ `READY` |
| PXE Provisioning 현재 Incident 재실행 | ⏳ `UNKNOWN / PENDING` |

### 최종 흐름

```text
Target #3 Node Failure
        ↓
Hardware Evidence
        ↓
Target Failure Confirmed
        ↓
ESCALATION
        ↓
Physical Recovery
        ↓
Target Isolation
        ↓
Spare #4 Hardware Ready
        ↓
Spare OS / Network Ready
        ↓
PXE Server Reachable
        ↓
Physical Recovery READY
        ↓
Backend Action
        ↓
Platform / Timeline 전달
```

**Day 7 결과: Node Failure 발생 시 Software Recovery 범위를 넘어 Spare Server로 전환하기 위한 Physical Recovery 검증 흐름 구축 및 Network / Service / Physical Recovery 통합 완료**

---

## 👤 B — Day 7

- `run_incident()`와 기존 Network/Service `run_recovery()`를 dispatcher로 사용하는 `run_workflow()`를 구현했다.
- Node Isolation, Spare Activation, PXE Rebuild는 callback adapter로 분리하고 DB 저장은 수행하지 않는다.
- Scenario A/B의 software recovery 성공, Scenario C의 L3~L5 요청과 Standard Build 연결을 mock으로 검증했다.
- timeline event, timeout, retry, idempotency, resume state, PLAN_ONLY 및 `MANUAL_REQUIRED` 반환 계약을 고정했다.

---


# 👤 C — Day 7

> Incident 전체 Lifecycle과 Physical Recovery 진행 상태를 Frontend에서 실시간 시각화하고, Rack Overview 및 CASE CLOSED 결과까지 하나의 운영 화면으로 연결

## 1. Day 7 C 목표

Day 6에서 구현한 Recovery Escalation UI를 확장하여 다음 항목을 구현했다.

```text
DETECTED
  ↓
INVESTIGATING
  ↓
ROOT_CAUSE_FOUND
  ↓
RECOVERING
  ↓
ESCALATING
  ↓
VERIFYING
  ↓
CLOSED
```

또한 Physical Recovery 진행 중 Rack Overview에서 장애 Target과 Spare 상태를 구분하도록 구성했다.

```text
Target #3   → FAILED
Spare #4    → SPARE / RECOVERING / READY
```

---

## 2. Incident State Machine UI

`frontend/src/IncidentPanel.jsx`에 Day 7 Incident State Machine을 추가했다.

상태 목록:

```text
DETECTED
INVESTIGATING
ROOT_CAUSE_FOUND
RECOVERING
ESCALATING
VERIFYING
CLOSED
```

현재 Incident / Diagnosis / Recovery / Escalation 상태를 조합하여 화면의 현재 Lifecycle 상태를 계산한다.

주요 매핑:

```text
Incident 생성                      → INVESTIGATING
Diagnosis MATCHED                  → ROOT_CAUSE_FOUND
Software Recovery 진행            → RECOVERING
Escalation 상태 존재               → ESCALATING
Escalation READY                   → VERIFYING
Incident status CLOSED             → CLOSED
```

각 단계는 `complete / active / pending` 상태로 표시되며 현재 단계가 시각적으로 강조된다.

---

## 3. Timeline 자동 Polling

기존 수동 Refresh Timeline 기능에 더해 현재 Incident가 존재하면 Timeline API를 2초 간격으로 자동 조회하도록 구성했다.

```text
GET /incidents/{incident_id}/timeline
        ↓
2초 Polling
        ↓
Incident Evidence Timeline 갱신
```

Day 6의 Escalation 2초 Polling과 함께 Recovery 진행 상태와 Timeline을 별도 새로고침 없이 확인할 수 있도록 구성했다.

---

## 4. Rack Overview Physical Recovery 상태 시각화

`App.jsx`에서 `IncidentPanel`의 현재 Platform 상태를 Parent로 전달하도록 `onPlatformStateChange` Callback을 추가했다.

Rack 상태 매핑:

```text
현재 Incident Target + Escalation 발생
    → FAILED

server-208 + SPARE_ACTIVATING / PXE / CONFIGURING
    → RECOVERING

server-208 + READY
    → READY

server-208 + Physical Recovery 미진행
    → SPARE
```

따라서 Physical Recovery 흐름 중 운영 화면에서 장애 서버와 대체 서버의 역할을 즉시 구분할 수 있다.

---

## 5. Day 7 Physical Recovery UI 전환 검증

검증 Incident:

```text
INC-20260902-181304-93AF
Target: server-207 / dca-target02
```

먼저 신규 Incident 생성 후 State Machine에서 다음 상태가 표시됨을 확인했다.

```text
INVESTIGATING
```

이후 Escalation API에 다음 상태를 입력했다.

```text
L3 / ESCALATION_REQUIRED
```

Frontend Polling 결과:

```text
INVESTIGATING
    ↓
ESCALATING
```

전환을 확인했다.

이후 동일 Incident에 다음 Physical Recovery 상태를 순차 적용했다.

```text
L4 / SPARE_ACTIVATING
L5 / PXE
L5 / CONFIGURING
L5 / READY
```

최종 `READY` 상태에서 Incident State Machine이 `VERIFYING` 단계로 전환되는 흐름을 검증했다.

Day 7 C 검증에서 실제 L3~L5 장비 제어는 수행하지 않았으며, C Escalation API 상태를 이용해 Platform / Visualization 경로를 검증했다.

---

## 6. Incident Close API

최종 Verification 이후 Incident를 명시적으로 종료할 수 있도록 Backend에 다음 API를 추가했다.

```text
POST /incidents/{incident_id}/close
```

Close 처리 시:

```text
Incident status  → CLOSED
ended_at         → 현재 시각 기록
Action           → CASE_CLOSED / CLOSED
```

CASE_CLOSED Action의 details에는 Physical Recovery Verification 완료 내용을 기록한다.

---

## 7. CASE CLOSED 및 Recovery Time UI

Incident History의 현재 Incident가 `CLOSED` 상태가 되면 State Machine의 마지막 단계가 활성화되도록 구성했다.

최종 결과 UI:

```text
FINAL RESULT
CASE CLOSED

Recovery Time
Xm Ys
```

Recovery Time은 Incident의 `started_at`과 `ended_at` 차이를 기준으로 계산한다.

사용자 요청에 따라 Day 7 마무리 시점에는 최종 `CLOSED / CASE CLOSED / Recovery Time` 화면 검증을 완료한 것으로 간주하고 문서화했다.

---

## 8. 스타일 구성

Day 7 전용 스타일을 다음 파일로 분리했다.

```text
frontend/src/day7.css
```

포함 스타일:

- Incident State Machine
- active / complete / pending 단계
- Rack `FAILED`
- Rack `SPARE`
- Rack `RECOVERING`
- Rack `READY`
- Final CASE CLOSED Card
- Recovery Time
- 반응형 Layout

`App.jsx`에서 `day7.css`를 import하여 기존 Day 5/6 UI와 함께 적용한다.

---

## 9. Day 7 C와 B/A 통합 범위 구분

Day 7 C에서 완료한 범위:

```text
Incident Lifecycle 시각화
Timeline 자동 Polling
Escalation → State Machine 연동
Rack Physical Recovery 상태 시각화
VERIFYING / CLOSED 상태 표현
CASE CLOSED / Recovery Time
```

실제 B의 L3~L5 Physical Infrastructure adapter를 통한 자동 장비 제어 및 실제 PXE Rebuild Trigger는 별도 통합 단계에서 검증한다.

따라서 다음을 구분한다.

```text
C Platform / Visualization 구현       : 완료
B → 실제 PXE 자동 실행 E2E 통합       : 후속 통합 검증
```

---

## Day 7 C 최종 결과

- Incident State Machine 구현
- `DETECTED → INVESTIGATING → ROOT_CAUSE_FOUND → RECOVERING → ESCALATING → VERIFYING → CLOSED` 시각화
- Timeline 2초 자동 Polling 구현
- Day 6 Escalation Polling과 Lifecycle 연동
- Parent App으로 Platform State 전달
- Rack Overview `FAILED / SPARE / RECOVERING / READY` 상태 표현
- `INVESTIGATING → ESCALATING` 실제 UI 전환 확인
- `READY → VERIFYING` Physical Recovery UI 흐름 구성
- Incident Close API 구현
- `CASE_CLOSED` Action 저장
- `CLOSED / CASE CLOSED / Recovery Time` 최종 UI 구현
- Day 7 전용 CSS 분리
- React Production Build 성공 확인
- 실제 B→PXE 자동연계는 후속 통합 검증 항목으로 분리

**Day 7 C — Incident Lifecycle·Physical Recovery Timeline·Rack 상태·CASE CLOSED 시각화 구현 완료**
