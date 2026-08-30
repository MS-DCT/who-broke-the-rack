# 📅 Day 5 — 2026-08-27

Day 5 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 5 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | dca-target02 Nginx Service Fault 환경 구성 및 Data Plane·iLO 정상 상태 분리, OPNsense 관점 Service 장애·수동 복구 검증 |
| **B** | Automation / Troubleshooting | 작성 예정 |
| **C** | Platform / Visualization | 작성 예정 |

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

> 작성 예정

---

# 👤 C — Day 5

> 작성 예정
