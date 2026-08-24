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

> Day 1 Baseline을 기준으로 network, OS, service 상태를 read-only로 자동 진단하고 호스트별 JSON Evidence와 역할 기반 판정 정책을 구현

### Development / Infrastructure
- `network_diagnostic`, `os_diagnostic`, `service_diagnostic` Ansible role 구성
- 진단 상태를 `PASS`, `WARN`, `FAIL`, `UNKNOWN`, `SKIP`으로 표준화
- category 및 host 집계 우선순위를 `FAIL > UNKNOWN > WARN > PASS > SKIP`으로 적용
- SSH를 baseline service로 설정하고 3개 managed node 간 TCP 22 reachability 대상 구성

### Implementation
- `network_diagnostic`
  - NIC link, QSFP NIC 존재, kernel driver/module, link state 진단
  - IP, Gateway, Route, DNS 진단
  - PXE ICMP reachability 및 TCP port reachability 진단
- `os_diagnostic`
  - systemd failed unit, filesystem, firewall, CPU load, memory 진단
  - critical systemd unit은 `FAIL`, non-critical unit은 `WARN`으로 분류
- `service_diagnostic`
  - process, listening port, HTTP health 진단 구조 구현
- 모든 진단 결과를 기존 schema의 호스트별 JSON Evidence로 생성

### Test / Verification
- SSH baseline 검증
  - `sshd` process `PASS`
  - TCP 22 listening port `PASS`
  - 3개 노드 간 TCP 22 reachability `PASS`
  - 실제 HTTP application 미배포로 HTTP health는 `SKIP`
- PXE Server `192.168.100.60` unreachable 정책 검증
  - `dca-target01`: `WARN`
  - `dca-target02`: `WARN`
  - `dca-spare01`: `FAIL` — Spare/Rebuild 대상의 rebuild capability 상실
- `dca-target01`
  - `systemd-networkd-wait-online.service` 실패를 non-critical `WARN`으로 판정
  - UFW inactive를 `WARN`으로 판정
- `dca-target02`, `dca-spare01`의 firewalld active를 `PASS`로 판정
- 자동 진단 Evidence JSON 3개 생성 완료

### Issue & Resolution
- Ubuntu firewall 검사에서 Ansible become prompt timeout 발생
  - 전체 become을 제거하고 root 권한이 필요한 read-only UFW 조회만 NOPASSWD 방식으로 변경
- 일반 계정의 UFW 상태 조회 권한 부족
  - 필요한 read-only 조회 명령만 최소 권한으로 허용하고 권한 상승 불가 시 `UNKNOWN` 처리
- Rocky의 `firewall-cmd --state`가 polkit authorization 오류 발생
  - 권한 상승이 필요 없는 `systemctl is-active firewalld` 기반 판정으로 변경
- 모든 systemd failed unit을 `FAIL`로 처리하던 문제
  - configurable critical unit 목록을 도입해 critical/non-critical을 `FAIL`/`WARN`으로 분리
- PXE 장애가 단순 누락되지 않도록 server role에 따라 target은 `WARN`, Spare/Rebuild는 `FAIL`로 분류
- port/service 미설정으로 진단이 `SKIP`되던 문제
  - SSH/22를 baseline으로 설정해 process, listening port 및 노드 간 reachability를 실제 검증

---

# 👤 C — Day 2

> 작성 예정
