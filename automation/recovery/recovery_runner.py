#!/usr/bin/env python3
"""Plan or execute the approved NET-ROUTE-01 recovery workflow."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from automation.diagnosis.incident_runner import IncidentRunnerError, run_incident


HERE = Path(__file__).resolve().parent
AUTOMATION_DIR = HERE.parent
DEFAULT_INVENTORY = AUTOMATION_DIR / "ansible" / "inventory.ini"
DEFAULT_PLAYBOOK = AUTOMATION_DIR / "ansible" / "playbooks" / "incident_network_recovery.yml"
ALLOWED_RULE = "NET-ROUTE-01"
ALLOWED_ACTION = "network_recovery"
DAY3_RECOMMENDED_ACTION = (
    "Verify the gateway and required destination routes, then correct the routing configuration."
)
ALLOWED_RECOVERY_KEYS = {
    "interface",
    "gateway",
    "routes",
    "verification",
    "allow_default_route_change",
    "allow_ssh_path_change",
}
ALLOWED_ROUTE_KEYS = {"destination", "via"}
ALLOWED_VERIFICATION_KEYS = {"required_checks"}
ALLOWED_VERIFICATION_CHECKS = {
    "nic_link",
    "ip_address",
    "gateway",
    "routes",
    "process",
    "listening_port",
    "http_health",
}
REQUIRED_VERIFICATION_CHECKS = {
    "nic_link",
    "ip_address",
    "gateway",
    "routes",
    "process",
    "listening_port",
}
OPTIONAL_VERIFICATION_CHECKS = {"http_health"}
CHECK_LAYERS = {
    "nic_link": "network",
    "ip_address": "network",
    "gateway": "network",
    "routes": "network",
    "process": "service",
    "listening_port": "service",
    "http_health": "service",
}
INTERFACE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,14}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,252}$")


class RecoveryRunnerError(RuntimeError):
    """A blocked or failed recovery request that callers can handle."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def require_json_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RecoveryRunnerError(f"{name} must be a JSON object")
    try:
        json.dumps(value)
    except (TypeError, ValueError) as error:
        raise RecoveryRunnerError(f"{name} must be JSON serializable: {error}") from error
    return value


def validate_diagnosis(incident_id: str, host: str, diagnosis: Any) -> dict[str, Any]:
    payload = require_json_object(diagnosis, "diagnosis")
    if isinstance(payload.get("diagnosis"), dict):
        if payload.get("incident_id") != incident_id:
            raise RecoveryRunnerError("Diagnosis incident_id does not match the request")
        if payload.get("host") != host:
            raise RecoveryRunnerError("Diagnosis host does not match the request")
        data = payload["diagnosis"]
    else:
        data = payload
    if data.get("diagnosis_status") in {"INSUFFICIENT_EVIDENCE", "NO_ISSUE"}:
        raise RecoveryRunnerError(
            f"Diagnosis status {data.get('diagnosis_status')!r} is not recoverable"
        )
    if data.get("rule_id") != ALLOWED_RULE:
        raise RecoveryRunnerError(
            f"Only {ALLOWED_RULE} can execute {ALLOWED_ACTION}"
        )
    recommended_action = data.get("recommended_action")
    if not isinstance(recommended_action, str) or recommended_action not in (
        ALLOWED_ACTION,
        DAY3_RECOMMENDED_ACTION,
    ):
        raise RecoveryRunnerError("Diagnosis recommended_action is not the NET-ROUTE-01 action")
    if "incident_id" in data and data.get("incident_id") != incident_id:
        raise RecoveryRunnerError("Diagnosis incident_id does not match the request")
    if "host" in data and data.get("host") != host:
        raise RecoveryRunnerError("Diagnosis host does not match the request")
    return data


def validate_recovery_vars(recovery_vars: Any) -> dict[str, Any]:
    data = require_json_object(recovery_vars, "recovery_vars")
    extras = set(data) - ALLOWED_RECOVERY_KEYS
    if extras:
        raise RecoveryRunnerError(f"Unsupported recovery_vars keys: {sorted(extras)}")

    interface = data.get("interface")
    if not isinstance(interface, str) or not INTERFACE_PATTERN.fullmatch(interface):
        raise RecoveryRunnerError("interface has an invalid Linux interface name")

    try:
        gateway = str(ipaddress.IPv4Address(data.get("gateway")))
    except ipaddress.AddressValueError as error:
        raise RecoveryRunnerError("gateway must be a valid IPv4 address") from error

    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        raise RecoveryRunnerError("routes must be a non-empty list")

    normalized_routes: list[dict[str, str]] = []
    destinations: set[str] = set()
    for position, route in enumerate(routes):
        if not isinstance(route, dict):
            raise RecoveryRunnerError(f"routes[{position}] must be an object")
        extras = set(route) - ALLOWED_ROUTE_KEYS
        if extras or set(route) != ALLOWED_ROUTE_KEYS:
            raise RecoveryRunnerError(
                f"routes[{position}] must contain only destination and via"
            )
        try:
            destination = str(ipaddress.IPv4Network(route["destination"], strict=True))
        except ValueError as error:
            raise RecoveryRunnerError(
                f"routes[{position}].destination must be a canonical IPv4 CIDR"
            ) from error
        try:
            via = str(ipaddress.IPv4Address(route["via"]))
        except ipaddress.AddressValueError as error:
            raise RecoveryRunnerError(
                f"routes[{position}].via must be a valid IPv4 address"
            ) from error
        if destination in destinations:
            raise RecoveryRunnerError(f"Duplicate route destination: {destination}")
        destinations.add(destination)
        normalized_routes.append({"destination": destination, "via": via})

    allow_default = data.get("allow_default_route_change", False)
    allow_ssh = data.get("allow_ssh_path_change", False)
    if not isinstance(allow_default, bool) or not isinstance(allow_ssh, bool):
        raise RecoveryRunnerError("Route safety approvals must be boolean values")
    if "0.0.0.0/0" in destinations and not allow_default:
        raise RecoveryRunnerError(
            "Default route recovery requires allow_default_route_change=true"
        )
    if "0.0.0.0/0" in destinations and not allow_ssh:
        raise RecoveryRunnerError(
            "Default route recovery requires allow_ssh_path_change=true"
        )

    verification = data.get("verification")
    if not isinstance(verification, dict):
        raise RecoveryRunnerError("verification must be an object")
    if set(verification) != ALLOWED_VERIFICATION_KEYS:
        raise RecoveryRunnerError("verification may contain only required_checks")
    required_checks = verification.get("required_checks")
    if not isinstance(required_checks, list) or not required_checks:
        raise RecoveryRunnerError("verification.required_checks must be a non-empty list")
    if any(not isinstance(item, str) for item in required_checks):
        raise RecoveryRunnerError("verification required check names must be strings")
    if len(set(required_checks)) != len(required_checks):
        raise RecoveryRunnerError("verification.required_checks contains duplicates")
    unsupported_checks = set(required_checks) - ALLOWED_VERIFICATION_CHECKS
    if unsupported_checks:
        raise RecoveryRunnerError(
            f"Unsupported verification checks: {sorted(unsupported_checks)}"
        )
    missing_checks = REQUIRED_VERIFICATION_CHECKS - set(required_checks)
    if missing_checks:
        raise RecoveryRunnerError(
            "verification.required_checks must include the mandatory network and SSH checks: "
            f"{sorted(missing_checks)}"
        )

    return {
        "interface": interface,
        "gateway": gateway,
        "routes": normalized_routes,
        "verification": {
            "required_checks": sorted(REQUIRED_VERIFICATION_CHECKS),
            "optional_checks": sorted(OPTIONAL_VERIFICATION_CHECKS),
        },
        "allow_default_route_change": allow_default,
        "allow_ssh_path_change": allow_ssh,
    }


def run_recovery_playbook(
    *, incident_id: str, host: str, recovery_vars: dict[str, Any], output_dir: Path
) -> dict[str, Any]:
    command = [
        "ansible-playbook",
        "-i",
        str(DEFAULT_INVENTORY),
        str(DEFAULT_PLAYBOOK),
        "--limit",
        host,
        "--extra-vars",
        json.dumps(
            {
                "incident_id": incident_id,
                "recovery_output_dir": str(output_dir),
                "network_recovery_config": recovery_vars,
            }
        ),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise RecoveryRunnerError(f"Could not start ansible-playbook: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise RecoveryRunnerError(
            f"Network recovery playbook failed with exit code {completed.returncode}: {detail}"
        )

    path = output_dir / f"{host}.json"
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RecoveryRunnerError(f"Invalid recovery result for host {host!r}: {error}") from error
    if result.get("incident_id") != incident_id or result.get("host") != host:
        raise RecoveryRunnerError("Recovery result incident_id or host does not match")
    recovery = result.get("recovery")
    if not isinstance(recovery, dict):
        raise RecoveryRunnerError("Recovery result is missing recovery data")
    return recovery


def collect_verification(incident_id: str, host: str) -> list[dict[str, Any]]:
    try:
        result = run_incident(incident_id, host)
    except IncidentRunnerError as error:
        raise RecoveryRunnerError(f"Verification evidence collection failed: {error}") from error
    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        raise RecoveryRunnerError("Verification collector returned invalid evidence")
    return evidence


def evaluate_verification(
    evidence: list[dict[str, Any]], required_checks: list[str]
) -> dict[str, Any]:
    check_names = [*required_checks, *sorted(OPTIONAL_VERIFICATION_CHECKS)]
    observed: dict[str, list[dict[str, str]]] = {name: [] for name in check_names}
    for item in evidence:
        if not isinstance(item, dict):
            continue
        name = item.get("check_name")
        if name in observed and item.get("layer") == CHECK_LAYERS[name]:
            observed[name].append(
                {
                    "result": str(item.get("result") or "UNKNOWN").upper(),
                    "detail": str(item.get("detail") or ""),
                }
            )

    required_results = [
        {
            "check_name": name,
            "results": [item["result"] for item in observed[name]],
        }
        for name in required_checks
    ]
    optional_results: list[dict[str, Any]] = []
    excluded_results: list[dict[str, str]] = []
    for name in sorted(OPTIONAL_VERIFICATION_CHECKS):
        values = observed[name]
        endpoint_not_configured = bool(values) and all(
            item["result"] == "SKIP" and "not configured" in item["detail"].lower()
            for item in values
        )
        if endpoint_not_configured:
            excluded_results.append(
                {"check_name": name, "reason": "ENDPOINT_NOT_CONFIGURED"}
            )
        else:
            optional_results.append(
                {"check_name": name, "results": [item["result"] for item in values]}
            )

    active_results = [*required_results, *optional_results]
    verified = all(
        item["results"] and all(result == "PASS" for result in item["results"])
        for item in active_results
    )
    return {
        "status": "VERIFIED" if verified else "ESCALATION_REQUIRED",
        "required_checks": required_results,
        "optional_checks": optional_results,
        "excluded_checks": excluded_results,
    }


def plan_after(recovery_vars: dict[str, Any]) -> dict[str, Any]:
    return {
        "interface": recovery_vars["interface"],
        "gateway": recovery_vars["gateway"],
        "routes": recovery_vars["routes"],
    }


def run_recovery(
    incident_id: str,
    host: str,
    diagnosis: dict[str, Any],
    recovery_vars: dict[str, Any],
    execute: bool = False,
) -> dict[str, Any]:
    if not isinstance(incident_id, str) or not IDENTIFIER_PATTERN.fullmatch(incident_id):
        raise RecoveryRunnerError("incident_id has an invalid format")
    if not isinstance(host, str) or not IDENTIFIER_PATTERN.fullmatch(host):
        raise RecoveryRunnerError("host has an invalid format")
    if not isinstance(execute, bool):
        raise RecoveryRunnerError("execute must be a boolean")
    validate_diagnosis(incident_id, host, diagnosis)
    normalized = validate_recovery_vars(recovery_vars)

    started_at = utc_now()
    started_clock = time.monotonic()
    if not execute:
        ended_at = utc_now()
        result = {
            "incident_id": incident_id,
            "host": host,
            "rule_id": ALLOWED_RULE,
            "action": ALLOWED_ACTION,
            "executor": "ansible",
            "mode": "PLAN_ONLY",
            "started_at": started_at,
            "ended_at": ended_at,
            "duration": round(time.monotonic() - started_clock, 6),
            "result": "PLANNED",
            "verification_status": "NOT_RUN",
            "verification": {
                "required_checks": normalized["verification"]["required_checks"],
                "optional_checks": normalized["verification"]["optional_checks"],
                "excluded_checks": [],
            },
            "before": {},
            "after": plan_after(normalized),
            "detail": None,
        }
        json.dumps(result)
        return result

    with tempfile.TemporaryDirectory(prefix="incident-network-recovery-") as directory:
        recovery = run_recovery_playbook(
            incident_id=incident_id,
            host=host,
            recovery_vars=normalized,
            output_dir=Path(directory),
        )
        verification_evidence = collect_verification(incident_id, host)

    verification = evaluate_verification(
        verification_evidence, normalized["verification"]["required_checks"]
    )
    verification_status = verification["status"]
    result_status = "SUCCESS" if verification_status == "VERIFIED" else "FAILED"
    ended_at = utc_now()
    result = {
        "incident_id": incident_id,
        "host": host,
        "rule_id": ALLOWED_RULE,
        "action": ALLOWED_ACTION,
        "executor": "ansible",
        "mode": "EXECUTE",
        "started_at": started_at,
        "ended_at": ended_at,
        "duration": round(time.monotonic() - started_clock, 6),
        "result": result_status,
        "verification_status": verification_status,
        "verification": verification,
        "before": recovery.get("before") or {},
        "after": recovery.get("after") or {},
        "detail": None,
    }
    json.dumps(result)
    return result


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RecoveryRunnerError(f"Could not load {label}: {error}") from error
    return require_json_object(value, label)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incident-id", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--diagnosis-json", required=True, type=Path)
    parser.add_argument("--recovery-vars", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_recovery(
            args.incident_id,
            args.host,
            load_json(args.diagnosis_json, "diagnosis"),
            load_json(args.recovery_vars, "recovery_vars"),
            execute=args.execute,
        )
    except RecoveryRunnerError as error:
        print(f"recovery_runner: {error}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
