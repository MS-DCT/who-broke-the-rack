#!/usr/bin/env python3
"""Common diagnosis, recovery, escalation, and rebuild orchestration."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from automation.diagnosis.incident_runner import run_incident
from automation.recovery.escalation_engine import LEVELS, run_escalation
from automation.recovery.recovery_runner import run_recovery
from automation.recovery.standard_build_runner import run_standard_build


class WorkflowError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _event(incident_id: str, level: str, action: str, host: str, status: str, result: Any, detail: str, started: float) -> dict[str, Any]:
    return {"incident_id": incident_id, "timestamp": _now(), "level": level, "action": action, "target_host": host, "status": status, "result": result, "detail": detail, "duration_ms": round((time.monotonic() - started) * 1000, 3)}


def run_workflow(
    incident_id: str,
    failed_host: str,
    recovery_vars: dict[str, Any],
    *,
    execute: bool = False,
    incident_result: dict[str, Any] | None = None,
    adapters: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
    execution_state: dict[str, Any] | None = None,
    incident_runner: Callable[..., dict[str, Any]] = run_incident,
    recovery_runner: Callable[..., dict[str, Any]] = run_recovery,
    standard_build_runner: Callable[..., dict[str, Any]] = run_standard_build,
) -> dict[str, Any]:
    """Run one resumable workflow without persisting to a database."""
    state = execution_state if execution_state is not None else {}
    timeline: list[dict[str, Any]] = []
    started = time.monotonic()
    incident = incident_result or incident_runner(incident_id, failed_host)
    diagnosis = incident.get("diagnosis")
    if not isinstance(diagnosis, dict) or not diagnosis.get("rule_id"):
        raise WorkflowError("Incident did not produce a recoverable diagnosis")
    rule_id = str(diagnosis["rule_id"])
    level = "L1" if rule_id == "SVC-HTTP-01" else "L2" if rule_id == "NET-ROUTE-01" else None
    if level is None:
        raise WorkflowError(f"Unsupported software recovery rule: {rule_id}")
    timeline.append(_event(incident_id, level, "DIAGNOSIS", failed_host, "MATCHED", diagnosis, rule_id, started))

    recovery_key = f"{incident_id}:{failed_host}:{level}:SOFTWARE_RECOVERY"
    if recovery_key in state:
        recovery = state[recovery_key]
    else:
        recovery = recovery_runner(incident_id, failed_host, incident, recovery_vars, execute=execute)
        state[recovery_key] = recovery
    recovery_status = str(recovery.get("verification_status", "NOT_RUN"))
    timeline.append(_event(incident_id, level, "SOFTWARE_RECOVERY", failed_host, recovery_status, recovery, "Existing recovery runner", started))
    if recovery_status == "VERIFIED":
        result = {"incident_id": incident_id, "failed_host": failed_host, "current_level": level, "attempted_levels": [level], "status": "VERIFIED", "next_action": None, "retry_count": 0, "timeline_events": timeline, "execution_state": state, "error": None}
        json.dumps(result)
        return result
    if not execute and recovery.get("mode") == "PLAN_ONLY":
        result = {"incident_id": incident_id, "failed_host": failed_host, "current_level": level, "attempted_levels": [level], "status": "PLAN_ONLY", "next_action": "EXECUTE_SOFTWARE_RECOVERY", "retry_count": 0, "timeline_events": timeline, "execution_state": state, "escalation_reason": None}
        json.dumps(result)
        return result

    attempted = [level]
    current = "L2" if level == "L1" else "L3"
    last: dict[str, Any] = {}
    while current:
        last = run_escalation(incident_id, failed_host, rule_id, current_level=current, attempted_levels=attempted, execution_state=state, adapters=adapters)
        timeline.extend(last["timeline_events"])
        attempted = last["attempted_levels"]
        if last["status"] in {"VERIFIED", "MANUAL_REQUIRED", "DUPLICATE_BLOCKED"}:
            break
        current = last.get("next_level")

    if last.get("status") in {"SUCCESS", "VERIFIED"} and last.get("current_level") == "L5":
        build = standard_build_runner("dca-spare01", execute=False)
        timeline.append(_event(incident_id, "L5", "STANDARD_BUILD_HEALTH_VALIDATE", "dca-spare01", build["status"], build, "Standard Build remains approval-gated", started))
        final_status = "VERIFIED" if build["status"] == "VERIFIED" else build["status"]
    else:
        final_status = last.get("status", "ESCALATION_REQUIRED")
    result = {"incident_id": incident_id, "failed_host": failed_host, "current_level": last.get("current_level", level), "attempted_levels": attempted, "status": final_status, "next_action": last.get("next_action"), "retry_count": last.get("retry_count", 0), "timeline_events": timeline, "execution_state": state, "error": last.get("error"), "escalation_reason": last.get("escalation_reason")}
    json.dumps(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incident-id", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--recovery-vars", required=True, type=Path)
    parser.add_argument("--incident-result", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        recovery_vars = json.loads(args.recovery_vars.read_text(encoding="utf-8"))
        incident = json.loads(args.incident_result.read_text(encoding="utf-8")) if args.incident_result else None
        result = run_workflow(args.incident_id, args.host, recovery_vars, execute=args.execute, incident_result=incident)
    except (OSError, ValueError, WorkflowError) as error:
        print(f"workflow_runner: {error}")
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in {"VERIFIED", "PLAN_ONLY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
