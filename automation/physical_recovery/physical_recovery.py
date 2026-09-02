#!/usr/bin/env python3
"""Validate a spare server for physical recovery without changing target state."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TARGET_EVIDENCE = (
    REPOSITORY_ROOT
    / "evidence"
    / "day7"
    / "hardware"
    / "DAY7-NODE-01-target.json"
)

DEFAULT_SPARE_EVIDENCE = (
    REPOSITORY_ROOT
    / "evidence"
    / "day7"
    / "hardware"
    / "DAY7-PHYSICAL-RECOVERY-01-spare.json"
)

DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "evidence"
    / "day7"
    / "physical_recovery"
    / "DAY7-PHYSICAL-RECOVERY-01.json"
)

TARGET_SERVER_ID = "server-207"
TARGET_HOST = "dca-target02"

SPARE_SERVER_ID = "server-208"
SPARE_HOST = "dca-spare01"
SPARE_IP = "192.168.100.208"
SPARE_INTERFACE = "pxe0"
PXE_SERVER_IP = "192.168.100.60"


class PhysicalRecoveryError(RuntimeError):
    """Expected physical recovery validation error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_evidence(
    result: str,
    value: Any,
    detail: str,
    source: str,
) -> dict[str, Any]:
    return {
        "result": result,
        "value": value,
        "detail": detail,
        "source": source,
    }


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PhysicalRecoveryError(
            f"Could not load evidence {path}: {error}"
        ) from error

    if not isinstance(data, dict):
        raise PhysicalRecoveryError(
            f"Evidence {path} must contain a JSON object"
        )

    return data


def validate_document(
    document: dict[str, Any],
    *,
    expected_server_id: str,
    expected_host: str,
    label: str,
) -> None:
    if document.get("server_id") != expected_server_id:
        raise PhysicalRecoveryError(
            f"{label} server_id mismatch: "
            f"{document.get('server_id')!r}"
        )

    if document.get("host") != expected_host:
        raise PhysicalRecoveryError(
            f"{label} host mismatch: "
            f"{document.get('host')!r}"
        )

    if not isinstance(document.get("evidence"), dict):
        raise PhysicalRecoveryError(
            f"{label} evidence must be an object"
        )


def check_target_failure(
    target_document: dict[str, Any],
) -> dict[str, Any]:
    evidence = target_document["evidence"]

    power = evidence.get("power_state", {})
    post = evidence.get("post_state", {})

    power_result = str(
        power.get("result") or "UNKNOWN"
    ).upper()
    power_value = str(
        power.get("value") or ""
    ).upper()

    post_result = str(
        post.get("result") or "UNKNOWN"
    ).upper()
    post_value = str(
        post.get("value") or ""
    ).upper()

    power_off = (
        power_result in {"WARN", "FAIL"}
        and power_value == "OFF"
    )

    post_blocked = (
        post_result in {"SKIP", "WARN", "FAIL"}
        and post_value in {"POWEROFF", "POWER_OFF", "OFF"}
    )

    if power_off and post_blocked:
        return make_evidence(
            "PASS",
            "NODE_FAILURE_CONFIRMED",
            (
                f"{TARGET_SERVER_ID} PowerState=Off and "
                "POST unavailable due to PowerOff"
            ),
            str(target_document.get("source") or "redfish"),
        )

    return make_evidence(
        "UNKNOWN",
        "NOT_CONFIRMED",
        (
            "Stored target evidence does not explicitly confirm "
            "the expected PowerOff node failure"
        ),
        str(target_document.get("source") or "redfish"),
    )


def check_spare_hardware(
    spare_document: dict[str, Any],
) -> dict[str, Any]:
    evidence = spare_document["evidence"]

    required_checks = [
        "ilo_reachability",
        "power_state",
        "system_health",
        "post_state",
        "memory_health",
        "storage_health",
    ]

    device_checks = sorted(
        name
        for name in evidence
        if (
            name.startswith("controller_")
            or name.startswith("logical_drive_")
            or name.startswith("physical_drive_")
        )
        and name.endswith("_health")
    )

    checks = [*required_checks, *device_checks]

    missing = [
        name
        for name in required_checks
        if name not in evidence
    ]

    failed = [
        name
        for name in checks
        if name in evidence
        and str(
            evidence[name].get("result") or "UNKNOWN"
        ).upper() != "PASS"
    ]

    if not missing and not failed:
        return make_evidence(
            "PASS",
            "READY",
            (
                "iLO, Power, System, POST, Memory, Storage and "
                f"{len(device_checks)} device-level hardware checks PASS"
            ),
            str(spare_document.get("source") or "redfish"),
        )

    detail_parts = []

    if missing:
        detail_parts.append(
            "missing=" + ",".join(missing)
        )

    if failed:
        detail_parts.append(
            "not_pass=" + ",".join(failed)
        )

    return make_evidence(
        "UNKNOWN",
        "NOT_READY",
        "; ".join(detail_parts) or "Hardware readiness not confirmed",
        str(spare_document.get("source") or "redfish"),
    )


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PhysicalRecoveryError(
            f"Could not run command {command!r}: {error}"
        ) from error


def check_spare_reachability() -> dict[str, Any]:
    completed = run_command(
        ["ping", "-c", "3", "-W", "1", SPARE_IP]
    )

    if completed.returncode == 0:
        return make_evidence(
            "PASS",
            "REACHABLE",
            f"{SPARE_IP} responded to ICMP probe",
            "icmp_probe",
        )

    return make_evidence(
        "FAIL",
        "UNREACHABLE",
        f"{SPARE_IP} did not respond to ICMP probe",
        "icmp_probe",
    )


def check_spare_os() -> dict[str, Any]:
    remote_command = (
        'printf "HOST=%s\\n" "$(hostname)"; '
        'printf "SYSTEM=%s\\n" "$(systemctl is-system-running)"'
    )

    completed = run_command(
        [
            "ssh",
            "-o",
            "ConnectTimeout=5",
            f"rocky@{SPARE_IP}",
            remote_command,
        ]
    )

    output = completed.stdout.strip()

    expected_host = f"HOST={SPARE_HOST}"
    expected_system = "SYSTEM=running"

    if (
        completed.returncode == 0
        and expected_host in output
        and expected_system in output
    ):
        return make_evidence(
            "PASS",
            "RUNNING",
            f"{SPARE_HOST} SSH reachable and systemd state=running",
            "ssh_systemd_probe",
        )

    detail = (
        output
        or completed.stderr.strip()
        or "SSH/OS readiness probe failed"
    )

    return make_evidence(
        "FAIL",
        "NOT_READY",
        detail,
        "ssh_systemd_probe",
    )


def check_spare_interface() -> dict[str, Any]:
    remote_command = (
        f"ip -br addr show {SPARE_INTERFACE}; "
        f"ethtool {SPARE_INTERFACE} 2>/dev/null "
        "| grep -E 'Speed:|Duplex:|Link detected:'"
    )

    completed = run_command(
        [
            "ssh",
            "-o",
            "ConnectTimeout=5",
            f"rocky@{SPARE_IP}",
            remote_command,
        ]
    )

    output = completed.stdout.strip()

    interface_up = (
        SPARE_INTERFACE in output
        and "UP" in output
        and SPARE_IP in output
    )
    speed_ok = "Speed: 40000Mb/s" in output
    duplex_ok = "Duplex: Full" in output
    link_ok = "Link detected: yes" in output

    if (
        completed.returncode == 0
        and interface_up
        and speed_ok
        and duplex_ok
        and link_ok
    ):
        return make_evidence(
            "PASS",
            "UP",
            (
                f"{SPARE_INTERFACE} {SPARE_IP}/24, "
                "40000Mb/s Full Duplex, Link detected=yes"
            ),
            "os_network_probe",
        )

    return make_evidence(
        "FAIL",
        "NOT_READY",
        output or "Spare interface readiness probe failed",
        "os_network_probe",
    )


def check_pxe_reachability() -> dict[str, Any]:
    completed = run_command(
        [
            "ssh",
            "-o",
            "ConnectTimeout=5",
            f"rocky@{SPARE_IP}",
            f"ping -c 3 -W 1 {PXE_SERVER_IP}",
        ]
    )

    if completed.returncode == 0:
        return make_evidence(
            "PASS",
            "REACHABLE",
            (
                f"{SPARE_HOST} can reach PXE server "
                f"{PXE_SERVER_IP}"
            ),
            "icmp_probe_from_spare",
        )

    return make_evidence(
        "FAIL",
        "UNREACHABLE",
        (
            completed.stderr.strip()
            or completed.stdout.strip()
            or f"PXE server {PXE_SERVER_IP} unreachable"
        ),
        "icmp_probe_from_spare",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--incident-id",
        default="DAY7-PHYSICAL-RECOVERY-01",
    )
    parser.add_argument(
        "--target-evidence",
        type=Path,
        default=DEFAULT_TARGET_EVIDENCE,
    )
    parser.add_argument(
        "--spare-evidence",
        type=Path,
        default=DEFAULT_SPARE_EVIDENCE,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        target_document = load_json(args.target_evidence)
        spare_document = load_json(args.spare_evidence)

        validate_document(
            target_document,
            expected_server_id=TARGET_SERVER_ID,
            expected_host=TARGET_HOST,
            label="Target",
        )

        validate_document(
            spare_document,
            expected_server_id=SPARE_SERVER_ID,
            expected_host=SPARE_HOST,
            label="Spare",
        )

        evidence = {
            "target_node_failure": check_target_failure(
                target_document
            ),
            "spare_hardware_ready": check_spare_hardware(
                spare_document
            ),
            "spare_reachability": check_spare_reachability(),
            "spare_network_ready": check_spare_interface(),
            "spare_os_ready": check_spare_os(),
            "pxe_server_reachability": check_pxe_reachability(),
            "pxe_provisioning_ready": make_evidence(
                "UNKNOWN",
                "PENDING",
                (
                    "PXE server reachability is checked separately; "
                    "full PXE boot and unattended reinstall E2E "
                    "verification is still pending"
                ),
                "day6_pxe_validation",
            ),
        }

        required = [
            "target_node_failure",
            "spare_hardware_ready",
            "spare_reachability",
            "spare_network_ready",
            "spare_os_ready",
            "pxe_server_reachability",
        ]

        ready = all(
            evidence[name]["result"] == "PASS"
            for name in required
        )

        evidence["physical_recovery_ready"] = make_evidence(
            "PASS" if ready else "FAIL",
            "READY" if ready else "NOT_READY",
            (
                "Target node failure confirmed and Spare #4 "
                "Hardware/Network/OS/PXE-server reachability verified"
                if ready
                else "One or more required physical recovery checks failed"
            ),
            "physical_recovery",
        )

        output = {
            "incident_id": args.incident_id,
            "server_id": SPARE_SERVER_ID,
            "host": SPARE_HOST,
            "timestamp": utc_now(),
            "category": "physical_recovery",
            "source": "physical_recovery",
            "evidence": evidence,
        }

        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.output.write_text(
            json.dumps(
                output,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        print("===== Physical Recovery Validation =====")
        print(f"Incident : {args.incident_id}")
        print(
            f"Target   : {TARGET_SERVER_ID} / {TARGET_HOST}"
        )
        print(
            f"Spare    : {SPARE_SERVER_ID} / {SPARE_HOST}"
        )
        print()

        for name, item in evidence.items():
            print(
                f"{name:28} "
                f"{item['result']:7} "
                f"{item['value']}"
            )

        print()
        print(
            "PHYSICAL_RECOVERY="
            + ("READY" if ready else "NOT_READY")
        )
        print(f"JSON saved to: {args.output}")

        return 0 if ready else 2

    except PhysicalRecoveryError as error:
        print(
            f"physical_recovery: {error}",
            file=__import__("sys").stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
