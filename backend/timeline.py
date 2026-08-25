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


    # Action 이벤트
    action_list = (
        db.query(Action)
        .filter(
            Action.incident_id == incident_id
        )
        .all()
    )

    for action in action_list:
        timeline.append(
            {
                "type": "ACTION",
                "name": action.action_type,
                "status": action.status,
                "details": action.details,
                "timestamp": action.timestamp
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
