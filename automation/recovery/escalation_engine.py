#!/usr/bin/env python3
"""Bounded, resumable escalation decisions for incident recovery."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from typing import Any, Callable


LEVELS = {
    "L1": {"action": "SERVICE_REPAIR", "timeout_seconds": 120, "max_retries": 1},
    "L2": {"action": "OS_NETWORK_REPAIR", "timeout_seconds": 180, "max_retries": 1},
    "L3": {"action": "NODE_ISOLATION", "timeout_seconds": 60, "max_retries": 0},
    "L4": {"action": "SPARE_ACTIVATION", "timeout_seconds": 300, "max_retries": 0},
    "L5": {"action": "PXE_REBUILD", "timeout_seconds": 1800, "max_retries": 0},
}
RULE_START_LEVEL = {"SVC-HTTP-01": "L1", "NET-ROUTE-01": "L2"}
NEXT_LEVEL = {"L1": "L2", "L2": "L3", "L3": "L4", "L4": "L5", "L5": None}


class EscalationError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_escalation(
    incident_id: str,
    failed_host: str,
    rule_id: str,
    *,
    current_level: str | None = None,
    attempted_levels: list[str] | None = None,
    retry_count: int = 0,
    execution_state: dict[str, Any] | None = None,
    adapters: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
    reason: str = "Software recovery failed or verification did not pass",
) -> dict[str, Any]:
    if not isinstance(incident_id, str) or not incident_id.strip():
        raise EscalationError("incident_id must be a non-empty string")
    if not isinstance(failed_host, str) or not failed_host.strip():
        raise EscalationError("failed_host must be a non-empty string")
    level = current_level or RULE_START_LEVEL.get(rule_id)
    if level not in LEVELS:
        raise EscalationError(f"Unsupported escalation level or rule: {level or rule_id!r}")
    attempted = list(attempted_levels or [])
    if any(item not in LEVELS for item in attempted):
        raise EscalationError("attempted_levels contains an unsupported level")
    policy = LEVELS[level]
    key = f"{incident_id}:{failed_host}:{level}:{policy['action']}"
    state = execution_state if execution_state is not None else {}
    started = time.monotonic()
    payload = {
        "incident_id": incident_id,
        "failed_host": failed_host,
        "level": level,
        "action": policy["action"],
        "timeout_seconds": policy["timeout_seconds"],
        "idempotency_key": key,
    }

    if key in state:
        status = "DUPLICATE_BLOCKED"
        detail: dict[str, Any] = state[key]
    elif level in {"L3", "L4", "L5"} and not (adapters or {}).get(policy["action"]):
        status = "MANUAL_REQUIRED"
        detail = {"action_payload": payload}
        state[key] = {"status": status}
    else:
        adapter = (adapters or {}).get(policy["action"])
        if adapter is None:
            status = "PLAN_ONLY"
            detail = {"action_payload": payload}
        else:
            attempt = 0
            detail = {}
            status = "ERROR"
            while attempt <= policy["max_retries"]:
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(adapter, payload)
                try:
                    detail = future.result(timeout=policy["timeout_seconds"])
                    status = str(detail.get("status", "ERROR"))
                except FutureTimeoutError:
                    future.cancel()
                    detail = {"error": f"Action timed out after {policy['timeout_seconds']} seconds"}
                    status = "TIMEOUT"
                except Exception as error:  # Adapter boundary is deliberately contained.
                    detail = {"error": str(error)}
                    status = "ERROR"
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)
                if status in {"VERIFIED", "SUCCESS"}:
                    break
                attempt += 1
            retry_count = attempt if attempt <= policy["max_retries"] else policy["max_retries"]
            state[key] = {"status": status, "result": detail}

    if level not in attempted:
        attempted.append(level)
    success = status == "VERIFIED"
    next_level = None if success else NEXT_LEVEL[level]
    event = {
        "incident_id": incident_id,
        "timestamp": _now(),
        "level": level,
        "action": policy["action"],
        "target_host": failed_host,
        "status": status,
        "result": detail,
        "detail": reason,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
    }
    result = {
        "incident_id": incident_id,
        "failed_host": failed_host,
        "current_level": level,
        "attempted_levels": attempted,
        "status": "VERIFIED" if success else status,
        "next_action": LEVELS[next_level]["action"] if next_level else None,
        "next_level": next_level,
        "retry_count": retry_count,
        "max_retries": policy["max_retries"],
        "timeout_seconds": policy["timeout_seconds"],
        "idempotency_key": key,
        "timeline_events": [event],
        "escalation_reason": None if success else reason,
        "error": detail.get("error") if isinstance(detail, dict) else None,
    }
    json.dumps(result)
    return result
