# 📅 Day 6 — 2026-08-30

Day 6 팀별 작업 기록

---

## 📊 Team Progress

| Role | 담당 | Day 6 작업 |
|---|---|---|
| **A** | Hardware / Infrastructure | Server #4 Spare/PXE 인프라 검증 및 One-Time Network Boot 기반 Boot Failure·복구, DHCP/PXE Handoff 구간 검증 |
| **B** | Automation / Troubleshooting | 작성 예정 |
| **C** | Platform / Visualization | 작성 예정 |

---

# 👤 A — Day 6

> 작성 예정

## 1. Server #4 Spare / Rebuild Target 상태 검증

Server #4를 Spare / Rebuild Target으로 사용하기 위한 현재 시스템 상태 확인

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

Server #4의 OS 및 Data Plane Network 정상 상태 확인을 통한 Spare / Rebuild Target 기반 상태 확보


## 2. PXE 재설치 후 QSFP+ NIC 상태 검증

Server #4에 선행 수행된 Rocky Linux 9.8 PXE 재설치 이후 Infrastructure 관점의 QSFP+ NIC 상태 직접 검증

기존 계획에서는 QSFP+ Interface를 `eno49`로 예상했으나 실제 재설치된 OS에서는 `pxe0`로 인식됨을 확인

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

PXE 재설치 후 QSFP+ NIC가 `pxe0`로 정상 인식되고 Data Plane Network까지 정상 복구된 상태 검증


## 3. Server #4 iLO / Hardware 상태 검증

Server #4의 물리 Hardware 및 Remote Management 상태 확인을 위해 iLO 접속 후 System 상태 검증

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

Boot Failure Scenario 수행 전 Server #4 Hardware 정상 상태 확보


## 4. Legacy BIOS Boot Mode 및 Boot Order 확인

Server #4의 PXE Boot 가능 여부 확인을 위해 iLO Remote Console에서 BIOS Boot 설정 확인

### Boot Mode

```text
Boot Mode           : Legacy BIOS Mode
UEFI Optimized Boot : Disabled
Boot Order Policy   : Retry Boot Order Indefinitely
```

### Legacy BIOS Boot Order

QSFP+ NIC가 Legacy BIOS Boot Order의 우선 Boot Device로 등록되어 있음을 확인

```text
Embedded FlexibleLOM 1 Port 1
HPE InfiniBand FDR/Ethernet
10Gb/40Gb 2-port 544+FLR-QSFP Adapter
```

Server #4의 QSFP+ NIC 기반 Network Boot 가능 구성 확인


## 5. One-Time Network Boot 동작 검증

정상 OS Boot Order를 영구 변경하지 않고 PXE Boot 경로를 검증하기 위해 F11 Legacy BIOS One-Time Boot Menu 사용

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

`One Time Boot to Network` 선택 후 QSFP+ NIC를 통한 실제 Network Boot 동작 확인

### PXE NIC 초기화 결과

```text
NIC       : ConnectX-3Pro
MAC       : 70:10:6f:a1:aa:41
PCI       : 04:00.0
Link      : UP
DHCP      : 성공
```

QSFP+ NIC 초기화 → Physical Link UP → DHCP 요청 단계까지 정상 진행 확인


## 6. ZT Storage PXE Server 상태 검증

PXE Server `192.168.100.60`에 직접 접속하여 Server #4 PXE Boot에 필요한 TFTP 및 HTTP 서비스 상태 확인

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

PXE Boot에 필요한 Bootloader 및 Rocky Linux Kernel / initrd 파일 존재 확인


## 7. Server #4 PXE Boot Configuration 확인

`/srv/tftp/pxelinux.cfg/default` 확인을 통한 Server #4 PXE Boot 설정 검증

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

PXE Configuration의 MAC Address와 Server #4 QSFP+ NIC 실제 MAC Address 일치 확인


## 8. Rocky Linux 9 HTTP 설치 Source 검증

PXE 설치 과정에서 Kernel Boot 이후 사용하는 Rocky Linux 설치 Repository 및 Kickstart File 제공 상태 확인

### HTTP Service

```text
192.168.100.60:8080
```

HTTP 8080 Port 정상 Listening 상태 확인

### Rocky Linux Repository

```text
http://192.168.100.60:8080/rocky9-repo/
```

HTTP `200 OK` 응답 확인

### Server #4 Kickstart

```text
http://192.168.100.60:8080/ks/server4.ks
```

HTTP `200 OK` 응답 확인

PXE Boot 이후 Rocky Linux 설치에 필요한 HTTP Repository 및 Kickstart File 접근 가능 상태 확인


## 9. Server #4 Kickstart 구성 검증

실제 Server #4 설치에 사용되는 Kickstart File 확인

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

Kickstart File을 통한 Server #4 무인 Rocky Linux 재설치 구성 확인


## 10. OPNsense Kea DHCP 및 Server #4 Lease 검증

PXE Boot 과정에서 Server #4의 DHCP 요청을 처리하는 장비 확인

OPNsense Data Plane Interface `192.168.100.90`에서 Kea DHCP Service 동작 확인

### DHCP Subnet

```text
Subnet : 192.168.100.0/24
Pool   : 192.168.100.201 - 192.168.100.224
```

### Server #4 DHCP Lease

```text
IP  : 192.168.100.202
MAC : 70:10:6f:a1:aa:41
```

Kea Lease 기록과 실제 PXE Boot 화면에서 획득한 IP / MAC Address 일치 확인

Server #4 QSFP+ NIC → OPNsense Kea DHCP 요청 및 Lease 할당 경로 정상 확인


## 11. 현재 DHCP / PXE Handoff 설정 상태 확인

현재 OPNsense Kea DHCP Configuration에서 PXE Boot 관련 정보 확인

공용 `192.168.100.0/24` Subnet의 현재 설정 확인 결과

```text
Next Server        : 미설정
TFTP Server        : 미설정
TFTP Bootfile Name : 미설정
Reservations       : 0
Options            : 0
```

Active Kea Configuration에서도 `next-server` 값이 비어 있으며 PXE Server `192.168.100.60`, `pxelinux`, Bootfile 관련 추가 설정이 확인되지 않는 상태 확인

해당 DHCP Infrastructure는 다른 팀에서도 사용하는 공용 환경이므로 PXE Server 및 Bootfile 관련 설정에 대한 임의 변경 미수행

현재 설정 상태만으로 OPNsense Kea의 설정 오류로 단정하지 않고 실제 DHCP Packet을 통한 PXE Handoff 상태 추가 검증 진행


## 12. DHCP Packet Capture 기반 PXE Handoff 구간 검증

Server #4의 실제 One-Time Network Boot 수행과 동시에 OPNsense Data Plane Interface에서 DHCP Packet Capture 수행

```bash
tcpdump -ni vlan0.100 -vvv -s0 port 67 or port 68
```

### DHCPDISCOVER

Server #4 PXE Client 확인

```text
MAC          : 70:10:6f:a1:aa:41
Vendor-Class : PXEClient:Arch:00000:UNDI:002001
Architecture : 0
```

PXE Client가 DHCP Parameter Request 과정에서 TFTP Server 및 Bootfile 정보를 요청함을 확인

```text
Option 66 : TFTP Server
Option 67 : Bootfile
```

### DHCPOFFER

OPNsense Kea DHCP에서 Server #4에 대한 IP Lease Offer 확인

```text
Your IP         : 192.168.100.202
Subnet          : 192.168.100.0/24
Default Gateway : 192.168.100.90
DHCP Server     : 192.168.100.90
```

### DHCPACK

Server #4의 DHCPREQUEST 이후 동일한 `192.168.100.202` 주소에 대한 DHCPACK 정상 확인

DHCPACK를 통해 다음 Network 정보 전달 확인

```text
IP              : 192.168.100.202
Subnet          : 192.168.100.0/24
Default Gateway : 192.168.100.90
DHCP Server     : 192.168.100.90
DNS             : 192.168.100.90
```

반면 현재 DHCPOFFER 및 DHCPACK에는 PXE Boot에 필요한 다음 정보가 포함되지 않음을 확인

```text
TFTP Server / Option 66 : 없음
Bootfile / Option 67    : 없음
```

### 현재 PXE Boot 흐름

```text
Server #4 QSFP+ NIC
        ↓
Physical Link UP
        ↓
DHCPDISCOVER
        ↓
OPNsense Kea DHCP
        ↓
192.168.100.202 Lease 할당
        ↓
PXE Boot Server / Bootfile 정보 미전달
        ↓
Boot File 획득 단계 진행 불가
        ↓
Nothing to boot
```

QSFP+ NIC 및 DHCP 통신 자체는 정상이나 현재 DHCP 응답에서 PXE Boot Server / Bootfile 정보가 전달되지 않아 Boot File 획득 단계로 진행되지 않는 상태 확인

공용 DHCP Infrastructure임을 고려하여 Kea PXE 설정에 대한 임의 변경 없이 Packet Level Evidence 확보


## 13. 안전한 Boot Failure Scenario 검증

Disk, Partition, GRUB 및 기존 Rocky Linux OS를 손상시키지 않고 실제 Boot Failure를 재현하기 위해 One-Time Network Boot 방식 사용

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

Server Reboot 후 F11 Legacy BIOS One-Time Boot Menu 진입

```text
One Time Boot to Network
```

선택 후 실제 QSFP+ NIC Network Boot 수행

```text
QSFP+ NIC 초기화 : 성공
Physical Link    : UP
DHCP             : 성공
IP               : 192.168.100.202
Gateway          : 192.168.100.90
Boot File 획득   : 실패
결과             : Nothing to boot
```

One-Time Network Boot를 이용하여 Disk 및 기존 OS 변경 없이 실제 Boot Failure 상태 재현


## 14. Boot Failure 후 정상 복구 검증

Boot Failure 관측 후 Server #4를 Reset하여 One-Time Network Boot를 해제하고 기존 HDD Boot 수행

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

Boot Failure 재현 이후 정상 HDD Boot 복귀 및 OS / QSFP+ Link / Data Plane / PXE Server 통신 정상 상태 재확인


## 15. Provisioning 자동화 검증 기준 정리

PXE 재설치 이후 Server #4가 실제 Spare / Rebuild Node로 정상 복구되었는지 판단하기 위한 Infrastructure 관점의 Provisioning 검증 기준 정리

Server #4의 현재 Rocky Linux 9.8 환경에서 직접 확인한 값을 기준으로 다음 항목 확보

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

기존 계획에서 예상했던 QSFP+ Interface `eno49`가 아닌 실제 재설치 환경의 `pxe0`를 기준으로 검증 항목 수정

향후 Provisioning 자동화의 Verify 단계에서 활용할 수 있도록 실제 Server #4 정상 상태 기준값 확보

### 현재 상태

Infrastructure 측 PASS 기준 정의 및 실제 값 검증 완료

B 담당 Provisioning 자동화에 해당 기준을 전달하고 자동 Verify 항목과 연계하는 작업은 현재 미완료 상태

OS Version은 현재 Server #4의 Rocky Linux 9.8 상태를 확인하였으나 향후 PXE 정책에 따라 변경될 수 있으므로 영구적인 자동화 PASS 조건으로 확정하지 않은 상태


## 16. PXE Boot Handoff 추가 확인 사항

현재 Server #4 PXE Boot 재현에서는 다음 단계까지 직접 검증 완료

```text
QSFP+ NIC 초기화        : 정상
Physical Link           : UP
DHCP 통신               : 정상
DHCP Lease              : 192.168.100.202
PXE Boot 정보 전달      : 현재 응답에서 미확인
Boot File 획득          : 진행 불가
결과                    : Nothing to boot
```

PXE Server `192.168.100.60`에서는 다음 구성 정상 확인

```text
TFTP :69
pxelinux.0
pxelinux.cfg/default
rocky9/vmlinuz
rocky9/initrd.img
HTTP :8080
rocky9-repo
server4.ks
```

따라서 PXE Server 자체의 주요 설치 Source 존재 여부와 Server #4의 QSFP+ / DHCP 경로까지 검증된 상태이며, 현재 재현에서는 DHCP 이후 PXE Boot File Handoff 단계에서 진행이 중단되는 상태 확인

### 추가 확인 필요 사항

Server #4의 Rocky Linux 9.8 PXE 재설치가 선행 작업에서 성공한 이력이 있으므로 당시 PXE Boot Handoff 구성 방식에 대한 C 담당자 확인 진행

확인 예정 항목

- PXE 설치 당시 OPNsense Kea DHCP 설정 변경 여부
- `Next Server` 설정 여부
- TFTP Server 설정 여부
- TFTP Bootfile 설정 여부
- 임시 설정을 사용한 경우 설치 완료 후 원복 여부
- Kea DHCP 외 별도 방식으로 PXE Boot 정보를 전달했는지 여부

현재 DHCP Infrastructure는 다른 팀에서도 사용하는 공용 환경이므로 확인되지 않은 PXE 관련 값을 임의로 추가하여 재현하지 않은 상태

현재 단계에서는 OPNsense 설정 오류로 단정하지 않고 **현재 DHCP 응답에서 PXE Boot File Handoff 정보가 확인되지 않는 상태**까지만 Infrastructure 검증 결과로 확정

C 담당자의 설정 이력 확인 후 성공 당시 PXE Boot 구성과 현재 상태를 비교하여 Day 6 기록 추가 보완 예정


## 17. Day 6 A 진행 결과

### 완료

- Server #4 Spare / Rebuild Target 상태 검증
- Rocky Linux 9.8 재설치 이후 Infrastructure 상태 검증
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
- OPNsense Kea DHCP Server 및 Server #4 Lease 확인
- DHCP Packet Capture 기반 현재 PXE Boot Handoff 중단 구간 확인
- One-Time Network Boot 기반 안전한 Boot Failure 재현
- 정상 HDD Boot 복귀 후 OS / Network / PXE 통신 재검증
- Provisioning 자동화에 사용할 Infrastructure PASS 기준 정의

### 추가 진행 필요

- B 담당자에게 Server #4 Provisioning PASS 기준 전달 및 자동 Verify 항목 연계 확인
- C 담당자에게 선행 PXE 재설치 성공 당시 DHCP / PXE Boot Handoff 구성 확인
- C 담당자 확인 결과와 현재 DHCP Packet Capture 결과 비교
- 확인 결과에 따른 Day 6 PXE Recovery 기록 최종 보완

### 현재 결론

Server #4를 Spare / Rebuild Target으로 사용하기 위한 iLO·QSFP+·Data Plane·PXE Infrastructure 상태 검증 완료

One-Time Network Boot를 이용한 안전한 Boot Failure 재현 및 기존 Rocky Linux 정상 Boot 복귀 검증 완료

현재 PXE Boot 재현에서는 QSFP+ Link 및 DHCP Lease 할당까지 정상 동작하며, DHCP 이후 PXE Boot File Handoff 정보가 전달되지 않는 구간까지 Packet Level Evidence 확보

공용 DHCP Infrastructure에 영향을 줄 수 있는 설정 변경은 수행하지 않고 현재 상태의 원인 구간까지만 검증

Provisioning PASS 기준의 B 담당자 전달 및 선행 PXE 성공 당시 DHCP/PXE 구성에 대한 C 담당자 확인 이후 Day 6 최종 보완 예정

---

## 👤 B — Day 6

> 작성 예정

---

# 👤 C — Day 6

> 작성 예정
