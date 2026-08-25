import json
from pathlib import Path
from datetime import datetime

from database import SessionLocal
from models import Incident, Evidence


DIAGNOSTIC_JSON_PATH = Path("../evidence/day2/diagnostic/dca-target02.json")
HARDWARE_JSON_PATH = Path("../evidence/day2/hardware/dca-target02.json")

INCIDENT_ID = "DAY2-207"
SERVER_ID = "server-207"

def convert_result(status):
    status = status.upper()

    if status in ["PASS", "FAIL", "WARN", "UNKNOWN", "SKIP"]:
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


def add_check(
    db,
    layer,
    check,
    timestamp
):
    check_name = check.get(
        "name",
        "unknown_check"
    )

    original_status = check.get(
        "status",
        "UNKNOWN"
    )

    result = convert_result(
        original_status
    )

    severity = convert_severity(
        original_status
    )

    details = check.get(
        "detail",
        ""
    )

    evidence = Evidence(
        incident_id=INCIDENT_ID,
        server_id=SERVER_ID,
        layer=layer.upper(),
        check_name=check_name,
        result=result,
        severity=severity,
        details=details,
        timestamp=timestamp
    )

    db.add(evidence)

    print(
        f"[ADD] {layer.upper():<10} "
        f"{check_name:<25} "
        f"{result}"
    )


def main():
    if not DIAGNOSTIC_JSON_PATH.exists():
        print(
            "[ERROR] Diagnostic JSON 파일을 찾을 수 없음:",
            DIAGNOSTIC_JSON_PATH
        )
        return

    if not HARDWARE_JSON_PATH.exists():
        print(
            "[ERROR] Hardware JSON 파일을 찾을 수 없음:",
            HARDWARE_JSON_PATH
        )
        return

    with open(
        DIAGNOSTIC_JSON_PATH,
        "r",
        encoding="utf-8"
    ) as f:
        diagnostic_data = json.load(f)

    with open(
        HARDWARE_JSON_PATH,
        "r",
        encoding="utf-8"
    ) as f:
        hardware_data = json.load(f)

    db = SessionLocal()

    try:
        incident = (
            db.query(Incident)
            .filter(
                Incident.incident_id == INCIDENT_ID
            )
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

            print(
                f"[CREATE] Incident 생성: "
                f"{INCIDENT_ID}"
            )

        else:
            incident.status = "INVESTIGATING"
            db.commit()

            print(
                f"[UPDATE] Incident 갱신: "
                f"{INCIDENT_ID}"
            )

        deleted = (
            db.query(Evidence)
            .filter(
                Evidence.incident_id == INCIDENT_ID,
                Evidence.server_id == SERVER_ID
            )
            .delete(
                synchronize_session=False
            )
        )

        db.commit()

        print(
            f"[DELETE] 기존 Evidence 제거: "
            f"{deleted}개"
        )

        added = 0

        # =========================
        # Hardware Evidence
        # =========================

        hardware_timestamp = parse_timestamp(
            hardware_data.get(
                "generated_at"
            )
        )

        hardware_layer = hardware_data.get(
            "category",
            "hardware"
        )

        for check in hardware_data.get(
            "checks",
            []
        ):
            add_check(
                db,
                hardware_layer,
                check,
                hardware_timestamp
            )

            added += 1

        # =========================
        # Network / OS / Service
        # =========================

        diagnostic_timestamp = parse_timestamp(
            diagnostic_data.get(
                "generated_at"
            )
        )

        for category in diagnostic_data.get(
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
                add_check(
                    db,
                    layer,
                    check,
                    diagnostic_timestamp
                )

                added += 1

        db.commit()

        print()
        print(
            "======================================"
        )
        print(
            " Day 2 Evidence Import 완료"
        )
        print(
            "======================================"
        )
        print(
            f"Incident : {INCIDENT_ID}"
        )
        print(
            f"Server   : {SERVER_ID}"
        )
        print(
            f"Hostname : "
            f"{diagnostic_data.get('host')}"
        )
        print(
            f"Hardware : "
            f"{len(hardware_data.get('checks', []))}"
        )
        print(
            f"Total    : {added}"
        )
        print(
            "======================================"
        )

    except Exception as e:
        db.rollback()

        print(
            f"[ERROR] Import 실패: {e}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
