#!/usr/bin/env python3
"""Plan or execute an approved rule-dispatched incident recovery workflow."""

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
NETWORK_PLAYBOOK = AUTOMATION_DIR / "ansible" / "playbooks" / "incident_network_recovery.yml"
SERVICE_PLAYBOOK = AUTOMATION_DIR / "ansible" / "playbooks" / "incident_service_recovery.yml"
DEFAULT_PLAYBOOK = NETWORK_PLAYBOOK  # Backward-compatible public constant.
NETWORK_RULE = "NET-ROUTE-01"
SERVICE_RULE = "SVC-HTTP-01"
NETWORK_ACTION = "network_recovery"
SERVICE_ACTION = "service_recovery"
NETWORK_RECOMMENDED_ACTION = (
    "Verify the gateway and required destination routes, then correct the routing configuration."
)
SERVICE_RECOMMENDED_ACTION = (
    "Inspect the failed service process, listening socket, application logs, and HTTP health endpoint."
)
RULE_ACTIONS = {
    NETWORK_RULE: (NETWORK_ACTION, {NETWORK_ACTION, NETWORK_RECOMMENDED_ACTION}),
    SERVICE_RULE: (SERVICE_ACTION, {SERVICE_ACTION, SERVICE_RECOMMENDED_ACTION}),
}
SERVICE_RECOVERY_PROFILES = {
    "day5_mock_http": {
        "service_name": "wbr-day5-mock.service",
        "package_name": "wbr-day5-mock",
        "config_path": "/etc/who-broke-the-rack/day5-mock.conf",
        "config_mode": "0644",
        "validation_argv": [
            "/usr/bin/wbr-day5-mock",
            "--check-config",
            "/etc/who-broke-the-rack/day5-mock.conf",
        ],
        "process_pattern": "wbr-day5-mock",
        "port": 18080,
        "http_url": "http://127.0.0.1:18080/health",
        "expected_body": None,
    },
    "dca_target02_nginx": {
        "allowed_host": "dca-target02",
        "service_name": "nginx.service",
        "package_name": "nginx",
        "config_path": "/etc/nginx/default.d/health.conf",
        "config_mode": "0644",
        "validation_argv": ["/usr/sbin/nginx", "-t"],
        "process_pattern": "nginx",
        "port": 80,
        "http_url": "http://127.0.0.1/health",
        "external_http_url": "http://192.168.100.207/health",
        "expected_body": "OK",
        "verification_target": "nginx",
    },
}
SERVICE_RECOVERY_KEYS = {"profile", "config_content", "http_enabled"}
ALLOWED_RECOVERY_KEYS = {
    "interface",
    "gateway",
    "routes",
    "remove_blackhole_routes",
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
    "pxe_reachability",
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
    "pxe_reachability": "network",
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
    rule_id = data.get("rule_id")
    if rule_id not in RULE_ACTIONS:
        raise RecoveryRunnerError(f"Unsupported recovery rule: {rule_id!r}")
    action, recommended_actions = RULE_ACTIONS[rule_id]
    recommended_action = data.get("recommended_action")
    if (
        not isinstance(recommended_action, str)
        or recommended_action not in recommended_actions
    ):
        raise RecoveryRunnerError(
            f"Diagnosis recommended_action is not the {rule_id} action {action!r}"
        )
    if "incident_id" in data and data.get("incident_id") != incident_id:
        raise RecoveryRunnerError("Diagnosis incident_id does not match the request")
    if "host" in data and data.get("host") != host:
        raise RecoveryRunnerError("Diagnosis host does not match the request")
    return data


def validate_network_recovery_vars(recovery_vars: Any) -> dict[str, Any]:
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
    if not isinstance(routes, list):
        raise RecoveryRunnerError("routes must be a list")

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

    remove_blackhole_routes = data.get("remove_blackhole_routes", [])
    if not isinstance(remove_blackhole_routes, list):
        raise RecoveryRunnerError("remove_blackhole_routes must be a list")
    normalized_blackholes: list[str] = []
    for position, destination_value in enumerate(remove_blackhole_routes):
        try:
            destination = ipaddress.IPv4Network(destination_value, strict=True)
        except (TypeError, ValueError) as error:
            raise RecoveryRunnerError(
                f"remove_blackhole_routes[{position}] must be a canonical IPv4 CIDR"
            ) from error
        if destination.prefixlen != 32:
            raise RecoveryRunnerError("Only exact /32 blackhole routes may be removed")
        normalized_destination = str(destination)
        if normalized_destination in normalized_blackholes:
            raise RecoveryRunnerError(
                f"Duplicate blackhole route destination: {normalized_destination}"
            )
        normalized_blackholes.append(normalized_destination)
    if not normalized_routes and not normalized_blackholes:
        raise RecoveryRunnerError(
            "routes or remove_blackhole_routes must contain at least one recovery action"
        )

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
    requested_required_checks = (
        REQUIRED_VERIFICATION_CHECKS
        | (set(required_checks) - OPTIONAL_VERIFICATION_CHECKS)
    )

    return {
        "interface": interface,
        "gateway": gateway,
        "routes": normalized_routes,
        "remove_blackhole_routes": normalized_blackholes,
        "verification": {
            "required_checks": sorted(requested_required_checks),
            "optional_checks": sorted(OPTIONAL_VERIFICATION_CHECKS),
        },
        "allow_default_route_change": allow_default,
        "allow_ssh_path_change": allow_ssh,
    }


def validate_service_recovery_vars(recovery_vars: Any) -> dict[str, Any]:
    data = require_json_object(recovery_vars, "recovery_vars")
    if set(data) != SERVICE_RECOVERY_KEYS:
        raise RecoveryRunnerError(
            f"Service recovery_vars must contain only {sorted(SERVICE_RECOVERY_KEYS)}"
        )
    profile_name = data.get("profile")
    if profile_name not in SERVICE_RECOVERY_PROFILES:
        raise RecoveryRunnerError(f"Unsupported service recovery profile: {profile_name!r}")
    config_content = data.get("config_content")
    if config_content is not None and not isinstance(config_content, str):
        raise RecoveryRunnerError("config_content must be a string or null")
    if isinstance(config_content, str) and len(config_content.encode("utf-8")) > 65536:
        raise RecoveryRunnerError("config_content exceeds the 64 KiB safety limit")
    http_enabled = data.get("http_enabled")
    if not isinstance(http_enabled, bool):
        raise RecoveryRunnerError("http_enabled must be a boolean")
    return {
        "profile": profile_name,
        **SERVICE_RECOVERY_PROFILES[profile_name],
        "config_content": config_content,
        "config_restore_requested": config_content is not None,
        "http_enabled": http_enabled,
        "verification": {
            "required_checks": sorted(
                REQUIRED_VERIFICATION_CHECKS
                | ({"http_health"} if http_enabled else set())
            ),
            "optional_checks": [] if http_enabled else ["http_health"],
        },
    }


def validate_recovery_vars(
    recovery_vars: Any, rule_id: str = NETWORK_RULE
) -> dict[str, Any]:
    if rule_id == NETWORK_RULE:
        return validate_network_recovery_vars(recovery_vars)
    if rule_id == SERVICE_RULE:
        return validate_service_recovery_vars(recovery_vars)
    raise RecoveryRunnerError(f"Unsupported recovery rule: {rule_id!r}")


def _run_recovery_playbook(
    *,
    incident_id: str,
    host: str,
    recovery_vars: dict[str, Any],
    output_dir: Path,
    playbook: Path,
    config_key: str,
) -> dict[str, Any]:
    command = [
        "ansible-playbook",
        "-i",
        str(DEFAULT_INVENTORY),
        str(playbook),
        "--limit",
        host,
        "--extra-vars",
        json.dumps(
            {
                "incident_id": incident_id,
                "recovery_output_dir": str(output_dir),
                config_key: recovery_vars,
            }
        ),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise RecoveryRunnerError(f"Could not start ansible-playbook: {error}") from error
    if completed.returncode != 0:
        detail = completed.stdout.strip() or completed.stderr.strip() or "unknown error"
        raise RecoveryRunnerError(
            f"Recovery playbook failed with exit code {completed.returncode}: {detail}"
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


def run_recovery_playbook(
    *, incident_id: str, host: str, recovery_vars: dict[str, Any], output_dir: Path
) -> dict[str, Any]:
    """Run the existing network playbook (kept for API and mock compatibility)."""
    return _run_recovery_playbook(
        incident_id=incident_id,
        host=host,
        recovery_vars=recovery_vars,
        output_dir=output_dir,
        playbook=NETWORK_PLAYBOOK,
        config_key="network_recovery_config",
    )


def run_service_recovery_playbook(
    *, incident_id: str, host: str, recovery_vars: dict[str, Any], output_dir: Path
) -> dict[str, Any]:
    return _run_recovery_playbook(
        incident_id=incident_id,
        host=host,
        recovery_vars=recovery_vars,
        output_dir=output_dir,
        playbook=SERVICE_PLAYBOOK,
        config_key="service_recovery_config",
    )


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
    evidence: list[dict[str, Any]],
    required_checks: list[str],
    optional_checks: list[str] | None = None,
    service_target: str | None = None,
) -> dict[str, Any]:
    optional = sorted(
        OPTIONAL_VERIFICATION_CHECKS if optional_checks is None else optional_checks
    )
    check_names = [*required_checks, *optional]
    observed: dict[str, list[dict[str, str]]] = {name: [] for name in check_names}
    excluded_results: list[dict[str, str]] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        name = item.get("check_name")
        if name in observed and item.get("layer") == CHECK_LAYERS[name]:
            item_target = item.get("source") or item.get("target")
            if item.get("layer") == "service" and service_target is not None:
                if item_target != service_target:
                    excluded_results.append(
                        {
                            "check_name": str(name),
                            "target": str(item_target or "UNKNOWN"),
                            "reason": "NON_TARGET_SERVICE",
                        }
                    )
                    continue
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
    for name in optional:
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
        "removed_blackhole_routes": recovery_vars["remove_blackhole_routes"],
    }


def service_plan_after(recovery_vars: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": recovery_vars["profile"],
        "service_name": recovery_vars["service_name"],
        "package_name": recovery_vars["package_name"],
        "config_path": recovery_vars["config_path"],
        "validation_argv": recovery_vars["validation_argv"],
        "config_restore_requested": recovery_vars["config_restore_requested"],
        "http_enabled": recovery_vars["http_enabled"],
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
    diagnosis_data = validate_diagnosis(incident_id, host, diagnosis)
    rule_id = str(diagnosis_data["rule_id"])
    action = RULE_ACTIONS[rule_id][0]
    normalized = validate_recovery_vars(recovery_vars, rule_id)
    if rule_id == SERVICE_RULE:
        allowed_host = normalized.get("allowed_host")
        if allowed_host is not None and host != allowed_host:
            raise RecoveryRunnerError(
                f"Service recovery profile {normalized['profile']!r} is restricted to host {allowed_host!r}"
            )
    optional_checks = normalized["verification"]["optional_checks"]

    started_at = utc_now()
    started_clock = time.monotonic()
    if not execute:
        ended_at = utc_now()
        result = {
            "incident_id": incident_id,
            "host": host,
            "rule_id": rule_id,
            "action": action,
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
            "after": (
                plan_after(normalized)
                if rule_id == NETWORK_RULE
                else service_plan_after(normalized)
            ),
            "detail": None,
        }
        json.dumps(result)
        return result

    with tempfile.TemporaryDirectory(prefix="incident-recovery-") as directory:
        playbook_runner = (
            run_recovery_playbook
            if rule_id == NETWORK_RULE
            else run_service_recovery_playbook
        )
        recovery = playbook_runner(
            incident_id=incident_id,
            host=host,
            recovery_vars=normalized,
            output_dir=Path(directory),
        )
        verification_evidence = collect_verification(incident_id, host)

    verification = evaluate_verification(
        verification_evidence,
        normalized["verification"]["required_checks"],
        optional_checks,
        normalized.get("verification_target") if rule_id == SERVICE_RULE else None,
    )
    recovery_failed = bool(recovery.get("recovery_failed", False))
    if recovery_failed:
        verification["status"] = "ESCALATION_REQUIRED"
        verification["recovery_error"] = recovery.get("recovery_error")
    verification_status = verification["status"]
    result_status = "SUCCESS" if verification_status == "VERIFIED" else "FAILED"
    ended_at = utc_now()
    result = {
        "incident_id": incident_id,
        "host": host,
        "rule_id": rule_id,
        "action": action,
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
        "detail": recovery.get("recovery_error") if recovery_failed else None,
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
    return 2 if result.get("verification_status") == "ESCALATION_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
