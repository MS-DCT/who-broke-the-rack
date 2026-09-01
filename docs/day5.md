# 📅 Day 5 — 2026-08-27

Day 5 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 5 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | dca-target02 Nginx Service Fault 환경 구성 및 Data Plane·iLO 정상 상태 분리, OPNsense 관점 Service 장애·수동 복구 검증 |
| **B** | Automation / Troubleshooting | Nginx Service Recovery 및 대상 Service 기준 Evidence 검증 |
| **C** | Platform / Visualization | Service Incident용 Suspect 제거 흐름(CULPRIT FOUND/CLEARED)과 Nginx Service Recovery UI 구현, Recovery·Verification·CASE CLOSED Timeline 및 Incident History 연동 |

---

# 👤 A — Day 5

> dca-target02 Nginx Service Fault 시나리오 구성 및 Data Plane·iLO 정상 상태 분리, OPNsense 관점 장애 확인과 수동 Service Recovery 검증

## 1. Nginx Service Fault 사전 환경 확인 및 구성

### Development
- Service Fault 대상 `dca-target02 (192.168.100.207)` 선정
- Management Server `.206` 및 SSH Service를 장애 대상에서 제외
- Nginx 설치 여부 및 TCP 80 Port 사용 상태 사전 확인
- Nginx Repository 패키지 조회 후 `nginx 1.26.3` 설치
- Nginx 기본 Configuration 정상 여부 확인

### 검증
- 초기 Nginx 미설치 상태 확인
- 초기 TCP 80 Port 미사용 상태 확인
- Nginx `1.26.3` 설치 완료 확인
- `nginx -t` 결과 `syntax is ok / test is successful` 확인
- 설치 직후 `nginx = inactive` 확인
- 설치 직후 TCP 80 Port 미사용 상태 확인

### Outcome
- 기존 Service와 Port 충돌 없이 사용할 수 있는 Nginx Service Fault 환경 확보
- `.207 / nginx / TCP 80` 기반 Day 5 Service Fault 대상 확정

---

## 2. `/health` Endpoint 구성 및 정상 Baseline 확보

### Development
- Nginx 기본 Server Block의 `/etc/nginx/default.d/*.conf` Include 구조 확인
- Service 상태 확인용 `/health` Endpoint 구성

```nginx
location = /health {
    default_type text/plain;
    return 200 "OK\n";
}
```

- Health Check Configuration 경로 확정

```text
/etc/nginx/default.d/health.conf
```

- Nginx Service 시작 및 TCP 80 / HTTP Health 상태 확인

### 검증
- `/health` Configuration 생성 확인
- `nginx -t` Configuration Validation 성공 확인
- `nginx = active` 확인
- TCP `0.0.0.0:80`, `[::]:80` LISTEN 확인
- `.207 → http://192.168.100.207/health` HTTP `200 OK` 확인
- Response Body `OK` 확인

### Outcome
- Service Fault 전 Nginx 정상 Configuration 확보
- Service 상태 판별에 사용할 `/health` Endpoint 확보
- Nginx / TCP 80 / HTTP Health 정상 Baseline 확보

---

## 3. Firewall HTTP 허용 및 외부 Health Check 검증

### Development
- `.207`의 `firewalld` 활성 Zone 및 허용 Service 확인
- 초기 HTTP 미허용 상태 확인
- 외부 Health Check를 위해 HTTP Service 영구 허용 및 Firewall Reload

```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

- Management Server `.206`에서 `.207/health` 외부 접근 검증

### 검증
- `public` Zone의 Interface `eno49` 확인
- 초기 허용 Service `cockpit dhcpv6-client ssh` 확인
- HTTP 허용 후 `cockpit dhcpv6-client http ssh` 확인
- `.206 → http://192.168.100.207/health` HTTP `200 OK` 확인
- 외부 Health Check Response `OK` 확인

### Outcome
- TCP 80 외부 Health Check 가능 상태 구성
- Management Server에서 Target Nginx Service 정상 접근 확인
- Service Fault 전 외부 접근 정상 Baseline 확보

---

## 4. OPNsense Data Plane 관점 정상 Service 확인

### Development
- OPNsense `DATA_PLANE (192.168.100.90/24)`에서 Target `.207` Health Endpoint 접근
- Service Fault 주입 전 LB/Data Plane 관점 정상 상태 확보

### 검증
- OPNsense → `http://192.168.100.207/health` 접근 성공 확인
- HTTP `200 OK` 확인
- Response Body `OK` 확인

### Outcome
- OPNsense Data Plane에서 `.207:80` 접근 가능 상태 확인
- Service Fault 전 LB/Data Plane 관점 Nginx 정상 Baseline 확보

---

## 5. Nginx Service Fault 주입 및 장애 상태 분리 검증

### Development
- Network 및 SSH 연결에 영향을 주지 않고 Nginx Service만 중지하는 Fault 방식 적용

```bash
sudo systemctl stop nginx
```

- Service Fault 상태에서 Nginx / Data Plane / SSH / HTTP Health 각각 검증

### 검증
- `nginx = inactive` 확인
- `.207 → Gateway 192.168.100.200` Ping `0% packet loss` 확인
- `.207 → PXE 192.168.100.60` Ping `0% packet loss` 확인
- `sshd = active` 확인
- `.207 → /health` TCP 80 Connection 실패 확인

### Outcome
- Data Plane 정상 상태에서 Nginx Service만 실패하는 장애 재현
- Network Fault와 Service Fault를 구분할 수 있는 상태 확보
- SSH 관리 연결을 유지한 안전한 Service Fault 시나리오 확정

---

## 6. Service Fault 중 iLO / Hardware 정상 상태 확인

### Development
- Nginx Service Fault 유지 상태에서 Target `.207` iLO Web Interface 직접 확인
- OS Service 장애와 Hardware / Management 상태 분리 검증

### 검증
- iLO `192.168.0.207` Web Interface 정상 접속 확인
- `System Health = OK` 확인
- `iLO Health = OK` 확인
- `Server Power = ON` 확인

### Outcome
- Nginx Service 장애 중 Hardware 상태 정상 확인
- iLO Management Interface 정상 동작 확인
- Hardware / Data Plane 장애가 아닌 OS Service 계층 장애로 범위 분리

---

## 7. OPNsense 관점 Service Fault 확인

### Development
- Nginx Service가 `inactive`인 상태에서 OPNsense Data Plane을 통한 `.207:80/health` 재확인
- 정상 Baseline과 Service Fault 상태 비교

### 검증
- 정상 상태에서 OPNsense → `.207/health` HTTP `200 OK` 확인
- Nginx 중지 후 OPNsense → `.207:80` Connection 실패 확인

```text
curl: (7) Failed to connect to 192.168.100.207:80
```

### Outcome
- Service Fault가 Target 내부에서만 관측되는 상태가 아닌 외부 Data Plane에서도 확인되는 장애임을 검증
- OPNsense 관점 정상 → 장애 상태 변화 확인
- Target `.207`의 Nginx Service 장애 외부 관측 검증 완료

---

## 8. Manual Service Recovery 및 정상화 검증

### Development
- Service Fault 시 즉시 원복 가능한 수동 Recovery 방법 확정

```bash
sudo systemctl start nginx
```

- Nginx 재시작 후 Service 및 Health Endpoint 정상화 확인

### 검증
- `nginx = active` 확인
- `/health` HTTP `200 OK` 확인
- Response Body `OK` 확인

### Outcome
- Nginx Service 수동 복구 성공 확인
- Service Recovery 후 Health Endpoint 정상화 확인
- 시연 후 즉시 적용 가능한 Manual Service Recovery 방법 확보
- Target `.207` 정상 상태 원복 완료

---

## Day 5 A 최종 결과

- `dca-target02 (.207)` 기반 Nginx Service Fault 시나리오 구성
- Nginx `1.26.3` 및 TCP 80 기반 독립 Service 환경 구성
- `/etc/nginx/default.d/health.conf` 기반 `/health` Endpoint 구성
- Local / Management Server / OPNsense 관점 HTTP `200 OK` 정상 Baseline 확보
- `systemctl stop nginx` 기반 실제 Service Fault 재현
- Service Fault 중 Gateway / PXE Data Plane / SSH 정상 상태 확인
- Service Fault 중 iLO Web Interface / System Health / iLO Health / Server Power 정상 확인
- OPNsense 관점 `.207:80/health` Service 장애 확인
- Network / Hardware 정상 상태와 Service Fault 상태 분리 검증
- `systemctl start nginx` 수동 Recovery 및 HTTP `200 OK` 정상화 확인
- **Day 5 A — Service Fault 환경 구성·장애 재현·계층 분리·외부 관측·수동 복구 검증 완료**

---

## 👤 B — Day 5

- `dca_target02_nginx` allowlist와 고정 `/usr/sbin/nginx -t` argv를 적용했다.
- `config_content: null`은 Config backup/deploy/rollback을 건너뛰고 Nginx만 시작하도록 분리했다.
- Flat Evidence 키 계약을 유지하면서 service target을 `source`에 보존하고, SSH의 미설정 HTTP `SKIP`을 Nginx 판정에서 제외한다.
- `ssh SKIP + nginx PASS`는 `VERIFIED`, Nginx HTTP FAIL/UNKNOWN/SKIP/누락은 `ESCALATION_REQUIRED`로 mock 검증했다.
- Incident `INC-NGINX-FINAL-20260901T134444Z`로 실제 Nginx stop/recovery E2E를 수행해 `SVC-HTTP-01/MATCHED`, PLAN_ONLY, exit 0, `SUCCESS/VERIFIED`를 확인했다.
- Config checksum은 전후 `8732f8534d075efed49c95f68b9a457b487f2b8b9213de9f6f79041b3dc62390`으로 동일했고, SSH HTTP `SKIP`은 `excluded_checks`로 분리됐다. 종료 시 Nginx active와 내부·외부 `/health` HTTP 200/body `OK`를 확인했다.

---

# 👤 C — Day 5

> Service Incident 진단 결과를 Suspect Card, Recovery UI, Timeline, Incident History에 연결해 장애 원인 판별부터 복구 결과까지 하나의 화면 흐름으로 시각화

## 1. Service Incident Suspect 제거 흐름 구현

### Development
- Diagnosis Engine의 `rule_id`를 Suspect Card와 연결
- `SVC-*` Rule이 MATCHED되면 `Service`를 Root Cause로 자동 선택
- Root Cause로 판정된 Card에 `CULPRIT FOUND` 표시
- Root Cause가 확정된 이후 정상 상태인 다른 Suspect Card에는 `CLEARED` 표시
- CLEARED Card는 opacity 및 취소선 스타일을 적용해 조사 대상에서 제외된 상태를 시각적으로 구분

### 검증
- `dca-target02`의 Nginx Service를 중지한 상태에서 Incident Diagnosis 실행
- Diagnosis 결과 `SVC-HTTP-01 / MATCHED` 확인
- Service 계층이 Root Cause로 선택되는 흐름 확인
- 정상 판정된 Suspect Card가 `CLEARED` 상태로 전환되는 UI 동작 확인

### Outcome
- Service Fault 발생 시 여러 장애 후보 중 Service가 최종 원인으로 좁혀지는 과정을 UI에서 확인 가능
- 단순 Root Cause 출력이 아니라 실제 Troubleshooting의 Suspect Elimination 흐름을 시각화

---

## 2. Nginx Service Recovery UI 구현

### Development
- Diagnosis 결과가 `SVC-HTTP-01 / MATCHED`일 때만 Service Recovery Card가 나타나도록 구성
- Recovery 대상 정보를 다음과 같이 고정해 Backend Recovery API와 연결

```text
Target: dca-target02
Service: nginx.service
Profile: dca_target02_nginx
HTTP Health Check: enabled
```

- `Plan Recovery`와 `Execute Recovery`를 분리
- Recovery 요청 시 다음 Service Recovery 변수를 Backend로 전달

```json
{
  "profile": "dca_target02_nginx",
  "config_content": null,
  "http_enabled": true
}
```

- Recovery 결과에서 다음 상태를 UI에 표시하도록 구현
  - Recovery Mode
  - Recovery Result
  - Verification Status
  - `CASE CLOSED`

### 검증
- Nginx Service Fault 진단 후 `SERVICE RECOVERY` Card 자동 표시 확인
- `Recover Nginx Service`
- `Target: dca-target02 / nginx.service`
- `Plan Recovery` 및 `Execute Recovery` 흐름이 동일 Incident에 연결되는 구조 확인

### Outcome
- Root Cause가 Network이면 Network Recovery, Service이면 Service Recovery가 자동 선택되는 Rule 기반 Recovery UI 구성
- Scenario별 별도 화면이 아닌 동일 Incident UI에서 Recovery Action을 선택할 수 있도록 통합

---

## 3. Recovery / Verification Timeline 확장

### Development
- 기존 Incident Timeline의 `ACTION` 결과를 Recovery 단계에 맞게 세분화
- Recovery Action 저장 결과를 파싱하여 다음 Timeline Event를 생성

```text
RECOVERY
VERIFICATION
CASE_CLOSED
```

- PLAN_ONLY 상태는 `RECOVERY` Event로 표시
- 실제 Recovery 수행 후 Verification 결과가 존재하면 `VERIFICATION` Event 추가
- Incident 상태가 `CLOSED`가 되면 마지막에 `CASE_CLOSED` Event 추가
- Frontend Timeline은 동일 Event Renderer를 사용해 Evidence / Diagnosis / Recovery / Verification을 시간 순으로 표시

### Outcome
- Incident 생성부터 장애 진단, Recovery, Verification, 종료까지 하나의 Timeline에서 추적 가능
- Recovery 성공 여부뿐 아니라 복구 이후 검증 결과까지 UI에서 확인 가능
- 최종 정상화 시 `CASE_CLOSED` 상태를 명확하게 표시

---

## 4. Incident History UI 구현

### Development
- Backend `/incidents` API를 사용해 기존 Incident 목록 조회
- 최근 Incident를 시작 시간 기준으로 정렬
- 최근 5개의 Incident를 화면에 표시
- 각 Incident에 다음 정보 표시
  - Incident ID
  - Server ID
  - Incident Status
- 새로운 Incident 생성 또는 Recovery 상태 변경 시 History 자동 갱신
- `Refresh History` 버튼을 통한 수동 갱신 기능 추가
- 긴 상태 문자열이 Card 영역을 벗어나지 않도록 History Layout 및 Overflow Style 보정

### 검증
- `ROOT_CAUSE_FOUND`
- `INSUFFICIENT_EVIDENCE`
- `CLOSED`

등 서로 다른 Incident 상태가 History 목록에 정상 표시되는 것 확인

### Outcome
- 현재 Incident뿐 아니라 이전 장애 처리 기록까지 동일 Dashboard에서 확인 가능
- 반복 시연 시 각 Incident의 상태 변화를 비교할 수 있는 최소 Incident History 기능 확보

---

## 5. Service Fault UI 통합 검증

### 검증
- `dca-target02` Nginx Service Fault 상태에서 실제 Incident 생성
- Service Evidence 기반 Diagnosis 수행
- `SVC-HTTP-01 / MATCHED` 확인
- Service Root Cause 및 `SERVICE RECOVERY` Card 자동 표시 확인
- React Production Build 정상 완료
- Incident History 및 Timeline UI 동작 확인

### 참고
- C의 Service Recovery UI와 Backend API 연결은 완료
- C 테스트 환경의 `.206`에는 일부 Service Recovery Automation 코드가 이전 mock-only 버전으로 남아 있어 C 화면을 통한 최종 Execute 통합 검증은 해당 로컬 코드 동기화 후 추가 확인 가능
- B 영역에서는 실제 Nginx stop → Recovery E2E `SUCCESS / VERIFIED`가 별도로 검증됨

---

## Day 5 C 최종 결과

- `SVC-HTTP-01` 기반 Service Root Cause 자동 시각화
- Service Suspect `CULPRIT FOUND` 표시 구현
- 정상 Suspect `CLEARED` 처리 및 시각적 제거 효과 구현
- Nginx Service Recovery Card 구현
- Network / Service Rule에 따른 Recovery UI 자동 분기
- `Plan Recovery → Execute Recovery` UI 흐름 구현
- Recovery Mode / Result / Verification 상태 표시
- `RECOVERY → VERIFICATION → CASE_CLOSED` Timeline 구조 구현
- 최근 5개 Incident를 표시하는 Incident History UI 구현
- 실제 Nginx Fault에서 `SVC-HTTP-01 / MATCHED` 및 Service Recovery UI 노출 확인
- **Day 5 C — Service Incident 시각화·Recovery UI·Verification Timeline·Incident History 구현 완료**
