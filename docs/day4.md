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

> day3내용인 pxe부트 최종 완료 

# PXE Bare-Metal Provisioning

This directory contains the PXE provisioning configuration used by
**WHO BROKE THE RACK** to rebuild physical Server #4.

## Target

| Item | Value |
|---|---|
| Hardware | HPE ProLiant DL360 Gen9 |
| Server | Server #4 / dca-spare01 |
| iLO | 192.168.0.208 |
| Final Data IP | 192.168.100.208 |
| PXE NIC | Mellanox ConnectX-3 Pro |
| PXE NIC MAC | 70:10:6f:a1:aa:41 |
| DHCP Server | 192.168.100.90 |
| PXE/TFTP Server | 192.168.100.60 |
| Provisioned OS | Rocky Linux 9.8 |

---

## Architecture

```text
Server #4
    |
    | PXE DHCP Request
    v
DHCP Server (.90)
    |
    | IP / Gateway / DNS
    v
Server #4

Server #4
    |
    | PXE Request
    v
dnsmasq proxyDHCP (.60)
    |
    | Next Server = 192.168.100.60
    | Boot File = pxelinux.0
    v
TFTP Server (.60)
    |
    | pxelinux.0
    | Rocky 9.8 vmlinuz
    | Rocky 9.8 initrd.img
    v
Rocky Installer
    |
    | HTTP
    v
192.168.100.60:8080
    |
    +-- rocky9-repo/
    |
    +-- ks/server4.ks
```

---

## Provisioning Flow

```text
iLO Network Boot
        ↓
Mellanox ConnectX-3 Pro PXE
        ↓
DHCP Server 192.168.100.90
        ↓
dnsmasq proxyDHCP 192.168.100.60
        ↓
TFTP / PXELINUX
        ↓
Rocky Linux 9.8 Kernel + initrd
        ↓
Local HTTP Repository
        ↓
Kickstart
        ↓
Disk Initialization
        ↓
Automatic LVM Partitioning
        ↓
Rocky Linux 9.8 Minimal Installation
        ↓
SSH Enablement
        ↓
Automatic Reboot
        ↓
SSH Validation
        ↓
Static IP 192.168.100.208
```

---

## PXE Server

PXE server information:

```text
Hostname  : zt-storage
IP        : 192.168.100.60
Interface : bond0
TFTP      : UDP 69
HTTP      : TCP 8080
```

Required packages:

```bash
sudo apt update
sudo apt install -y tftpd-hpa pxelinux syslinux-common dnsmasq-base
```

TFTP root:

```text
/srv/tftp
```

Example TFTP configuration:

```ini
TFTP_USERNAME="tftp"
TFTP_DIRECTORY="/srv/tftp"
TFTP_ADDRESS=":69"
TFTP_OPTIONS="--secure"
```

Verify TFTP:

```bash
sudo systemctl status tftpd-hpa
sudo ss -lunp | grep ':69 '
```

---

## proxyDHCP

The existing DHCP server at:

```text
192.168.100.90
```

continues to provide:

```text
IP Address
Subnet Mask
Gateway
DNS
```

The PXE server at:

```text
192.168.100.60
```

provides only PXE boot information through dnsmasq proxyDHCP:

```text
Next Server : 192.168.100.60
Boot File   : pxelinux.0
```

The PXE configuration is restricted to Server #4 using its Mellanox NIC MAC:

```text
70:10:6f:a1:aa:41
```

This prevents unrelated PXE clients from receiving the Server #4 provisioning configuration.

---

## PXELINUX

Server #4 uses Legacy BIOS PXE.

PXELINUX loads the Rocky Linux 9.8 installer:

```text
rocky9/vmlinuz
rocky9/initrd.img
```

The Mellanox NIC is explicitly mapped as:

```text
pxe0
```

using:

```text
ifname=pxe0:70:10:6f:a1:aa:41
```

The installer obtains its temporary address through DHCP:

```text
ip=:::::pxe0:dhcp
```

Kickstart:

```text
inst.ks=http://192.168.100.60:8080/ks/server4.ks
```

Installation repository:

```text
inst.stage2=http://192.168.100.60:8080/rocky9-repo/
```

---

## Local Rocky Linux Repository

Rocky Linux 9.8 Minimal ISO is mounted on the PXE server.

Example mount:

```bash
sudo mkdir -p /srv/rocky-http/rocky9-repo

sudo mount -o loop,ro \
  /srv/rocky-http/Rocky-9.8-x86_64-minimal.iso \
  /srv/rocky-http/rocky9-repo
```

The repository is served through HTTP:

```bash
nohup python3 -m http.server 8080 \
  --bind 192.168.100.60 \
  --directory /srv/rocky-http \
  >/tmp/rocky-http.log 2>&1 &
```

Repository URL:

```text
http://192.168.100.60:8080/rocky9-repo/
```

Validation:

```bash
curl -I http://192.168.100.60:8080/rocky9-repo/.treeinfo

curl -I \
http://192.168.100.60:8080/rocky9-repo/Minimal/repodata/repomd.xml
```

Expected:

```text
HTTP/1.0 200 OK
```

---

## Kickstart

Kickstart URL:

```text
http://192.168.100.60:8080/ks/server4.ks
```

The Kickstart configuration performs:

```text
Clear existing partitions on /dev/sda
Automatic LVM partitioning
Rocky Linux 9.8 Minimal installation
Create rocky user
Add rocky user to wheel group
Enable SSH
Enable firewall SSH service
Automatic reboot after installation
```

WARNING:

```text
clearpart --all --drives=sda
```

removes all existing partitions from Server #4 `/dev/sda`.

Provisioning should only be started after confirming that Server #4 is the intended Spare / Rebuild Target.

---

## Password Handling

Do not commit a real password or password hash to Git.

The repository version of the Kickstart file should use:

```text
<REPLACE_WITH_SHA512_PASSWORD_HASH>
```

Generate the password hash only on the PXE server:

```bash
openssl passwd -6
```

Replace the placeholder only in the runtime copy.

Do not commit:

```text
Real passwords
Password hashes
SSH private keys
iLO credentials
Administrator credentials
```

---

## Rocky Linux 10 Compatibility Finding

Rocky Linux 10 was initially tested.

The PXE firmware successfully downloaded:

```text
pxelinux.0
vmlinuz
initrd.img
```

However, networking failed after the Rocky Linux 10 installer kernel took control of the Mellanox ConnectX-3 Pro NIC.

The target NIC uses the `mlx4` driver family.

Rocky Linux 9.8 was then tested and the following drivers loaded successfully:

```text
mlx4_core
mlx4_en
```

Rocky Linux 9.8 was therefore selected as the provisioning OS for Server #4.

---

## Provisioning Result

The unattended installation completed successfully.

Initial DHCP address after installation:

```text
192.168.100.217
```

SSH validation:

```bash
ssh rocky@192.168.100.217
```

Successful login:

```text
[rocky@dca-spare01 ~]$
```

---

## Static IP Configuration

After provisioning, Server #4 was changed from the temporary DHCP address:

```text
192.168.100.217
```

to the final project Data IP:

```text
192.168.100.208/24
```

Configuration:

```bash
sudo nmcli con mod pxe0 \
  ipv4.method manual \
  ipv4.addresses 192.168.100.208/24 \
  ipv4.gateway 192.168.100.90 \
  ipv4.dns 192.168.100.90 \
  connection.autoconnect yes

sudo nmcli con up pxe0
```

Final SSH:

```bash
ssh rocky@192.168.100.208
```

---

## Final Validation

Commands:

```bash
ip -br addr
ip route
cat /etc/rocky-release
```

Final result:

```text
pxe0             UP   192.168.100.208/24

default via 192.168.100.90 dev pxe0 proto static metric 100

Rocky Linux release 9.8 (Blue Onyx)
```

Final system:

```text
Hostname : dca-spare01
OS       : Rocky Linux 9.8
NIC      : pxe0
IP       : 192.168.100.208/24
Gateway  : 192.168.100.90
SSH      : Working
```

---

## Day 3 Status

```text
PXE Network Boot                 PASS
DHCP                             PASS
proxyDHCP                        PASS
TFTP                             PASS
PXELINUX                         PASS
Rocky Linux 9.8 Kernel/initrd    PASS
Mellanox mlx4 Networking         PASS
Local HTTP Repository            PASS
Kickstart Delivery               PASS
Automatic Disk Provisioning      PASS
Unattended OS Installation       PASS
Automatic Reboot                 PASS
SSH Access                       PASS
Static IP 192.168.100.208        PASS
```

**Day 3 PXE Bare-Metal Provisioning Complete.**
