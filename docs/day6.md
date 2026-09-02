# 📅 Day 6 — 2026-08-30

Day 6 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 6 작업 |
|---|---|---|
| **A** | Server #4 Spare/PXE Infrastructure 검증 및 One-Time Network Boot 기반 Boot Failure·복구, DHCP·ProxyDHCP·TFTP/PXELINUX Handoff 구조 검증 |
| **B** | Automation / Troubleshooting | Escalation Engine 및 read-only Standard Build 검증 |
| **C** | Platform / Visualization | Escalation 상태 DB/API와 2초 Polling 기반 Physical Recovery Progress UI 구현; `ESCALATION_REQUIRED → SPARE_ACTIVATING → PXE → CONFIGURING → READY` 실시간 전환 검증 |

---

# 👤 A — Day 6

> Server #4 Spare / Rebuild Infrastructure 상태 및 PXE Provisioning 경로 검증, One-Time Network Boot 기반 안전한 Boot Failure·복구 검증, DHCP·ProxyDHCP·TFTP/PXELINUX 기반 PXE Handoff 구조 확인

## 1. Server #4 Spare / Rebuild Target 상태 검증

Server #4를 Spare / Rebuild Target으로 사용하기 위한 현재 시스템 상태 확인.

- Hostname `dca-spare01` 확인
- Rocky Linux 9.8 부팅 상태 확인
- Data Plane IP `192.168.100.208/24` 확인
- Default Route 및 Data Plane Network 상태 확인
- PXE Server `192.168.100.60` 통신 가능 상태 확인

### 검증 결과

```text
Hostname        : dca-spare01
OS              : Rocky Linux 9.8
Data Plane IP   : 192.168.100.208/24
PXE Server      : 192.168.100.60
PXE 통신        : 정상
```

Server #4의 OS 및 Data Plane Network 정상 상태 확인을 통한 Spare / Rebuild Target Baseline 확보.

---

## 2. PXE 재설치 후 QSFP+ NIC 상태 검증

Server #4에 선행 수행된 Rocky Linux 9.8 PXE 재설치 이후 Infrastructure 관점의 QSFP+ NIC 상태 직접 검증.

해당 Rocky Linux 9.8 PXE 재설치는 C 담당자가 수행했으며, A는 재설치 완료 이후 Server #4의 NIC / Link / Data Plane 상태 검증 수행.

기존 계획에서는 QSFP+ Interface를 `eno49`로 예상했으나 실제 재설치된 OS에서는 `pxe0`로 인식됨을 확인.

### Driver 확인

```text
Interface : pxe0
Driver    : mlx4_en
Bus Info  : 0000:04:00.0
```

### Link 상태 확인

```text
Speed         : 40000Mb/s
Duplex        : Full
Link detected : yes
```

### Network 상태 확인

```text
Interface : pxe0
IP        : 192.168.100.208/24
MAC       : 70:10:6f:a1:aa:41
```

- `mlx4_en` Driver 정상 Load 확인
- QSFP+ NIC 40Gbps 인식 확인
- Full Duplex 확인
- Physical Link UP 확인
- Data Plane IP `192.168.100.208/24` 확인
- PXE Server `192.168.100.60` 통신 정상 확인

PXE 재설치 이후 QSFP+ NIC `pxe0` 정상 인식 및 Data Plane Network 정상 상태 검증.

---

## 3. Server #4 iLO / Hardware 상태 검증

Server #4의 물리 Hardware 및 Remote Management 상태 확인을 위해 iLO 접속 후 System 상태 검증.

### iLO 상태

```text
Server        : HPE ProLiant DL360 Gen9
iLO           : iLO 4
System Health : OK
iLO Health    : OK
Server Power  : ON
```

### Hardware Health 확인

- BIOS / Hardware Health 정상
- Fan 상태 정상
- Memory 상태 정상
- Network 상태 정상
- Power 상태 정상
- Power Supply 상태 정상
- Processor 상태 정상
- Storage 상태 정상
- Temperature 상태 정상

Boot Failure Scenario 수행 전 Server #4 Hardware 정상 상태 확보.

---

## 4. Legacy BIOS Boot Mode 및 Boot Order 확인

Server #4의 PXE Boot 가능 여부 확인을 위해 iLO Remote Console에서 BIOS Boot 설정 확인.

### Boot Mode

```text
Boot Mode           : Legacy BIOS Mode
UEFI Optimized Boot : Disabled
Boot Order Policy   : Retry Boot Order Indefinitely
```

### Legacy BIOS Boot Order

QSFP+ NIC가 Legacy BIOS Boot Order의 우선 Boot Device로 등록되어 있음을 확인.

```text
Embedded FlexibleLOM 1 Port 1
HPE InfiniBand FDR/Ethernet
10Gb/40Gb 2-port 544+FLR-QSFP Adapter
```

Server #4의 QSFP+ NIC 기반 Network Boot 가능 구성 확인.

---

## 5. One-Time Network Boot 동작 검증

정상 OS Boot Order를 영구 변경하지 않고 PXE Boot 경로를 검증하기 위해 F11 Legacy BIOS One-Time Boot Menu 사용.

### One-Time Boot Menu

```text
1. CD-ROM
2. USB DriveKey
3. HDD
4. One Time Boot to Network
5. UEFI Boot Menu
6. UEFI Shell
7. Intelligent Provisioning
8. System Utilities
0. Exit
```

`One Time Boot to Network` 선택 후 QSFP+ NIC를 통한 실제 Network Boot 동작 확인.

### PXE NIC 초기화 결과

```text
NIC       : ConnectX-3Pro
MAC       : 70:10:6f:a1:aa:41
PCI       : 04:00.0
Link      : UP
DHCP      : 성공
```

QSFP+ NIC 초기화 → Physical Link UP → DHCP 요청 단계 정상 진행 확인.

---

## 6. ZT Storage PXE Server 상태 검증

PXE Server `192.168.100.60`에 직접 접속하여 Server #4 PXE Boot에 필요한 TFTP 및 HTTP 서비스 상태 확인.

### PXE Server Network

```text
Host       : zt-storage
PXE Server : 192.168.100.60
Interface  : bond0
```

### TFTP 상태

- `tftpd-hpa` Service Active 확인
- UDP 69 Port Listening 확인
- TFTP Root `/srv/tftp` 확인
- `pxelinux.0` 존재 확인

### TFTP 주요 파일

```text
/srv/tftp/
├── pxelinux.0
├── ldlinux.c32
├── pxelinux.cfg/
│   └── default
├── rocky9/
│   ├── vmlinuz
│   └── initrd.img
└── rocky10/
    ├── vmlinuz
    └── initrd.img
```

PXE Boot에 필요한 Bootloader 및 Rocky Linux Kernel / initrd 파일 존재 확인.

---

## 7. Server #4 PXE Boot Configuration 확인

`/srv/tftp/pxelinux.cfg/default` 확인을 통한 Server #4 PXE Boot 설정 검증.

```text
DEFAULT rocky9
PROMPT 0
TIMEOUT 50

LABEL rocky9
    KERNEL rocky9/vmlinuz
    IPAPPEND 2
    APPEND initrd=rocky9/initrd.img rd.neednet=1 ifname=pxe0:70:10:6f:a1:aa:41 ip=:::::pxe0:dhcp bootdev=pxe0 inst.stage2=http://192.168.100.60:8080/rocky9-repo/ inst.ks=http://192.168.100.60:8080/ks/server4.ks
```

### 주요 설정

```text
Interface         : pxe0
MAC               : 70:10:6f:a1:aa:41
Kernel            : rocky9/vmlinuz
Initrd            : rocky9/initrd.img
Installation Repo : http://192.168.100.60:8080/rocky9-repo/
Kickstart         : http://192.168.100.60:8080/ks/server4.ks
```

PXE Configuration의 MAC Address와 Server #4 QSFP+ NIC 실제 MAC Address 일치 확인.

---

## 8. Rocky Linux 9 HTTP 설치 Source 검증

PXE 설치 과정에서 Kernel Boot 이후 사용하는 Rocky Linux 설치 Repository 및 Kickstart File 제공 상태 확인.

### HTTP Service

```text
192.168.100.60:8080
```

### Rocky Linux Repository

```text
http://192.168.100.60:8080/rocky9-repo/
```

### Server #4 Kickstart

```text
http://192.168.100.60:8080/ks/server4.ks
```

Repository 및 Kickstart File HTTP 접근 가능 상태 확인.

C 담당자의 실제 PXE 설치 기록에서도 Rocky Linux Installer가 `.60:8080`의 Repository 및 Kickstart File에 접근하고 Package를 전달받은 이력 확인.

**결과: PXE Boot 이후 Rocky Linux 9.8 설치 Source 제공 경로 확인**

---

## 9. Server #4 Kickstart 구성 검증

실제 Server #4 설치에 사용된 Kickstart File 확인.

```text
/srv/rocky-http/ks/server4.ks
```

### 주요 구성

- Korean Locale 설정
- `Asia/Seoul` Timezone 설정
- DHCP 기반 Network 설정
- Server #4 QSFP+ MAC Address 기준 Network Device 지정
- Hostname `dca-spare01` 지정
- Rocky Linux 9 HTTP Repository 지정
- `sda` 대상 Disk 초기화 및 자동 Partition 구성
- LVM 기반 자동 Partition 구성
- Minimal Environment 설치
- OpenSSH Server 설치
- `sshd` 자동 Enable
- 설치 완료 후 자동 Reboot

Kickstart File을 통한 Server #4 Rocky Linux 9.8 자동 설치 구성 확인.

---

## 10. OPNsense Kea DHCP 역할 및 PXE Lease 검증

Server #4 PXE Boot 과정에서 OPNsense `192.168.100.90`의 Kea DHCP가 Network 정보 제공 역할을 수행함을 확인.

### DHCP Subnet

```text
Subnet : 192.168.100.0/24
Pool   : 192.168.100.201 - 192.168.100.224
```

Kea DHCP의 역할:

```text
IP Address
Subnet
Default Gateway
DNS
```

C 담당자 확인 결과, 실제 Rocky Linux 9.8 PXE 설치를 위해 OPNsense Kea의 다음 항목을 별도로 변경하지 않았음을 확인.

```text
Next Server        : 변경 없음
TFTP Server        : 변경 없음
TFTP Bootfile Name : 변경 없음
Reservations       : 추가 없음
Options            : 추가 없음
```

따라서 설치 후 Kea PXE 관련 설정을 원복하는 작업 역시 수행되지 않음.

A의 Day 6 재현에서는 Server #4가 `.202`를 DHCP Lease로 획득했으며, C 담당자의 선행 PXE 설치 성공 과정에서는 `.217`을 임시 DHCP 주소로 사용.

```text
A Day 6 재현 Lease       : 192.168.100.202
C 선행 PXE 설치 임시 IP  : 192.168.100.217
설치 완료 후 최종 IP     : 192.168.100.208/24
```

각 주소는 서로 다른 PXE 실행 시점의 DHCP Lease 및 최종 Static IP로 구분.

**결과: OPNsense Kea DHCP의 Network 정보 제공 역할 및 Server #4 DHCP 경로 확인**

---

## 11. DHCP / ProxyDHCP 기반 PXE Handoff 구조 확인

C 담당자 확인을 통해 Server #4 PXE 설치 성공 당시 사용된 Handoff 구조 확인.

OPNsense Kea DHCP가 PXE Bootfile 정보를 직접 제공하는 방식이 아니라, PXE Server `.60`의 `dnsmasq ProxyDHCP`가 PXE Boot 정보만 별도로 제공하는 구조 사용.

### 역할 분리

```text
OPNsense Kea DHCP (.90)
    └─ IP / Gateway / DNS 제공

dnsmasq ProxyDHCP (.60)
    └─ PXE Boot 정보 제공
       ├─ Bootfile : pxelinux.0
       └─ Next Server : 192.168.100.60

TFTP / PXELINUX (.60)
    └─ pxelinux.0 / Kernel / initrd 제공

HTTP (.60:8080)
    └─ Rocky Linux 9.8 Repository / Kickstart 제공
```

따라서 OPNsense Kea Configuration에서 다음 항목이 비어 있는 상태는 PXE 구성 오류의 직접 근거가 아님을 확인.

```text
Next Server        : 미설정
TFTP Server        : 미설정
TFTP Bootfile Name : 미설정
Reservations       : 0
Options            : 0
```

PXE Boot 정보는 Kea가 아닌 `.60`의 ProxyDHCP가 담당하는 구조로 확인.

**결과: DHCP와 PXE Boot 정보 전달 역할이 분리된 ProxyDHCP 기반 Handoff 구조 확인**

---

## 12. Server #4 전용 ProxyDHCP 구성 확인

Repository에 작성된 Server #4 전용 ProxyDHCP 설정 확인.

```text
automation/pxe/dnsmasq/pxe-proxy.conf
```

해당 설정은 Server #4의 PXE NIC MAC을 기준으로 대상 서버를 제한하도록 구성.

```text
Server #4 MAC : 70:10:6f:a1:aa:41
Bootfile      : pxelinux.0
Next Server   : 192.168.100.60
```

C 담당자의 선행 설치 기록에서 Server #4 PXE 요청에 대해 다음 정보가 전달된 이력 확인.

```text
tags          : server4
bootfile name : pxelinux.0
next server   : 192.168.100.60
```

동시에 다른 MAC Address의 PXE 요청은 `proxy-ignored` 처리된 기록 확인.

이를 통해 ProxyDHCP가 공용 Subnet 전체에 무조건 PXE 정보를 전달하는 방식이 아니라 Server #4 MAC을 기준으로 PXE 정보를 제공하도록 구성되었음을 확인.

### Repository PXE 구성

```text
automation/pxe/
├── README.md
├── dnsmasq/
│   └── pxe-proxy.conf
├── kickstart/
│   └── server4.ks
└── tftp/
    └── pxelinux.cfg
```

**결과: Server #4 한정 ProxyDHCP 구성 및 PXE Boot 정보 전달 방식 확인**

---

## 13. DHCP Packet Capture 기반 현재 PXE Handoff 상태 검증

Server #4의 One-Time Network Boot 수행과 동시에 OPNsense Data Plane Interface에서 DHCP Packet Capture 수행.

```bash
tcpdump -ni vlan0.100 -vvv -s0 port 67 or port 68
```

### DHCPDISCOVER

```text
MAC          : 70:10:6f:a1:aa:41
Vendor-Class : PXEClient:Arch:00000:UNDI:002001
Architecture : 0
```

PXE Client가 DHCP Parameter Request 과정에서 TFTP Server 및 Bootfile 정보를 요청함을 확인.

```text
Option 66 : TFTP Server
Option 67 : Bootfile
```

### DHCPOFFER / DHCPACK

A의 현재 재현에서는 OPNsense Kea DHCP로부터 `.202` Lease 및 Network 정보 정상 획득.

```text
IP              : 192.168.100.202
Subnet          : 192.168.100.0/24
Default Gateway : 192.168.100.90
DHCP Server     : 192.168.100.90
DNS             : 192.168.100.90
```

Kea의 DHCPOFFER / DHCPACK에 Option 66 / 67이 포함되지 않은 상태 확인.

다만 C 담당자의 구성 이력 확인 결과, 해당 정보는 Kea가 아닌 `.60`의 dnsmasq ProxyDHCP가 별도로 제공하도록 설계된 구조임을 확인.

Day 6 현재 확인 시점에는 `.60`에서 ProxyDHCP가 동작하지 않는 상태였으며 이에 따라 Network Boot가 다음 단계에서 중단.

```text
Server #4 QSFP+ NIC
        ↓
Physical Link UP
        ↓
DHCPDISCOVER
        ↓
Kea DHCP (.90)
        ↓
IP / Gateway / DNS 정상 획득
        ↓
ProxyDHCP (.60) PXE Boot 정보 미수신
        ↓
Boot File 획득 단계 진행 불가
        ↓
Nothing to boot
```

따라서 현재 재현의 `Nothing to boot` 결과를 Kea DHCP 설정 오류로 판단하지 않고 **현재 시점 ProxyDHCP Boot 정보가 제공되지 않은 상태에서 발생한 PXE Handoff 중단**으로 정리.

공용 Infrastructure임을 고려하여 `.60`의 ProxyDHCP 재활성화 및 Kea 설정 변경 미수행.

---

## 14. 선행 PXE Provisioning 성공 경로 확인

C 담당자가 수행한 Server #4 Rocky Linux 9.8 PXE 설치 기록을 통해 실제 성공 경로 확인.

### PXE Server 준비

```bash
sudo apt update
sudo apt install -y tftpd-hpa pxelinux syslinux-common dnsmasq-base
```

### TFTP 확인

```bash
sudo systemctl status tftpd-hpa
sudo ss -lunp | grep ':69 '
```

### Rocky Linux 9.8 ISO Mount

```bash
sudo mkdir -p /srv/rocky-http/rocky9-repo
sudo mount -o loop,ro \
  /srv/rocky-http/Rocky-9.8-x86_64-minimal.iso \
  /srv/rocky-http/rocky9-repo
```

### HTTP Server

```bash
nohup python3 -m http.server 8080 \
  --bind 192.168.100.60 \
  --directory /srv/rocky-http \
  >/tmp/rocky-http.log 2>&1 &
```

### Repository 확인

```bash
curl -I http://192.168.100.60:8080/rocky9-repo/.treeinfo
curl -I http://192.168.100.60:8080/rocky9-repo/Minimal/repodata/repomd.xml
```

선행 설치 과정에서 다음 흐름으로 Rocky Linux 9.8 Installer 및 Package Download 진행 확인.

```text
DHCP (.90)
    ↓
ProxyDHCP (.60)
    ↓
TFTP / PXELINUX (.60)
    ↓
Rocky Linux Kernel / initrd
    ↓
HTTP (.60:8080)
    ↓
Rocky Linux 9.8 Repository
    +
Kickstart server4.ks
    ↓
Rocky Linux 9.8 설치
```

설치 과정에서 Server #4는 DHCP Pool의 임시 주소 `.217` 사용.

```text
PXE 설치 중 임시 IP : 192.168.100.217
```

설치 완료 이후 `pxe0`를 최종 Data Plane 주소 `.208`로 설정.

```bash
sudo nmcli con mod pxe0 \
  ipv4.method manual \
  ipv4.addresses 192.168.100.208/24 \
  ipv4.gateway 192.168.100.90 \
  ipv4.dns 192.168.100.90 \
  connection.autoconnect yes

sudo nmcli con up pxe0
```

최종 상태:

```text
Hostname  : dca-spare01
OS        : Rocky Linux 9.8
Interface : pxe0
IP        : 192.168.100.208/24
Gateway   : 192.168.100.90
```

**결과: C 담당자의 선행 실행 기록을 통한 Server #4 Rocky Linux 9.8 PXE Provisioning 성공 경로 확인**

---

## 15. 안전한 Boot Failure Scenario 검증

Disk, Partition, GRUB 및 기존 Rocky Linux OS를 손상시키지 않고 실제 Boot Failure를 재현하기 위해 One-Time Network Boot 방식 사용.

### 장애 전 Baseline

```text
Server      : dca-spare01
OS          : Rocky Linux 9.8
System      : running
Interface   : pxe0
IP          : 192.168.100.208/24
Speed       : 40000Mb/s
Duplex      : Full
Link        : yes
PXE Server  : 192.168.100.60 reachable
iLO Health  : OK
Power       : ON
```

### Boot Failure 재현

Server Reboot 후 F11 Legacy BIOS One-Time Boot Menu 진입.

```text
One Time Boot to Network
```

현재 Infrastructure 상태에서 실제 Network Boot 수행 결과:

```text
QSFP+ NIC 초기화 : 성공
Physical Link    : UP
DHCP             : 성공
IP               : 192.168.100.202
Gateway          : 192.168.100.90
PXE Boot 정보    : 미수신
결과             : Nothing to boot
```

C 담당자 확인을 통해 해당 결과는 Kea 자체의 설정 오류가 아니라 **현재 `.60`의 ProxyDHCP가 동작하지 않는 상태에서 PXE Boot 정보가 제공되지 않아 발생한 안전한 Boot Failure**로 확인.

One-Time Network Boot를 이용하여 Disk 및 기존 OS 변경 없이 Boot Failure 상태 재현.

---

## 16. Boot Failure 후 정상 복구 검증

Boot Failure 관측 후 Server #4를 Reset하여 One-Time Network Boot를 해제하고 기존 HDD Boot 수행.

### OS 복귀 확인

```text
Hostname : dca-spare01
OS       : Rocky Linux 9.8
System   : running
```

### QSFP+ NIC 복귀 확인

```text
Interface     : pxe0
IP            : 192.168.100.208/24
Speed         : 40000Mb/s
Duplex        : Full
Link detected : yes
```

### PXE Server 통신 재검증

```text
192.168.100.60
3 packets transmitted
3 received
0% packet loss
```

Boot Failure 재현 이후 정상 HDD Boot 복귀 및 OS / QSFP+ Link / Data Plane / PXE Server 통신 정상 상태 재확인.

---

## 17. Provisioning 자동화 검증 기준 정리

PXE 재설치 이후 Server #4가 실제 Spare / Rebuild Node로 정상 복구되었는지 판단하기 위한 Infrastructure 관점의 Provisioning 검증 기준 정리.

| 검증 항목 | 현재 확인값 / PASS 기준 |
| --- | --- |
| Host | `dca-spare01` |
| QSFP+ Interface | `pxe0` 존재 |
| Driver | `mlx4_en` Load |
| Link | `Link detected: yes` |
| Speed | `40000Mb/s` |
| Duplex | `Full` |
| Data Plane IP | `192.168.100.208/24` |
| PXE Server 통신 | `192.168.100.60` 통신 성공 |
| Remote Access | SSH 접속 가능 |

기존 계획에서 예상했던 QSFP+ Interface `eno49`가 아닌 실제 재설치 환경의 `pxe0`를 기준으로 검증 항목 수정.

향후 Provisioning 자동화 Verify 단계에서 활용할 수 있도록 실제 Server #4 정상 상태 기준값 확보.

OS Version은 현재 Server #4의 Rocky Linux 9.8 상태를 확인하였으나 향후 PXE 정책에 따라 변경될 수 있으므로 영구적인 자동화 PASS 조건으로 확정하지 않은 상태.

**결과: Server #4 Provisioning 이후 Infrastructure Ready 판정을 위한 실제 검증 기준 확보**

---

## 18. Day 6 A 진행 결과

### 완료

- Server #4 Spare / Rebuild Target 상태 검증
- C 담당자의 Rocky Linux 9.8 PXE 재설치 이후 Infrastructure 상태 검증
- 실제 QSFP+ Interface `pxe0` 식별
- `mlx4_en` Driver 정상 Load 확인
- QSFP+ 40Gbps / Full Duplex / Link UP 확인
- Data Plane `192.168.100.208/24` 정상 상태 확인
- PXE Server `192.168.100.60` 통신 확인
- iLO Power / Hardware Health 정상 상태 확인
- Legacy BIOS Boot Mode 및 QSFP+ NIC Boot Order 확인
- F11 One-Time Network Boot 동작 확인
- ZT Storage TFTP / HTTP / Rocky Linux PXE Source 확인
- Server #4 PXE Configuration 및 Kickstart 구성 확인
- OPNsense Kea DHCP 역할 및 Server #4 Lease 확인
- Kea DHCP와 dnsmasq ProxyDHCP 역할 분리 확인
- Server #4 전용 ProxyDHCP 설정 확인
- DHCP Packet Capture 기반 현재 PXE Handoff 중단 구간 확인
- C 담당자의 선행 PXE Provisioning 성공 경로 확인
- PXE 설치 중 `.217` 임시 DHCP 주소 및 설치 후 `.208` 최종 IP 전환 확인
- One-Time Network Boot 기반 안전한 Boot Failure 재현
- 정상 HDD Boot 복귀 후 OS / Network / PXE 통신 재검증
- Provisioning 자동화에 사용할 Infrastructure PASS 기준 정의

### 현재 결론

Server #4를 Spare / Rebuild Target으로 사용하기 위한 iLO·QSFP+·Data Plane·PXE Infrastructure 상태 검증 완료.

Server #4의 실제 Rocky Linux 9.8 PXE Provisioning은 C 담당자가 선행 수행하였으며, 성공 당시 다음 구조 사용 확인.

```text
DHCP (.90)
    ↓
ProxyDHCP (.60)
    ↓
TFTP / PXELINUX (.60)
    ↓
Rocky Linux 9.8
Repository + Kickstart (.60:8080)
    ↓
Server #4 Provisioning
```

OPNsense Kea는 IP / Gateway / DNS 제공 역할을 담당하고 PXE Bootfile 정보는 `.60`의 dnsmasq ProxyDHCP가 별도로 제공하는 구조 확인.

따라서 Kea의 `Next Server / TFTP Server / TFTP Bootfile Name` 미설정 상태는 오류가 아니며, Day 6 현재 재현에서 발생한 `Nothing to boot`는 `.60`의 ProxyDHCP가 현재 동작하지 않는 상태에서 PXE Boot 정보가 전달되지 않아 발생한 것으로 정리.

공용 Infrastructure에 영향을 줄 수 있는 ProxyDHCP 재활성화 및 Kea 설정 변경 없이 현재 상태 검증 완료.

One-Time Network Boot 기반 안전한 Boot Failure 재현 및 기존 Rocky Linux 9.8 정상 HDD Boot 복귀 검증 완료.

C 담당자의 선행 PXE 설치 기록과 A의 재설치 이후 Infrastructure 직접 검증을 결합하여 **Server #4 PXE Provisioning 경로 및 Spare / Rebuild Ready 상태 검증 완료**.

---

## 👤 B — Day 6

- L1 Service Repair부터 L5 PXE Rebuild까지 timeout, 제한 retry, idempotency key와 다음 action 계약을 구현했다.
- Infrastructure adapter가 없는 L3~L5는 실제 장비를 변경하지 않고 `MANUAL_REQUIRED`와 action payload를 반환한다.
- `.208`의 `pxe0`, `mlx4_en`, module, link/speed/duplex, IP/gateway/PXE reachability를 읽기 전용으로 검사하는 Standard Build runner를 추가했다.
- iLO에서 확인한 ED25519 fingerprint와 새 수집 key의 일치를 검증한 뒤 `.208`의 해당 known_hosts 항목만 안전하게 교체했다.
- BatchMode SSH, Ansible ping, become root를 확인하고 PLAN_ONLY `PLANNED`와 승인 profile의 실제 read-only Health Validation `VERIFIED`를 완료했다.
- Rocky OS, `pxe0`, `mlx4_en` modules, link, 40000Mb/s, Full Duplex, `192.168.100.208/24`, gateway `.90`, PXE server `.60` reachability가 모두 PASS였다.

---

# 👤 C — Day 6

> Software Recovery 실패 이후 Escalation 상태를 Backend/DB에 저장하고, React Dashboard에서 Physical Recovery 진행 상태를 자동 Polling하여 실시간 시각화

## 1. Escalation 상태 DB 모델 확장

### Development
- 기존 `Incident` 모델에 Physical Recovery 진행 상태 저장 필드 추가

```text
escalation_level
escalation_status
```

- 기존 SQLite Incident 데이터를 유지한 상태에서 `ALTER TABLE`을 사용해 두 컬럼 추가
- 기존 DB를 `rack.db.day6bak`으로 백업한 뒤 Schema 확장 수행

### 검증
- `PRAGMA table_info(incidents)`로 컬럼 존재 확인
- `backend/models.py` Python compile 정상 확인

### Outcome
- Incident별 Recovery Escalation Level과 진행 상태를 DB에서 지속적으로 관리할 수 있는 기반 확보

---

## 2. Escalation Status API 구현

### Development
- 현재 Incident의 Escalation 상태를 읽는 API 추가

```text
GET /incidents/{incident_id}/escalation
```

- Frontend 또는 Recovery Workflow에서 상태를 기록할 수 있는 API 추가

```text
POST /incidents/{incident_id}/escalation
```

- 지원 Escalation Level

```text
L1 / L2 / L3 / L4 / L5
```

- UI 상태 계약

```text
SOFTWARE_RECOVERY_FAILED
ESCALATION_REQUIRED
SPARE_ACTIVATING
PXE
CONFIGURING
READY
```

- `ESCALATION_REQUIRED` 입력 시 Incident 상태를 `ESCALATED`로 함께 갱신

### 검증
- Incident `INC-20260902-095643-FA80`에서 초기 Escalation 값 `null` 조회 확인
- `L3 / ESCALATION_REQUIRED` POST 후 동일 값을 GET 및 DB에서 조회 가능함을 확인

### Outcome
- B Escalation Engine 및 Physical Recovery 결과를 C Dashboard에서 사용할 수 있는 상태 API 계약 확보

---

## 3. Frontend 2초 자동 Polling 구현

### Development
- `IncidentPanel.jsx`에 `escalation` State 추가
- 현재 Incident가 존재하면 `/escalation` API를 즉시 조회
- 이후 `2,000ms` 간격으로 Backend 상태 자동 Polling
- Incident 변경 시 기존 Polling Timer 정리
- 새로운 Incident 생성 시 이전 Escalation State 초기화

### Outcome
- 사용자가 Refresh 버튼을 누르지 않아도 Backend의 Recovery 진행 상태가 Dashboard에 자동 반영되는 구조 구현

---

## 4. Physical Recovery Progress UI 구현

### Development
- Recovery Escalation 전용 Card 추가
- 다음 6단계를 하나의 Progress UI로 구성

```text
SOFTWARE RECOVERY FAILED
        ↓
ESCALATION REQUIRED
        ↓
SPARE ACTIVATING
        ↓
PXE
        ↓
CONFIGURING
        ↓
READY
```

- 현재 `escalation_level`을 `L3 / L4 / L5` Badge로 표시
- 현재 단계는 Active 상태로 강조
- 이미 통과한 단계는 Complete 상태로 표시
- 아직 진행하지 않은 단계는 Pending 상태로 표시
- 현재 상태를 Card 하단 `Current Status`에 별도로 표시
- 반응형 Layout을 적용해 작은 화면에서도 단계가 깨지지 않도록 구성

### Outcome
- Software Recovery 실패 이후 Spare 투입과 PXE Rebuild 진행 상황을 운영자 및 발표자가 한눈에 확인할 수 있는 Recovery View 확보

---

## 5. Incident History 상태 동기화

### Development
- 기존 Incident History 조회 Effect가 Recovery 결과뿐 아니라 `escalation_status` 변경에도 반응하도록 수정
- Escalation API에서 Incident가 `ESCALATED`로 변경되면 History에도 갱신된 상태가 반영되도록 연결

### Outcome
- 현재 Recovery Progress와 Incident History가 서로 다른 상태를 표시하는 UI 불일치 방지

---

## 6. Escalation Progress 실시간 전환 검증

### Test Incident

```text
INC-20260902-173359-7D66
Target: server-207 / dca-target02
```

### 검증 흐름

먼저 `L3 / ESCALATION_REQUIRED` 상태를 입력한 뒤 브라우저를 새로고침하지 않은 상태에서 약 2초 이내에 Progress Card가 자동 표시되는 것을 확인.

이후 동일 Incident에 다음 상태를 순차 입력하여 실시간 진행 상태 변경 검증.

```text
L3 / ESCALATION_REQUIRED
        ↓
L4 / SPARE_ACTIVATING
        ↓
L5 / PXE
        ↓
L5 / CONFIGURING
        ↓
L5 / READY
```

### 검증 결과

- `ESCALATION REQUIRED` Progress UI 자동 표시 확인
- Escalation Level `L3` Badge 표시 확인
- `SPARE_ACTIVATING` API 저장 성공
- `PXE` API 저장 성공
- `CONFIGURING` API 저장 성공
- `READY` API 저장 성공
- 브라우저 Refresh 없이 Polling 기반 상태 반영 구조 확인
- React Production Build 성공

### Outcome
- Backend 상태 변화가 Frontend Physical Recovery Progress UI까지 이어지는 전체 C 데이터 흐름 검증 완료

```text
DB
 ↓
FastAPI Escalation API
 ↓
2초 Polling
 ↓
React Escalation State
 ↓
Physical Recovery Progress UI
```

---

## 7. 실제 PXE / B Workflow 연계 상태

C의 Escalation DB/API, Polling 및 Progress UI는 구현·검증 완료.

다만 Day 6 검증에서 `SPARE_ACTIVATING → PXE → CONFIGURING → READY` 상태는 C Escalation API에 테스트 상태를 순차 입력하여 UI 흐름을 검증한 것이다.

B의 현재 Escalation Engine은 L1~L5 상태 계약을 구현했지만 Infrastructure adapter가 연결되지 않은 L3~L5에서는 실제 장비 변경 대신 `MANUAL_REQUIRED`를 반환하도록 구성되어 있다.

따라서 다음 두 항목을 구분한다.

```text
C Escalation 상태 저장 / API / Polling / Progress UI      : 완료
B L3~L5 → 실제 Physical Infrastructure 자동 상태 연동    : 통합 단계에서 추가 검증 필요
```

Server #4의 실제 Rocky Linux 9.8 PXE Provisioning 자체는 선행 작업에서 성공한 이력이 있으며, Day 6 C에서는 해당 물리 설치를 다시 수행한 것이 아니라 **Backend 상태를 UI에 실시간 반영하는 Platform / Visualization 경로를 구현**했다.

---

## Day 6 C 최종 결과

- Incident `escalation_level`, `escalation_status` DB 필드 구현
- 기존 SQLite 데이터 유지 상태에서 Schema 확장 완료
- Escalation 상태 GET / POST API 구현
- `ESCALATION_REQUIRED` 시 Incident `ESCALATED` 상태 연동
- React 2초 자동 Polling 구현
- Physical Recovery Progress UI 구현
- `SOFTWARE RECOVERY FAILED → ESCALATION REQUIRED → SPARE ACTIVATING → PXE → CONFIGURING → READY` 단계 시각화
- Incident History와 Escalation 상태 동기화
- 실제 API를 통한 `L3 → L4 → L5` 상태 전환 저장 검증
- 브라우저 Refresh 없는 실시간 Progress UI 반영 검증
- React Production Build 성공
- 실제 B L3~L5 Infrastructure adapter 미연결 상태는 통합 검증 항목으로 명확히 분리
- **Day 6 C — Recovery Escalation 상태 관리·API·자동 Polling·Physical Recovery Progress UI 구현 완료**
