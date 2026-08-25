from datetime import datetime
from uuid import uuid4

from models import Incident


SERVER_HOST_MAP = {
    "server-205": "dca-target01",
    "server-206": "dca-mgmt01",
    "server-207": "dca-target02",
    "server-208": "dca-spare01",
}


def create_incident(db, server_id):
    host = SERVER_HOST_MAP.get(server_id)

    if host is None:
        raise ValueError(
            f"지원하지 않는 server_id입니다: {server_id}"
        )

    now = datetime.now()

    incident_id = (
        f"INC-"
        f"{now.strftime('%Y%m%d-%H%M%S')}-"
        f"{uuid4().hex[:4].upper()}"
    )

    incident = Incident(
        incident_id=incident_id,
        server_id=server_id,
        status="DETECTED"
    )

    db.add(incident)
    db.commit()
    db.refresh(incident)

    return {
        "incident_id": incident.incident_id,
        "server_id": server_id,
        "host": host,
        "status": incident.status,
        "started_at": incident.started_at
    }
