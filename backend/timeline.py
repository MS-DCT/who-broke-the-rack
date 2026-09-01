import json
from datetime import datetime

from models import Incident, Evidence, Action, Diagnosis


def get_incident_timeline(
    db,
    incident_id
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

    timeline = []

    # Incident 시작 이벤트
    timeline.append(
        {
            "type": "INCIDENT",
            "name": "INCIDENT_CREATED",
            "status": incident.status,
            "details": (
                f"Incident created for "
                f"{incident.server_id}"
            ),
            "timestamp": incident.started_at
        }
    )

    # Evidence 이벤트
    evidence_list = (
        db.query(Evidence)
        .filter(
            Evidence.incident_id == incident_id
        )
        .all()
    )

    for evidence in evidence_list:
        timeline.append(
            {
                "type": "EVIDENCE",
                "layer": evidence.layer,
                "name": evidence.check_name,
                "status": evidence.result,
                "severity": evidence.severity,
                "details": evidence.details,
                "timestamp": evidence.timestamp
            }
        )

    # Diagnosis 이벤트
    diagnosis_list = (
        db.query(Diagnosis)
        .filter(
            Diagnosis.incident_id == incident_id
        )
        .all()
    )

    for diagnosis in diagnosis_list:
        timeline.append(
            {
                "type": "DIAGNOSIS",
                "name": diagnosis.root_cause,
                "status": diagnosis.severity,
                "details": (
                    f"Rule: {diagnosis.rule_id} / "
                    f"Recommended Action: "
                    f"{diagnosis.recommended_action}"
                ),
                "timestamp": diagnosis.timestamp
            }
        )

    # Recovery / Verification 이벤트
    action_list = (
        db.query(Action)
        .filter(
            Action.incident_id == incident_id
        )
        .all()
    )

    for action in action_list:
        try:
            payload = (
                json.loads(action.details)
                if isinstance(action.details, str)
                else {}
            )
        except (json.JSONDecodeError, TypeError):
            payload = {}

        mode = payload.get("mode", "UNKNOWN")
        result = payload.get(
            "result",
            action.status
        )
        recovery_action = payload.get(
            "action",
            action.action_type
        )

        timeline.append(
            {
                "type": "RECOVERY",
                "name": recovery_action,
                "status": result,
                "details": (
                    f"Mode: {mode} / "
                    f"Action: {recovery_action}"
                ),
                "timestamp": action.timestamp
            }
        )

        verification_status = payload.get(
            "verification_status"
        )

        if (
            mode != "PLAN_ONLY"
            and verification_status
        ):
            timeline.append(
                {
                    "type": "VERIFICATION",
                    "name": "RECOVERY_VERIFICATION",
                    "status": verification_status,
                    "details": (
                        f"{recovery_action} verification result"
                    ),
                    "timestamp": action.timestamp
                }
            )

    if (
        incident.status == "CLOSED"
        and incident.ended_at is not None
    ):
        timeline.append(
            {
                "type": "INCIDENT",
                "name": "CASE_CLOSED",
                "status": "CLOSED",
                "details": (
                    "Recovery and verification completed successfully"
                ),
                "timestamp": incident.ended_at
            }
        )

    timeline.sort(
        key=lambda item: (
            item["timestamp"]
            if item["timestamp"] is not None
            else datetime.min
        )
    )

    return {
        "incident_id": incident.incident_id,
        "server_id": incident.server_id,
        "status": incident.status,
        "root_cause": incident.root_cause,
        "event_count": len(timeline),
        "timeline": timeline
    }
