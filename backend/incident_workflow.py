import sys
from pathlib import Path

from models import Incident, Diagnosis
from incident_controller import SERVER_HOST_MAP
from diagnosis_service import save_incident_result


# backend에서 실행해도 repo root의 automation 패키지를 찾도록 설정
REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from automation.diagnosis.incident_runner import (
    run_incident,
    IncidentRunnerError,
)


def run_incident_workflow(
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

    # 이미 진단된 Incident 재실행 방지
    existing_diagnosis = (
        db.query(Diagnosis)
        .filter(
            Diagnosis.incident_id == incident_id
        )
        .first()
    )

    if existing_diagnosis is not None:
        raise ValueError(
            f"이미 진단된 Incident입니다: {incident_id}"
        )

    host = SERVER_HOST_MAP.get(
        incident.server_id
    )

    if host is None:
        raise ValueError(
            f"대상 Host를 찾을 수 없습니다: "
            f"{incident.server_id}"
        )

    incident_started_at = None

    if incident.started_at is not None:
        incident_started_at = (
            incident.started_at.isoformat()
        )

    # B Diagnosis Engine 실행
    result = run_incident(
        incident_id=incident_id,
        host=host,
        incident_started_at=incident_started_at
    )

    # C DB에 Evidence + Diagnosis 저장
    saved = save_incident_result(
        db,
        result
    )

    return {
        "incident_id": incident_id,
        "server_id": incident.server_id,
        "host": host,
        "evidence_count": saved[
            "evidence_count"
        ],
        "root_cause": saved[
            "root_cause"
        ],
        "diagnosis_saved": saved[
            "diagnosis_saved"
        ],
        "diagnosis": result.get(
            "diagnosis"
        )
    }
