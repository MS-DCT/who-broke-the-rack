#!/usr/bin/env bash
set -u

IFACE="${1:-eno49}"
SVI="${2:-192.168.100.200}"
PXE="${3:-192.168.100.60}"

echo "===== DC:SURVIVE Role B - QSFP+/Data Plane diagnostics ====="
date
echo

echo "[1] OS / Kernel"
cat /etc/os-release | head
uname -r
echo

echo "[2] Mellanox PCI device"
lspci -nn | grep -i -E 'mellanox|ethernet' || true
echo

echo "[3] mlx4 modules"
lsmod | grep -E '^mlx4_(core|en)' || true
echo

echo "[4] Interface"
ip -br link show "$IFACE" || true
ip -br addr show "$IFACE" || true
echo

echo "[5] Driver"
ethtool -i "$IFACE" || true
echo

echo "[6] Physical Link"
ethtool "$IFACE" | grep -E 'Speed:|Duplex:|Link detected:' || true
echo

echo "[7] Route to Cisco SVI"
ip route get "$SVI" || true
echo

echo "[8] Cisco SVI ping"
ping -c 4 -W 1 "$SVI" || true
echo

echo "[9] PXE Server ping"
ping -c 4 -W 1 "$PXE" || true
echo

echo "[10] PXE ARP/Neighbor"
ip neigh show "$PXE" || true
echo

echo "===== END ====="
