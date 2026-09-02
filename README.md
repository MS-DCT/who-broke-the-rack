# WHO BROKE THE RACK?

> **Data Center Troubleshooting & Automated Recovery Platform**

---

## 📅 Development Log

| Day | A | B | C |
|---|---|---|---|
| **Day 1 — 2026-08-23** | #5/#6/#7/#8 서버 / iLO / 네트워크 Baseline 구성 및 연결 확인 완료 | Ansible 대상 서버 구성 + QSFP/네트워크 Baseline 수동 검증 + 수동 Evidence 확보 | FastAPI / SQLite / React Dashboard / GitHub 환경 구성 |

➡️ [Day 1 상세 작업 기록](docs/day1.md)

---

## 📅 Development Log

| Day | A | B | C |
|---|---|---|---|
| **Day 2 — 2026-08-24** | Redfish 기반 Hardware/POST Evidence Collector 구현 + 상태 판정 + 다중 서버 Evidence JSON 수집 | Network/OS/Service 자동 진단 Role 구현 + 상태 판정 + Evidence JSON 자동 생성 | Diagnostic Evidence DB 연동 + Suspect Card + Evidence Timeline 구현 |

➡️ [Day 2 상세 작업 기록](docs/day2.md)

---

## 📅 Development Log

| Day | A | B | C |
|---|---|---|---|
| **Day 3 — 2026-08-25** | Hardware Evidence 연동 및 Power·POST·Storage 진단 검증, iLO/OS Timestamp 및 NTP 동기화 검증 | Rule 기반 diagnosis Engine 구현 | FastAPI Incident Controller, Diagnosis 연동, Evidence/Diagnosis DB 저장, Incident Timeline 및 React Live Diagnosis UI 구현 |

➡️ [Day 3 상세 작업 기록](docs/day3.md)

---

## 📅 Development Log

| Day | A | B | C |
|---|---|---|---|
| **Day 4 — 2026-08-26** | Blackhole Route 기반 Network Fault 재현 및 Cisco SVI·Data Plane·OPNsense 장애 범위 검증, 수동 복구 검증 | NET-ROUTE-01 기반 Network Recovery Role 및 Runner 구현 + 복구 후 Evidence 재수집·상태 검증 | FastAPI Recovery API 및 React Recovery UI 구현 + NET-ROUTE-01 기반 Recovery Plan·Execute·Verification·CASE CLOSED 연동 |

➡️ [Day 4 상세 작업 기록](docs/day4.md)

---

## 📅 Development Log

| Day | A | B | C |
|---|---|---|---|
| **Day 5 — 2026-08-27** | Nginx Service Fault 환경 구성 및 Data Plane·iLO 정상 상태 분리, OPNsense 장애 관측·수동 복구 검증 | Nginx allowlist Recovery와 service-target Evidence 검증 구현; 실제 stop/recovery E2E `SUCCESS/VERIFIED` 완료 | Service Incident용 Suspect 제거 흐름(CULPRIT FOUND/CLEARED)과 Nginx Service Recovery UI 구현, Recovery·Verification·CASE CLOSED Timeline 및 Incident History 연동 |

➡️ [Day 5 상세 작업 기록](docs/day5.md)

---

## 📅 Development Log

| Day | A | B | C |
|---|---|---|---|
| **Day 6 — 2026-08-30** | Server #4 Spare/PXE Infrastructure 및 DHCP·ProxyDHCP·TFTP Handoff 검증; One-Time Network Boot 기반 Boot Failure·정상 복구 검증 | L1~L5 Escalation 및 `.208` read-only Standard Build 구현; PLAN_ONLY와 실제 Health Validation `VERIFIED` 완료 | Escalation 상태 DB/API와 2초 Polling 기반 Physical Recovery Progress UI 구현; `ESCALATION_REQUIRED → SPARE_ACTIVATING → PXE → CONFIGURING → READY` 실시간 전환 검증 |

➡️ [Day 6 상세 작업 기록](docs/day6.md)

---

## 📅 Development Log

| Day | A | B | C |
|---|---|---|---|
| **Day 7 — 2026-08-31** | Target #3 Node Failure 재현 및 Spare #4 Physical Recovery 검증; Backend 연계 및 Network·Service·Physical Recovery 3개 Scenario 통합 | Network/Service/Physical 공통 Workflow와 adapter·timeline·resume 계약 구현 및 mock 검증 | Incident State Machine, 2초 Timeline Polling, Rack Overview `FAILED/RECOVERING/READY`, Physical Recovery `VERIFYING`, `CASE CLOSED` 및 Recovery Time UI 구현 |

➡️ [Day 7 상세 작업 기록](docs/day7.md)

---

## 📅 Development Log

| Day | A | B | C |
|---|---|---|---|
| **Day 8 — 2026-09-01** | Reset Checklist 기반 Demo Baseline 검증 및 Network·Service·Physical Recovery 반복 안정성 검증; 수동 우회 절차·발표용 Evidence 확보 | B 통합·안전성 회귀 101건 완료; L3~L5 실제 실행은 Infrastructure adapter 미연결로 MANUAL_REQUIRED | 작성예정 |

➡️ [Day 8 상세 작업 기록](docs/day8.md)
