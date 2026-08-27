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
