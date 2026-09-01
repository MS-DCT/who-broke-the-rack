#!/usr/bin/env python3
"""Plan or run the allowlisted Server #4 standard-build validation."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "automation/ansible/inventory.ini"
PLAYBOOK = ROOT / "automation/ansible/playbooks/standard_build.yml"
PROFILE = {
    "host": "dca-spare01",
    "interface": "pxe0",
    "driver": "mlx4_en",
    "modules": ["mlx4_core", "mlx4_en"],
    "speed_mbps": 40000,
    "duplex": "Full",
    "ip_address": "192.168.100.208/24",
    "gateway": "192.168.100.90",
    "pxe_server": "192.168.100.60",
    "required_services": ["sshd.service"],
}
CHECKS = ("ssh_access", "os_release", "interface", "driver", "modules", "link", "speed", "duplex", "ip_address", "gateway", "pxe_reachability", "required_services")


class StandardBuildError(RuntimeError):
    pass


def evaluate_standard_build(checks: dict[str, Any]) -> dict[str, Any]:
    normalized = {name: str(checks.get(name, "UNKNOWN")).upper() for name in CHECKS}
    normalized["overall_status"] = "PASS" if all(value == "PASS" for value in normalized.values()) else "FAIL"
    return normalized


def run_standard_build(host: str = "dca-spare01", *, execute: bool = False, approved_profile: str | None = None) -> dict[str, Any]:
    if host != PROFILE["host"]:
        raise StandardBuildError("Standard Build is restricted to dca-spare01")
    if not execute:
        return {"host": host, "mode": "PLAN_ONLY", "status": "PLANNED", "profile": PROFILE, "validation": evaluate_standard_build({})}
    if approved_profile != "dca_spare01_validation":
        raise StandardBuildError("Execute requires approved_profile=dca_spare01_validation")
    with tempfile.TemporaryDirectory(prefix="standard-build-") as directory:
        command = ["ansible-playbook", "-i", str(INVENTORY), str(PLAYBOOK), "--limit", host, "--extra-vars", json.dumps({"standard_build_output_dir": directory, "standard_build_profile": PROFILE})]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise StandardBuildError(completed.stderr.strip() or completed.stdout.strip() or "standard build failed")
        try:
            checks = json.loads((Path(directory) / f"{host}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StandardBuildError(f"Invalid standard build result: {error}") from error
    validation = evaluate_standard_build(checks)
    return {"host": host, "mode": "EXECUTE", "status": "VERIFIED" if validation["overall_status"] == "PASS" else "ESCALATION_REQUIRED", "profile": PROFILE, "validation": validation}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="dca-spare01")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approved-profile")
    args = parser.parse_args()
    try:
        result = run_standard_build(args.host, execute=args.execute, approved_profile=args.approved_profile)
    except StandardBuildError as error:
        print(f"standard_build_runner: {error}")
        return 1
    print(json.dumps(result, indent=2))
    return 2 if result["status"] == "ESCALATION_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
