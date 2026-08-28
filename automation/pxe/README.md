# PXE Bare-Metal Provisioning

This directory contains the PXE provisioning configuration used by **WHO BROKE THE RACK** to rebuild physical Server #4.

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

## PXE Server

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

Example `/etc/default/tftpd-hpa`:

```ini
TFTP_USERNAME="tftp"
TFTP_DIRECTORY="/srv/tftp"
TFTP_ADDRESS=":69"
TFTP_OPTIONS="--secure"
```

Verify:

```bash
sudo systemctl status tftpd-hpa
sudo ss -lunp | grep ':69 '
```

## proxyDHCP

The existing DHCP server at `192.168.100.90` continues to provide IP address, subnet mask, gateway, and DNS.

The PXE server at `192.168.100.60` provides only PXE boot information through dnsmasq proxyDHCP:

```text
Next Server : 192.168.100.60
Boot File   : pxelinux.0
```

The configuration is restricted to Server #4 using its Mellanox NIC MAC:

```text
70:10:6f:a1:aa:41
```

## PXELINUX

Server #4 uses Legacy BIOS PXE. PXELINUX loads:

```text
rocky9/vmlinuz
rocky9/initrd.img
```

The Mellanox NIC is explicitly mapped as `pxe0` using:

```text
ifname=pxe0:70:10:6f:a1:aa:41
ip=:::::pxe0:dhcp
bootdev=pxe0
```

Kickstart:

```text
inst.ks=http://192.168.100.60:8080/ks/server4.ks
```

Installation repository:

```text
inst.stage2=http://192.168.100.60:8080/rocky9-repo/
```

## Local Rocky Linux Repository

Rocky Linux 9.8 Minimal ISO is mounted on the PXE server.

```bash
sudo mkdir -p /srv/rocky-http/rocky9-repo
sudo mount -o loop,ro /srv/rocky-http/Rocky-9.8-x86_64-minimal.iso /srv/rocky-http/rocky9-repo
```

Start HTTP server:

```bash
nohup python3 -m http.server 8080 --bind 192.168.100.60 --directory /srv/rocky-http >/tmp/rocky-http.log 2>&1 &
```

Repository URL:

```text
http://192.168.100.60:8080/rocky9-repo/
```

Validation:

```bash
curl -I http://192.168.100.60:8080/rocky9-repo/.treeinfo
curl -I http://192.168.100.60:8080/rocky9-repo/Minimal/repodata/repomd.xml
```

Expected:

```text
HTTP/1.0 200 OK
```

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
Automatic reboot after installation
```

> WARNING: `clearpart --all --drives=sda` removes all existing partitions from Server #4 `/dev/sda`. Only run provisioning after confirming that Server #4 is the intended Spare / Rebuild Target.

## Password Handling

Do not commit a real password or password hash. The repository version of the Kickstart file uses:

```text
<REPLACE_WITH_SHA512_PASSWORD_HASH>
```

Generate the deployment hash only on the PXE server:

```bash
openssl passwd -6
```

Do not commit real passwords, password hashes, SSH private keys, iLO credentials, or administrator credentials.

## Rocky Linux 10 Compatibility Finding

Rocky Linux 10 was initially tested. The PXE firmware successfully downloaded `pxelinux.0`, `vmlinuz`, and `initrd.img`, but networking failed after the installer kernel took control of the Mellanox ConnectX-3 Pro NIC in this environment.

Rocky Linux 9.8 was then tested and the `mlx4_core` and `mlx4_en` drivers loaded successfully, so Rocky Linux 9.8 was selected as the provisioning OS for Server #4.

## Provisioning Result

The unattended installation completed successfully. Initial DHCP address after installation:

```text
192.168.100.217
```

SSH validation:

```bash
ssh rocky@192.168.100.217
```

After provisioning, Server #4 was changed to the final project Data IP:

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

## Final Validation

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
