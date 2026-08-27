#!/usr/bin/env python3
"""Evaluate diagnostic evidence using diagnosis rules."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


VALID_RESULTS = {"PASS", "FAIL", "WARN", "UNKNOWN", "SKIP"}
PASS_ALIASES = {
    "OK",
    "ON",
    "ENABLED",
    "GOODINUSE",
    "FINISHEDPOST",
    "LOGGEDIN",
    "LOGINCONFIRMED",
    "OSLOGINCONFIRMED",
}
WARN_ALIASES = {"WARNING", "DEGRADED", "CAUTION"}
FAIL_ALIASES = {"FAILED", "ERROR", "CRITICAL"}

HARDWARE_STORAGE_NAMES = (
    "storage_health",
    "storage_controller",
    "logical_drive",
    "physical_drive",
)
HARDWARE_STORAGE_NAME_PATTERN = re.compile(
    r"^(?:controller|logical_drive|physical_drive)_\d+_health$"
)
SYSTEM_HEALTH_REFS = (
    ("hardware", "system_health"),
    ("hardware", "hardware_health"),
)
POWER_REFS = (("hardware", "power_state"),)
POST_REFS = (
    ("hardware", "post_status"),
    ("hardware", "post_state"),
    ("boot", "post_status"),
    ("boot", "post_state"),
)
BOOT_OS_REFS = (
    ("boot", "boot_state"),
    ("boot", "boot_status"),
    ("boot", "os_boot"),
    ("boot", "os_access"),
    ("boot", "os_reachability"),
    ("os", "os_access"),
    ("os", "os_reachability"),
)
NETWORK_REFS = tuple(
    ("network", name) for name in ("nic_link", "ip_address", "gateway", "routes")
)
SERVICE_REFS = tuple(
    ("service", name) for name in ("process", "listening_port", "http_health")
)
STORAGE_IML_REFS = (
    # Legacy locations
    ("hardware", "storage_iml_event"),
    ("hardware", "iml_event"),
    # Common Collector format converted by incident_runner.py
    ("event", "storage_iml_event"),
    ("event", "iml_event"),
)

HEALTH_REQUIREMENTS = (
    ("hardware", "system_health", SYSTEM_HEALTH_REFS),
    ("hardware", "power_state", POWER_REFS),
    ("hardware", "storage_health", (("hardware", "storage_health"),)),
    ("boot", "post_status", POST_REFS),
    ("boot", "boot_or_os_access", BOOT_OS_REFS),
    *(("network", name, (("network", name),)) for _, name in NETWORK_REFS),
    *(("service", name, (("service", name),)) for _, name in SERVICE_REFS),
)


def compact_status(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def normalize_result(value: Any) -> str:
    result = str(value or "UNKNOWN").upper()
    if result in VALID_RESULTS:
        return result
    compact = compact_status(value)
    if compact in PASS_ALIASES:
        return "PASS"
    if compact in WARN_ALIASES:
        return "WARN"
    if compact in FAIL_ALIASES:
        return "FAIL"
    return "UNKNOWN"


def build_index(data: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Index only supplied checks; missing evidence is never synthesized as PASS."""
    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    results = data.get("results", [])
    if not isinstance(results, list):
        return index

    for category in results:
        if not isinstance(category, dict):
            continue
        layer = str(category.get("category") or "").lower()
        checks = category.get("checks", [])
        if not layer or not isinstance(checks, list):
            continue
        layer_index = index.setdefault(layer, {})
        for check in checks:
            if not isinstance(check, dict):
                continue
            check_name = str(check.get("name") or "").lower()
            if not check_name:
                continue
            raw_result = next(
                (
                    check[key]
                    for key in ("status", "result", "value", "health", "severity")
                    if check.get(key) is not None
                ),
                None,
            )
            layer_index.setdefault(check_name, []).append(
                {
                    "layer": layer,
                    "check_name": check_name,
                    "result": normalize_result(raw_result),
                    "_raw": check,
                }
            )
    return index


def checks_for(
    index: dict[str, dict[str, list[dict[str, Any]]]],
    references: Iterable[tuple[str, str]],
) -> list[dict[str, Any]]:
    return [
        check
        for layer, check_name in references
        for check in index.get(layer, {}).get(check_name, [])
    ]


def storage_health_checks(
    index: dict[str, dict[str, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    """Return aggregate and per-device storage health checks."""
    hardware = index.get("hardware", {})
    return [
        check
        for check_name, checks in hardware.items()
        if check_name in HARDWARE_STORAGE_NAMES
        or HARDWARE_STORAGE_NAME_PATTERN.fullmatch(check_name)
        for check in checks
    ]


def confirmed_pass(
    index: dict[str, dict[str, list[dict[str, Any]]]],
    references: Iterable[tuple[str, str]],
) -> bool:
    observed = checks_for(index, references)
    return bool(observed) and all(check["result"] == "PASS" for check in observed)


def explicit_fail(
    index: dict[str, dict[str, list[dict[str, Any]]]],
    references: Iterable[tuple[str, str]],
) -> bool:
    return any(check["result"] == "FAIL" for check in checks_for(index, references))


def evidence_gaps(
    index: dict[str, dict[str, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for layer, check_name, references in HEALTH_REQUIREMENTS:
        observed = checks_for(index, references)
        if not observed:
            gaps.append({"layer": layer, "check_name": check_name, "reason": "MISSING"})
        elif not confirmed_pass(index, references):
            gaps.append(
                {
                    "layer": layer,
                    "check_name": check_name,
                    "reason": "NOT_CONFIRMED_PASS",
                    "observed_results": sorted({item["result"] for item in observed}),
                }
            )
    return gaps


def public_evidence(checks: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "layer": str(check["layer"]),
            "check_name": str(check["check_name"]),
            "result": str(check["result"]),
        }
        for check in checks
    ]


def parse_evidence_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def incident_storage_events(
    data: dict[str, Any], index: dict[str, dict[str, list[dict[str, Any]]]]
) -> list[dict[str, Any]]:
    incident_start = parse_evidence_time(data.get("incident_started_at"))
    if incident_start is None:
        return []

    related: list[dict[str, Any]] = []
    for event in checks_for(index, STORAGE_IML_REFS):
        raw = event["_raw"]
        if event["result"] not in {"WARN", "FAIL"}:
            continue
        if event["check_name"] == "iml_event":
            component = compact_status(
                raw.get("subsystem") or raw.get("component") or raw.get("category")
            )
            if component != "STORAGE":
                continue
        created = parse_evidence_time(
            raw.get("created") or raw.get("event_created") or raw.get("timestamp")
        )
        if created is not None and created >= incident_start:
            related.append(event)
    return related


def safe_token(value: Any) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "unknown")).strip("-")
    return token or "unknown"


def result_base(
    data: dict[str, Any], incident_id: str | None, server_id: str | None
) -> dict[str, str]:
    host = str(data.get("host") or data.get("ansible_host") or "unknown")
    source_timestamp = str(data.get("generated_at") or "")
    timestamp = source_timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    incident = (
        incident_id
        or data.get("incident_id")
        or f"DIAG-{safe_token(host)}-{safe_token(source_timestamp or 'undated')}"
    )
    server = server_id or data.get("server_id") or host
    return {
        "incident_id": str(incident),
        "server_id": str(server),
        "host": host,
        "timestamp": timestamp,
    }


def matched_result(
    base: dict[str, str],
    rule_id: str,
    root_cause: str,
    matched_evidence: list[dict[str, str]],
    recommended_action: str,
    severity: str,
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        **base,
        "diagnosis_status": "MATCHED",
        "rule_id": rule_id,
        "root_cause": root_cause,
        "matched_evidence": matched_evidence,
        "recommended_action": recommended_action,
        "severity": severity,
        "evidence_gaps": gaps,
    }


def diagnose(
    data: dict[str, Any], incident_id: str | None = None, server_id: str | None = None
) -> dict[str, Any]:
    """Return the first diagnosis in hardware -> boot/OS -> network -> service order."""
    index = build_index(data)
    base = result_base(data, incident_id, server_id)
    gaps = evidence_gaps(index)

    unhealthy_storage = [
        check
        for check in storage_health_checks(index)
        if check["result"] in {"WARN", "FAIL"}
    ]
    related_storage_events = incident_storage_events(data, index)
    if unhealthy_storage and related_storage_events:
        return matched_result(
            base,
            "HW-STORAGE-01",
            "Current storage health is degraded and a storage IML event is related to this incident",
            public_evidence([*unhealthy_storage, *related_storage_events]),
            "Correlate the current storage health with the incident IML event, then inspect the affected controller and drives.",
            "CRITICAL",
            gaps,
        )

    if confirmed_pass(index, POST_REFS) and explicit_fail(index, BOOT_OS_REFS):
        matched = [
            *checks_for(index, POST_REFS),
            *checks_for(index, BOOT_OS_REFS),
        ]
        return matched_result(
            base,
            "BOOT-OS-01",
            "Boot or operating-system access failed after POST passed",
            public_evidence(matched),
            "Review boot console evidence, boot device selection, and the operating-system boot path.",
            "CRITICAL",
            gaps,
        )

    route_prerequisites = (("network", "nic_link"), ("network", "ip_address"))
    route_outcomes = (("network", "gateway"), ("network", "routes"))
    if all(confirmed_pass(index, (ref,)) for ref in route_prerequisites) and explicit_fail(
        index, route_outcomes
    ):
        return matched_result(
            base,
            "NET-ROUTE-01",
            "Gateway or required route failed while NIC link and IP address passed",
            public_evidence(checks_for(index, NETWORK_REFS)),
            "Verify the gateway and required destination routes, then correct the routing configuration.",
            "HIGH",
            gaps,
        )

    if all(confirmed_pass(index, (ref,)) for ref in NETWORK_REFS) and explicit_fail(
        index, SERVICE_REFS
    ):
        return matched_result(
            base,
            "SVC-HTTP-01",
            "Service process, listening port, or HTTP health evidence reports an explicit failure",
            public_evidence(
                [*checks_for(index, NETWORK_REFS), *checks_for(index, SERVICE_REFS)]
            ),
            "Inspect the failed service process, listening socket, application logs, and HTTP health endpoint.",
            "HIGH",
            gaps,
        )

    insufficient = bool(gaps)
    return {
        **base,
        "diagnosis_status": "INSUFFICIENT_EVIDENCE" if insufficient else "NO_ISSUE",
        "rule_id": None,
        "root_cause": (
            "Insufficient evidence to determine a root cause"
            if insufficient
            else "No fault matched the diagnosis rules"
        ),
        "matched_evidence": [],
        "recommended_action": (
            "Collect or explicitly verify the checks listed in evidence_gaps."
            if insufficient
            else "Continue monitoring."
        ),
        "severity": "UNKNOWN" if insufficient else "INFO",
        "evidence_gaps": gaps,
    }


def output_path(output_dir: Path, input_path: Path) -> Path:
    return output_dir / f"{input_path.stem}.diagnosis.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="Evidence JSON file(s)")
    parser.add_argument("--output-dir", type=Path, default=Path("diagnosis-output"))
    parser.add_argument("--incident-id", help="Override incident ID; requires one input")
    parser.add_argument("--server-id", help="Override server ID; requires one input")
    args = parser.parse_args()
    if len(args.inputs) != 1 and (args.incident_id or args.server_id):
        parser.error("ID overrides require exactly one input")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for input_path in args.inputs:
        with input_path.open(encoding="utf-8") as source:
            data = json.load(source)
        result = diagnose(data, args.incident_id, args.server_id)
        destination = output_path(args.output_dir, input_path)
        with destination.open("w", encoding="utf-8") as target:
            json.dump(result, target, ensure_ascii=False, indent=2)
            target.write("\n")
        print(
            f"{input_path}: {result['diagnosis_status']} "
            f"{result['rule_id'] or '-'} -> {destination}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
