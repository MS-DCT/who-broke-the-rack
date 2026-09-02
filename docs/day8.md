# 📅 Day 8 — 2026-09-01

Day 8 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 8 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | Reset Checklist 기반 Demo Baseline 검증 및 Network·Service·Physical Recovery 반복 안정성 검증, 수동 우회 절차·발표용 Evidence 확보 |
| **B** | Automation / Troubleshooting | B 통합 안정화, 안전성 회귀 및 C 인계 계약 정리 |
| **C** | Platform / Visualization | 작성 예정 |

---

# 👤 A — Day 8

> Reset Checklist 기반 Demo Baseline 검증 및 Network·Service·Physical Recovery 반복 안정성 확인, 장애 발생 시 수동 우회 절차 정리 및 최종 Demo Freeze 완료

## 1. Day 8 목표

- 기능 추가 없이 기존 Infrastructure 및 Recovery 흐름의 반복 안정성 검증
- 각 Scenario 실행 전 Target #3·Spare #4 정상 상태 복귀를 위한 Reset Checklist 검증
- Network·Service·Physical Recovery 3개 Scenario 반복 실행 결과 확인
- iLO·PXE·Network·LB 문제 발생 시 Demo 중 사용할 수동 우회 절차 정리
- 최종 Demo Baseline 확인 및 발표용 Evidence 확보

---

## 2. Reset Checklist 및 Pre-Demo Baseline 검증

### Target #3 — `dca-target02`

- Data Plane `192.168.100.207` Reachability 정상 확인
- `eno49` UP 및 `192.168.100.207/24` 확인
- Default Gateway `192.168.100.200` 확인
- Network Fault 재현에 사용한 Blackhole Route 제거 상태 확인
- `nginx` Active 상태 확인
- Local `/health` HTTP `200` 확인
- Failed Unit 미검출 확인

### Spare #4 — `dca-spare01`

- Data Plane `192.168.100.208` Reachability 정상 확인
- `pxe0` UP 및 `192.168.100.208/24` 확인
- QSFP+ NIC `40Gbps / Full Duplex / Link detected yes` 확인
- PXE Server `192.168.100.60` Reachability 정상 확인
- Failed Unit 미검출 확인

### Shared Infrastructure

- VLAN100 Gateway `192.168.100.200` Reachability 정상 확인
- PXE Server `192.168.100.60` Reachability 정상 확인
- Management Node → Target #3 `/health` HTTP `200` 확인

---

## 3. Network Recovery 반복 안정성 검증

기존 `NET-ROUTE-01` Diagnosis Evidence와 Day 8 Network Recovery Variables를 이용해 Recovery Runner 반복 실행 검증.

```text
rule_id             : NET-ROUTE-01
action              : network_recovery
executor            : ansible
mode                : PLAN_ONLY
result              : PLANNED
verification_status : NOT_RUN
```

Recovery Plan에서 다음 항목 동일 생성 확인.

- Interface `eno49`
- Gateway `192.168.100.200`
- `192.168.100.60/32` Blackhole Route 제거 계획
- 반복 실행 시 동일 Recovery Plan 생성 확인
- `PLAN_ONLY` 실행을 통한 Target Network 무변경 확인

**결과: Network Recovery 반복 안정성 PASS**

---

## 4. Service Recovery 반복 안정성 검증

Day 5 Service Fault 흐름과 B의 `day5_mock_http` Profile을 기준으로 Day 8 반복 검증용 `SVC-HTTP-01` Diagnosis Fixture 구성.

```text
rule_id             : SVC-HTTP-01
action              : service_recovery
executor            : ansible
mode                : PLAN_ONLY
result              : PLANNED
verification_status : NOT_RUN
```

Recovery Plan에서 다음 항목 확인.

- Profile `day5_mock_http`
- Service `wbr-day5-mock.service`
- Config Restore 요청 생성
- HTTP Recovery 활성화
- 반복 실행 시 동일 Service Recovery Plan 생성 확인
- `PLAN_ONLY` 실행을 통한 실제 Target Service 무변경 확인

**결과: Service Recovery 반복 안정성 PASS**

> Day 8의 `SVC-HTTP-01` Diagnosis JSON은 Day 5 당시 저장된 실제 Diagnosis Evidence가 아닌 반복 안정성 검증용 Fixture로 사용.

---

## 5. Physical Recovery 반복 안정성 검증

Day 7에서 확보한 Target #3 Node Failure Evidence와 Spare #4 Hardware Evidence를 기반으로 Physical Recovery 재실행.

동시에 현재 Spare #4의 Reachability·Network·OS·PXE Server 연결 상태를 재검증.

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

- 저장된 Target Node Failure Evidence 재사용
- Spare #4 현재 상태 실시간 검증
- Physical Recovery 반복 실행 시 `READY` 재확인
- 실제 PXE Provisioning 미수행으로 `UNKNOWN / PENDING` 상태 유지

**결과: Physical Recovery 반복 안정성 PASS**

---

## 6. Demo 수동 우회 절차 정리

### iLO

- 자동 상태 확인 불가 시 iLO Web Console을 통한 Power·Health 직접 확인
- Data Plane 및 OS 접근 가능 시 SSH 기반 Host 상태 교차 확인

### Network

- Recovery 자동 실행 문제 발생 시 `ip addr`, `ip route` 기반 상태 확인
- 승인된 Target에 한해 장애 Route 수동 제거 후 Reachability 재검증

### Service

- Recovery 자동 실행 문제 발생 시 `systemctl` 기반 Service 상태 확인
- `/health` HTTP 응답을 통한 Service 상태 교차 확인
- 승인된 Target에 한해 Service 수동 복구 수행

### PXE

- Demo 중 공유 PXE·ProxyDHCP 설정 임의 변경 금지
- Spare #4의 기존 Rocky Linux 9.8 환경 유지
- `pxe0` 및 PXE Server `192.168.100.60` Reachability를 Provisioning 준비 상태의 보조 Evidence로 사용
- 실제 PXE 재설치 필요 시 기존 검증 절차 및 C의 PXE Provisioning 결과 활용

### LB

- 프로젝트 전용 LB Backend / Listener 구성 Evidence 미확보
- 공유 OPNsense 설정 임의 변경 금지
- Day 8 Demo 범위에서 LB 변경 `N/A` 처리

### Backend / UI

- Backend 또는 UI 연계 문제 발생 시 저장된 Evidence JSON 및 Terminal 실행 결과를 Demo Fallback으로 사용

---

## 7. Final Demo Baseline 및 Freeze

3개 Scenario 반복 검증 이후 Target #3·Spare #4·Shared Infrastructure의 최종 정상 상태 재확인.

```text
Target #3
- 192.168.100.207 Reachability PASS
- eno49 UP
- Default Gateway 192.168.100.200
- Blackhole Route NONE
- nginx active
- /health HTTP 200

Spare #4
- 192.168.100.208 Reachability PASS
- pxe0 UP
- System running
- PXE Server 192.168.100.60 Reachability PASS

Shared Infrastructure
- Gateway 192.168.100.200 Reachability PASS
- PXE Server 192.168.100.60 Reachability PASS
- Management → Target /health HTTP 200
```

### Day 8 최종 상태

- Reset Checklist 검증 완료
- Network Recovery 반복 안정성 PASS
- Service Recovery 반복 안정성 PASS
- Physical Recovery 반복 안정성 PASS
- Manual Bypass 절차 정리 완료
- 발표용 Infrastructure Evidence 확보
- Target #3·Spare #4·Shared Infrastructure 정상 상태 복귀 확인
- 추가 Fault Injection 및 공유 Infrastructure 설정 변경 중단
- **Demo Baseline Freeze 완료**

---

## 👤 B — Day 8

- Diagnosis → Recovery → Verify → Escalation 흐름과 Scenario A/B/C의 공통 incident/timeline JSON 계약을 회귀 검증했다.
- 공개 함수는 `run_recovery`, `run_escalation`, `run_standard_build`, `run_workflow`이며 import만으로 CLI나 Ansible을 실행하지 않는다.
- unsupported rule, evidence 부족, recovery 실패, timeout, duplicate/resume, adapter 미설정 결과를 구분하는 통합 테스트를 추가했다.
- Python 테스트 101건과 B 관련 playbook syntax check를 통과했다. 전체 playbook 순회에서는 기존 `post_pxe.yml`의 `community.general.modprobe` collection 부재가 blocker로 남았다.
- 실제 환경 결과와 mock 결과를 구분했으며, L3~L5 Physical Recovery와 PXE는 실행하지 않았다.
- 최종 실제 검증에서 `.207` Nginx Recovery는 `SUCCESS/VERIFIED`, `.208` read-only Standard Build Health Validation은 `VERIFIED`로 확인했다.

---

# 👤 C — Day 8

> 작성 예정
