# 📅 Day 4 — 2026-08-26

Day 4 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 4 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | 작성 예정 |
| **B** | Automation / Troubleshooting | NET-ROUTE-01 기반 Network Recovery Role 및 Runner 구현 + 복구 후 Evidence 재수집·상태 검증|
| **C** | Platform / Visualization | 작성 예정 |

---

# 👤 A — Day 4

> 작성 예정

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

> 작성 예정
