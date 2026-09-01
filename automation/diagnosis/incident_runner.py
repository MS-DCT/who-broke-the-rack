#!/usr/bin/env python3
"""Collect incident evidence once and return evidence plus diagnosis as JSON."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from .diagnosis_engine import diagnose, normalize_result
except ImportError:  # Direct script execution.
    from diagnosis_engine import diagnose, normalize_result


HERE = Path(__file__).resolve().parent
AUTOMATION_DIR = HERE.parent
DEFAULT_PLAYBOOK = AUTOMATION_DIR / "ansible" / "playbooks" / "incident_diagnostic.yml"
DEFAULT_INVENTORY = AUTOMATION_DIR / "ansible" / "inventory.ini"


class IncidentRunnerError(RuntimeError):
    """Expected pipeline error suitable for a concise CLI failure message."""


def run_ansible_collection(
    *,
    incident_id: str,
    incident_started_at: str | None,
    host: str,
    output_dir: Path,
    inventory: Path,
    playbook: Path,
    ansible_playbook: str,
) -> None:
    variables = {
        "incident_id": incident_id,
        "evidence_output_dir": str(output_dir),
    }
    if incident_started_at is not None:
        variables["incident_started_at"] = incident_started_at
    extra_vars = json.dumps(variables)
    command = [
        ansible_playbook,
        "-i",
        str(inventory),
        str(playbook),
        "--limit",
        host,
        "--extra-vars",
        extra_vars,
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise IncidentRunnerError(f"Could not start ansible-playbook: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise IncidentRunnerError(
            f"Ansible diagnostic collection failed with exit code "
            f"{completed.returncode}: {detail}"
        )


def load_collected_evidence(output_dir: Path, incident_id: str, host: str) -> dict[str, Any]:
    candidates = sorted(
        output_dir.glob("*.json"), key=lambda path: path.stat().st_mtime_ns, reverse=True
    )
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise IncidentRunnerError(f"Invalid collected evidence {path}: {error}") from error
        if data.get("incident_id") == incident_id and data.get("host") == host:
            return data
    raise IncidentRunnerError(
        f"No collected evidence found for incident {incident_id!r} and host {host!r}"
    )


def select_host_hardware(payload: Any, host: str) -> dict[str, Any]:
    """Select one host document from a single document, list, or host-keyed object."""
    candidates: list[Any]
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict) and isinstance(payload.get("hosts"), list):
        candidates = payload["hosts"]
    elif isinstance(payload, dict) and isinstance(payload.get("hosts"), dict):
        selected = payload["hosts"].get(host)
        candidates = [{"host": host, **selected}] if isinstance(selected, dict) else []
    elif isinstance(payload, dict) and host in payload and isinstance(payload[host], dict):
        candidates = [{"host": host, **payload[host]}]
    else:
        candidates = [payload]

    matches = [item for item in candidates if isinstance(item, dict) and item.get("host") == host]
    if len(matches) != 1:
        raise IncidentRunnerError(
            f"Hardware evidence must contain exactly one document for host {host!r}"
        )
    return matches[0]


def merge_hardware_evidence(
    evidence: dict[str, Any], hardware_document: dict[str, Any]
) -> dict[str, Any]:
    merged = copy.deepcopy(evidence)
    hardware_results = hardware_document.get("results", [])
    if not isinstance(hardware_results, list):
        raise IncidentRunnerError("Hardware evidence 'results' must be a list")
    selected_results = [
        copy.deepcopy(item)
        for item in hardware_results
        if isinstance(item, dict)
        and str(item.get("category") or "").lower() in {"hardware", "boot"}
    ]
    if not selected_results:
        raise IncidentRunnerError("Hardware evidence has no hardware or boot categories")

    existing_results = merged.get("results", [])
    if not isinstance(existing_results, list):
        raise IncidentRunnerError("Collected evidence 'results' must be a list")
    retained = [
        item
        for item in existing_results
        if not isinstance(item, dict)
        or str(item.get("category") or "").lower() not in {"hardware", "boot"}
    ]
    merged["results"] = [*selected_results, *retained]
    return merged


BOOT_CHECK_NAMES = {
    "post_state",
    "post_status",
    "boot_state",
    "boot_status",
    "os_boot",
    "os_access",
    "os_reachability",
}


def normalize_hardware_evidence(
    hardware_document: dict[str, Any], *, incident_id: str, host: str
) -> dict[str, Any]:
    """Convert A's common hardware document to the internal results/checks shape."""
    document_host = hardware_document.get("host")
    if document_host is not None and document_host != host:
        raise IncidentRunnerError(
            f"Hardware evidence host {document_host!r} does not match target host {host!r}"
        )
    document_incident_id = hardware_document.get("incident_id")
    if document_incident_id is not None and document_incident_id != incident_id:
        raise IncidentRunnerError(
            "Hardware evidence incident_id "
            f"{document_incident_id!r} does not match runner incident_id {incident_id!r}"
        )

    # A legacy document already uses the diagnosis engine's native shape.
    if "evidence" not in hardware_document:
        return hardware_document

    if str(hardware_document.get("category") or "").lower() != "hardware":
        raise IncidentRunnerError("Hardware evidence 'category' must be 'hardware'")
    evidence = hardware_document.get("evidence")
    if not isinstance(evidence, dict):
        raise IncidentRunnerError("Hardware evidence 'evidence' must be an object")

    document_source = hardware_document.get("source")
    document_timestamp = hardware_document.get("timestamp")
    categorized_checks: dict[str, list[dict[str, Any]]] = {
        "hardware": [],
        "boot": [],
    }
    for name, item in evidence.items():
        if not isinstance(item, dict):
            raise IncidentRunnerError(f"Hardware evidence item {name!r} must be an object")
        check = {
            "name": name,
            "result": item.get("result"),
            "value": item.get("value"),
            "detail": item.get("detail"),
            "source": item.get("source", document_source),
            "timestamp": document_timestamp,
        }
        layer = "boot" if snake_case(name) in BOOT_CHECK_NAMES else "hardware"
        categorized_checks[layer].append(check)

    iml_events = hardware_document.get("iml_events", [])
    if not isinstance(iml_events, list):
        raise IncidentRunnerError("Hardware evidence 'iml_events' must be a list")
    for event in iml_events:
        if not isinstance(event, dict):
            raise IncidentRunnerError("Hardware evidence IML events must be objects")
        categorized_checks["hardware"].append(
            {
                "name": "iml_event",
                "message": event.get("message"),
                "severity": event.get("severity"),
                "created": event.get("created"),
                "subsystem": event.get("subsystem"),
            }
        )

    return {
        "incident_id": document_incident_id,
        "server_id": hardware_document.get("server_id"),
        "host": document_host,
        "timestamp": document_timestamp,
        "results": [
            {"category": category, "checks": checks}
            for category, checks in categorized_checks.items()
            if checks
        ],
    }


def load_and_merge_hardware(
    evidence: dict[str, Any],
    hardware_evidence: Any,
    host: str,
    incident_id: str | None = None,
) -> dict[str, Any]:
    if isinstance(hardware_evidence, (str, Path)):
        hardware_path = Path(hardware_evidence)
        try:
            payload = json.loads(hardware_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise IncidentRunnerError(f"Could not load hardware evidence: {error}") from error
    else:
        payload = hardware_evidence
    selected = select_host_hardware(payload, host)
    normalized = normalize_hardware_evidence(
        selected,
        incident_id=incident_id or str(evidence.get("incident_id") or ""),
        host=host,
    )
    return merge_hardware_evidence(evidence, normalized)


def snake_case(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    text = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return text or None


def flatten_evidence(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert category/check evidence into C's stable database-ingest shape."""
    flattened: list[dict[str, Any]] = []
    incident_id = data.get("incident_id")
    host = data.get("host")
    generated_at = data.get("generated_at")
    results = data.get("results", [])
    if not isinstance(results, list):
        return flattened

    for category in results:
        if not isinstance(category, dict):
            continue
        layer = category.get("category")
        checks = category.get("checks", [])
        if not isinstance(checks, list):
            continue
        for check in checks:
            if not isinstance(check, dict):
                continue
            raw_result = next(
                (
                    check[key]
                    for key in ("status", "result", "value", "health", "severity")
                    if check.get(key) is not None
                ),
                None,
            )
            flattened.append(
                {
                    "incident_id": incident_id,
                    "timestamp": (
                        check.get("timestamp")
                        or check.get("created")
                        or check.get("event_created")
                        or generated_at
                    ),
                    "host": host,
                    "layer": str(layer).lower() if layer is not None else None,
                    "source": (
                        check.get("source")
                        or category.get("source")
                        or (check.get("target") if str(layer).lower() == "service" else None)
                    ),
                    "check_name": snake_case(check.get("name")),
                    "result": normalize_result(raw_result),
                    "severity": check.get("severity"),
                    "detail": (
                        check.get("detail")
                        if check.get("detail") is not None
                        else check.get("details", check.get("message"))
                    ),
                    "value": check.get("value"),
                }
            )
    return flattened


def diagnosis_contract(diagnosis: dict[str, Any]) -> dict[str, Any]:
    contracted = {
        "rule_id": diagnosis.get("rule_id"),
        "root_cause": diagnosis.get("root_cause"),
        "matched_evidence": diagnosis.get("matched_evidence") or [],
        "recommended_action": diagnosis.get("recommended_action"),
        "severity": diagnosis.get("severity"),
    }
    for key in (
        "diagnosis_status",
        "evidence_gaps",
        "timestamp",
        "server_id",
    ):
        if key in diagnosis:
            contracted[key] = diagnosis[key]
    return contracted


def run_incident(
    incident_id: str,
    host: str,
    *,
    incident_started_at: str | None = None,
    hardware_evidence: Any = None,
) -> dict[str, Any]:
    if not isinstance(incident_id, str) or not incident_id.strip():
        raise IncidentRunnerError("incident_id must be a non-empty string")
    if not isinstance(host, str) or not host.strip():
        raise IncidentRunnerError("host must be a non-empty string")

    with tempfile.TemporaryDirectory(prefix="incident-diagnostic-") as directory:
        output_dir = Path(directory)
        run_ansible_collection(
            incident_id=incident_id,
            incident_started_at=incident_started_at,
            host=host,
            output_dir=output_dir,
            inventory=DEFAULT_INVENTORY,
            playbook=DEFAULT_PLAYBOOK,
            ansible_playbook="ansible-playbook",
        )
        evidence = load_collected_evidence(output_dir, incident_id, host)
        if incident_started_at is None:
            evidence.pop("incident_started_at", None)
        else:
            evidence["incident_started_at"] = incident_started_at
        if hardware_evidence is not None:
            evidence = load_and_merge_hardware(
                evidence, hardware_evidence, host, incident_id=incident_id
            )
        diagnosis = diagnose(evidence, incident_id=incident_id, server_id=host)
        result = {
            "incident_id": incident_id,
            "host": host,
            "evidence": flatten_evidence(evidence),
            "diagnosis": diagnosis_contract(diagnosis),
        }
        try:
            json.dumps(result)
        except (TypeError, ValueError) as error:
            raise IncidentRunnerError(f"Incident result is not JSON serializable: {error}") from error
        return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incident-id", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--incident-started-at")
    parser.add_argument("--hardware-evidence", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_incident(
            args.incident_id,
            args.host,
            incident_started_at=args.incident_started_at,
            hardware_evidence=args.hardware_evidence,
        )
    except (IncidentRunnerError, OSError, ValueError) as error:
        print(f"incident_runner: {error}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
