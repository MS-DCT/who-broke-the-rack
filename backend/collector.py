import json
from pathlib import Path
from datetime import datetime

from models import Incident, Evidence


BASE_DIR = Path(__file__).resolve().parent.parent

DIAGNOSTIC_PATH = (
    BASE_DIR
    / "evidence"
    / "day2"
    / "diagnostic"
    / "dca-target02.json"
)

HARDWARE_PATH = (
    BASE_DIR
    / "evidence"
    / "day2"
    / "hardware"
    / "dca-target02.json"
)


def convert_result(status):
    status = status.upper()

    if status in [
        "PASS",
        "FAIL",
        "WARN",
        "UNKNOWN",
        "SKIP"
    ]:
        return status

    return "UNKNOWN"


def convert_severity(status):
    status = status.upper()

    if status == "PASS":
        return "INFO"
    if status == "FAIL":
        return "HIGH"
    if status == "WARN":
        return "WARN"
    if status == "SKIP":
        return "INFO"

    return "WARN"


def parse_timestamp(value):
    if not value:
        return datetime.now()

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return datetime.now()


def add_evidence(
    db,
    incident_id,
    server_id,
    layer,
    check,
    timestamp
):
    status = check.get(
        "status",
        "UNKNOWN"
    )

    evidence = Evidence(
        incident_id=incident_id,
        server_id=server_id,
        layer=layer.upper(),
        check_name=check.get(
            "name",
            "unknown_check"
        ),
        result=convert_result(status),
        severity=convert_severity(status),
        details=check.get(
            "detail",
            ""
        ),
        timestamp=timestamp
    )

    db.add(evidence)


def collect_server_evidence(
    db,
    server_id
):
    if server_id != "server-207":
        raise ValueError(
            "현재 Collector는 server-207만 지원합니다."
        )

    with open(
        DIAGNOSTIC_PATH,
        "r",
        encoding="utf-8"
    ) as f:
        diagnostic = json.load(f)

    with open(
        HARDWARE_PATH,
        "r",
        encoding="utf-8"
    ) as f:
        hardware = json.load(f)

    incident_id = "DAY2-207"

    incident = (
        db.query(Incident)
        .filter(
            Incident.incident_id == incident_id
        )
        .first()
    )

    if incident is None:
        incident = Incident(
            incident_id=incident_id,
            server_id=server_id,
            status="INVESTIGATING"
        )
        db.add(incident)
    else:
        incident.status = "INVESTIGATING"

    db.query(Evidence).filter(
        Evidence.incident_id == incident_id,
        Evidence.server_id == server_id
    ).delete(
        synchronize_session=False
    )

    hardware_timestamp = parse_timestamp(
        hardware.get("generated_at")
    )

    hardware_count = 0

    for check in hardware.get(
        "checks",
        []
    ):
        add_evidence(
            db,
            incident_id,
            server_id,
            "HARDWARE",
            check,
            hardware_timestamp
        )

        hardware_count += 1

    diagnostic_timestamp = parse_timestamp(
        diagnostic.get("generated_at")
    )

    diagnostic_count = 0

    for category in diagnostic.get(
        "results",
        []
    ):
        layer = category.get(
            "category",
            "UNKNOWN"
        )

        for check in category.get(
            "checks",
            []
        ):
            add_evidence(
                db,
                incident_id,
                server_id,
                layer,
                check,
                diagnostic_timestamp
            )

            diagnostic_count += 1

    db.commit()

    return {
        "incident_id": incident_id,
        "server_id": server_id,
        "hardware": hardware_count,
        "diagnostic": diagnostic_count,
        "total": hardware_count + diagnostic_count,
        "status": "COLLECTED"
    }
