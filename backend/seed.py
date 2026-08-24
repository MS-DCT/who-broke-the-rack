from database import SessionLocal
import models

db = SessionLocal()

try:
    incident_id = "MOCK-001"

    # Mock Incident 생성
    incident = (
        db.query(models.Incident)
        .filter(models.Incident.incident_id == incident_id)
        .first()
    )

    if not incident:
        incident = models.Incident(
            incident_id=incident_id,
            server_id="server-207",
            status="INVESTIGATING",
            root_cause=None
        )
        db.add(incident)
        db.commit()

    # 같은 Mock Evidence가 없다면 생성
    existing = (
        db.query(models.Evidence)
        .filter(models.Evidence.incident_id == incident_id)
        .first()
    )

    if not existing:
        evidence_list = [
            models.Evidence(
                incident_id=incident_id,
                server_id="server-207",
                layer="HARDWARE",
                check_name="system_health",
                result="PASS",
                severity="INFO",
                details="[MOCK] Hardware health 정상"
            ),
            models.Evidence(
                incident_id=incident_id,
                server_id="server-207",
                layer="POST_BOOT",
                check_name="boot_status",
                result="PASS",
                severity="INFO",
                details="[MOCK] POST 및 OS Boot 정상"
            ),
            models.Evidence(
                incident_id=incident_id,
                server_id="server-207",
                layer="NETWORK",
                check_name="gateway_reachability",
                result="FAIL",
                severity="HIGH",
                details="[MOCK] Gateway 연결 실패"
            ),
            models.Evidence(
                incident_id=incident_id,
                server_id="server-207",
                layer="OS",
                check_name="ssh_reachability",
                result="UNKNOWN",
                severity="WARN",
                details="[MOCK] Network 문제로 SSH 확인 불가"
            )
        ]

        db.add_all(evidence_list)
        db.commit()

    print("Mock Incident / Evidence 생성 완료")

finally:
    db.close()
