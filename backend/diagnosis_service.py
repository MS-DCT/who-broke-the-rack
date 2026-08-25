import json
from datetime import datetime, timezone

from models import Incident, Evidence, Diagnosis


def parse_timestamp(value):
    if not value:
        return datetime.now()

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        # SQLite DateTime과 Timeline 정렬을 위해
        # UTC naive datetime으로 통일
        if parsed.tzinfo is not None:
            parsed = (
                parsed.astimezone(timezone.utc)
                .replace(tzinfo=None)
            )

        return parsed

    except (ValueError, TypeError):
        return datetime.now()


def severity_from_result(result):
    result = (result or "UNKNOWN").upper()

    if result == "PASS":
        return "INFO"

    if result == "FAIL":
        return "HIGH"

    if result == "WARN":
        return "WARN"

    if result == "SKIP":
        return "INFO"

    return "WARN"


def build_details(item):
    parts = []

    value = item.get("value")
    detail = item.get("detail")
    source = item.get("source")

    if value is not None:
        parts.append(f"Value: {value}")

    if detail:
        parts.append(f"Detail: {detail}")

    if source:
        parts.append(f"Source: {source}")

    return " | ".join(parts)


def save_incident_result(db, result):
    incident_id = result.get("incident_id")

    if not incident_id:
        raise ValueError(
            "B 결과에 incident_id가 없습니다."
        )

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

    # 같은 Incident 결과가 이미 저장된 경우
    # 기존 Timeline을 몰래 삭제하지 않고 중단
    existing_diagnosis = (
        db.query(Diagnosis)
        .filter(
            Diagnosis.incident_id == incident_id
        )
        .first()
    )

    if existing_diagnosis is not None:
        raise ValueError(
            f"이미 진단 결과가 저장된 Incident입니다: {incident_id}"
        )

    evidence_count = 0

    for item in result.get("evidence", []):
        evidence_result = (
            item.get("result")
            or "UNKNOWN"
        ).upper()

        severity = item.get("severity")

        if not severity:
            severity = severity_from_result(
                evidence_result
            )

        evidence = Evidence(
            incident_id=incident_id,
            server_id=incident.server_id,
            layer=(
                item.get("layer")
                or "UNKNOWN"
            ).upper(),
            check_name=(
                item.get("check_name")
                or "unknown_check"
            ),
            result=evidence_result,
            severity=severity,
            details=build_details(item),
            timestamp=parse_timestamp(
                item.get("timestamp")
            )
        )

        db.add(evidence)
        evidence_count += 1

    diagnosis_data = (
        result.get("diagnosis")
        or {}
    )

    diagnosis = None

    if diagnosis_data:
        diagnosis = Diagnosis(
            incident_id=incident_id,

            rule_id=diagnosis_data.get(
                "rule_id"
            ),

            root_cause=diagnosis_data.get(
                "root_cause"
            ),

            matched_evidence=json.dumps(
                diagnosis_data.get(
                    "matched_evidence",
                    []
                ),
                ensure_ascii=False
            ),

            recommended_action=(
                diagnosis_data.get(
                    "recommended_action"
                )
            ),

            severity=diagnosis_data.get(
                "severity"
            ),

            diagnosis_status=(
                diagnosis_data.get(
                    "diagnosis_status"
                )
            ),

            evidence_gaps=json.dumps(
                diagnosis_data.get(
                    "evidence_gaps",
                    []
                ),
                ensure_ascii=False
            ),

            timestamp=parse_timestamp(
                diagnosis_data.get(
                    "timestamp"
                )
            )
        )

        db.add(diagnosis)

        incident.root_cause = (
            diagnosis_data.get(
                "root_cause"
            )
        )

        # B가 명시적으로 status를 주는 경우에만 변경
        if diagnosis_data.get(
            "diagnosis_status"
        ):
            incident.status = (
                diagnosis_data[
                    "diagnosis_status"
                ]
            )

    db.commit()

    return {
        "incident_id": incident_id,
        "server_id": incident.server_id,
        "host": result.get("host"),
        "evidence_count": evidence_count,
        "root_cause": incident.root_cause,
        "diagnosis_saved": (
            diagnosis is not None
        )
    }
