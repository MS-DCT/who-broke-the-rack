import json
from pathlib import Path
from datetime import datetime

from database import SessionLocal
from models import Incident, Evidence


JSON_PATH = Path("../evidence/day2/diagnostic/dca-target02.json")

INCIDENT_ID = "DAY2-207"
SERVER_ID = "server-207"


def convert_result(status):
    """
    B Diagnostic 결과값을 그대로 사용
    PASS / FAIL / WARN / UNKNOWN / SKIP
    """
    status = status.upper()

    if status in ["PASS", "FAIL", "WARN", "UNKNOWN", "SKIP"]:
        return status

    return "UNKNOWN"


def convert_severity(status):
    """
    B JSON에는 severity가 없으므로 status 기준으로 생성
    """
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
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now()


def main():
    if not JSON_PATH.exists():
        print(f"[ERROR] JSON 파일을 찾을 수 없음: {JSON_PATH}")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()

    try:
        # Incident 생성 또는 기존 Incident 상태 갱신
        incident = (
            db.query(Incident)
            .filter(Incident.incident_id == INCIDENT_ID)
            .first()
        )

        if incident is None:
            incident = Incident(
                incident_id=INCIDENT_ID,
                server_id=SERVER_ID,
                status="INVESTIGATING"
            )

            db.add(incident)
            db.commit()

            print(f"[CREATE] Incident 생성: {INCIDENT_ID}")

        else:
            incident.status = "INVESTIGATING"
            db.commit()

            print(f"[UPDATE] Incident 갱신: {INCIDENT_ID}")

        # 이전 DAY2-207 Evidence 제거
        deleted = (
            db.query(Evidence)
            .filter(
                Evidence.incident_id == INCIDENT_ID,
                Evidence.server_id == SERVER_ID
            )
            .delete(synchronize_session=False)
        )

        db.commit()

        print(f"[DELETE] 기존 Evidence 제거: {deleted}개")

        generated_at = parse_timestamp(data.get("generated_at"))

        added = 0

        for category in data.get("results", []):
            layer = category.get("category", "UNKNOWN").upper()

            for check in category.get("checks", []):
                check_name = check.get("name", "unknown_check")
                original_status = check.get("status", "UNKNOWN")

                result = convert_result(original_status)
                severity = convert_severity(original_status)
                details = check.get("detail", "")

                evidence = Evidence(
                    incident_id=INCIDENT_ID,
                    server_id=SERVER_ID,
                    layer=layer,
                    check_name=check_name,
                    result=result,
                    severity=severity,
                    details=details,
                    timestamp=generated_at
                )

                db.add(evidence)

                print(
                    f"[ADD] {layer:<8} "
                    f"{check_name:<25} "
                    f"{result}"
                )

                added += 1

        db.commit()

        print()
        print("======================================")
        print(" Day 2 Evidence Import 완료")
        print("======================================")
        print(f"Incident : {INCIDENT_ID}")
        print(f"Server   : {SERVER_ID}")
        print(f"Hostname : {data.get('host')}")
        print(f"추가     : {added}")
        print(f"상태     : {data.get('status')}")
        print("======================================")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Import 실패: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
