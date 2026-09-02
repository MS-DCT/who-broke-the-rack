import json
from datetime import datetime
from pathlib import Path

from models import Incident, Action


REPO_ROOT = Path(__file__).resolve().parents[1]


def save_physical_recovery(
    db,
    incident_id,
    evidence_path=None,
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

    # Physical Recovery는 Target #3 장애 Incident에 연결
    if incident.server_id != "server-207":
        raise ValueError(
            "Physical Recovery 대상 Incident는 "
            "server-207이어야 합니다."
        )

    if evidence_path is None:
        evidence_path = (
            REPO_ROOT
            / "evidence"
            / "day7"
            / "physical_recovery"
            / "DAY7-PHYSICAL-RECOVERY-01.json"
        )
    else:
        evidence_path = Path(evidence_path)

    if not evidence_path.exists():
        raise ValueError(
            f"Physical Recovery Evidence가 없습니다: "
            f"{evidence_path}"
        )

    with evidence_path.open(
        "r",
        encoding="utf-8"
    ) as f:
        payload = json.load(f)

    if payload.get("category") != "physical_recovery":
        raise ValueError(
            "category가 physical_recovery가 아닙니다."
        )

    if payload.get("server_id") != "server-208":
        raise ValueError(
            "Spare server_id가 server-208이 아닙니다."
        )

    if payload.get("host") != "dca-spare01":
        raise ValueError(
            "Spare host가 dca-spare01이 아닙니다."
        )

    evidence = payload.get("evidence")

    if not isinstance(evidence, dict):
        raise ValueError(
            "Physical Recovery evidence 형식이 올바르지 않습니다."
        )

    ready = evidence.get(
        "physical_recovery_ready",
        {}
    )

    if (
        ready.get("result") != "PASS"
        or ready.get("value") != "READY"
    ):
        raise ValueError(
            "Physical Recovery가 READY 상태가 아닙니다."
        )

    # 동일 Incident에 Physical Recovery Action 중복 저장 방지
    existing_action = (
        db.query(Action)
        .filter(
            Action.incident_id == incident_id,
            Action.action_type == "physical_recovery",
        )
        .first()
    )

    if existing_action is not None:
        raise ValueError(
            f"Physical Recovery Action이 이미 존재합니다: "
            f"{incident_id}"
        )

    # 원본 Physical Recovery 공통 포맷 유지 +
    # 기존 Timeline이 읽을 수 있는 Action 메타데이터 추가
    action_payload = dict(payload)

    action_payload["incident_id"] = incident_id
    action_payload["action"] = "physical_recovery"
    action_payload["mode"] = "PHYSICAL"
    action_payload["result"] = "READY"

    action = Action(
        incident_id=incident_id,
        action_type="physical_recovery",
        status="READY",
        details=json.dumps(
            action_payload,
            ensure_ascii=False
        ),
        timestamp=datetime.now(),
    )

    db.add(action)

    # Software Recovery 범위를 넘어 Physical Recovery로
    # Escalation된 Incident임을 기존 상태값으로 표현
    incident.status = "ESCALATED"

    db.commit()
    db.refresh(action)

    return {
        "incident_id": incident.incident_id,
        "target_server_id": incident.server_id,
        "target_host": "dca-target02",
        "status": incident.status,
        "action_type": action.action_type,
        "action_status": action.status,
        "spare_server_id": payload.get("server_id"),
        "spare_host": payload.get("host"),
        "physical_recovery_ready": ready,
        "pxe_provisioning_ready": evidence.get(
            "pxe_provisioning_ready"
        ),
    }
