import json
import sys
from datetime import datetime
from pathlib import Path

from models import Incident, Diagnosis, Action
from incident_controller import SERVER_HOST_MAP


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.recovery.recovery_runner import (
    run_recovery,
    RecoveryRunnerError,
)


def run_incident_recovery(
    db,
    incident_id,
    recovery_vars,
    execute=False,
):
    incident = (
        db.query(Incident)
        .filter(
            Incident.incident_id == incident_id
        )
        .first()
    )

    if incident is None:
        raise ValueError(
            f"Incident를 찾을 수 없습니다: {incident_id}"
        )

    diagnosis = (
        db.query(Diagnosis)
        .filter(
            Diagnosis.incident_id == incident_id
        )
        .order_by(Diagnosis.id.desc())
        .first()
    )

    if diagnosis is None:
        raise ValueError(
            f"Diagnosis 결과가 없습니다: {incident_id}"
        )

    host = SERVER_HOST_MAP.get(
        incident.server_id
    )

    if host is None:
        raise ValueError(
            f"Host를 찾을 수 없습니다: {incident.server_id}"
        )

    diagnosis_payload = {
        "incident_id": incident_id,
        "host": host,
        "rule_id": diagnosis.rule_id,
        "recommended_action": diagnosis.recommended_action,
        "diagnosis_status": diagnosis.diagnosis_status,
    }

    result = run_recovery(
        incident_id=incident_id,
        host=host,
        diagnosis=diagnosis_payload,
        recovery_vars=recovery_vars,
        execute=execute,
    )

    action = Action(
        incident_id=incident_id,
        action_type=result.get(
            "action",
            "network_recovery"
        ),
        status=result.get(
            "result",
            "UNKNOWN"
        ),
        details=json.dumps(
            result,
            ensure_ascii=False
        ),
        timestamp=datetime.now(),
    )

    db.add(action)

    if execute:
        if (
            result.get("result") == "SUCCESS"
            and result.get(
                "verification_status"
            ) == "VERIFIED"
        ):
            incident.status = "CLOSED"
            incident.ended_at = datetime.now()
        else:
            incident.status = "ESCALATED"
    else:
        incident.status = "ROOT_CAUSE_FOUND"

    db.commit()

    return {
        "incident_id": incident_id,
        "server_id": incident.server_id,
        "host": host,
        "status": incident.status,
        "recovery": result,
    }
