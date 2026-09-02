from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, SessionLocal
import models
from collector import collect_server_evidence
from incident_controller import create_incident
from timeline import get_incident_timeline
from incident_workflow import (
    run_incident_workflow,
    IncidentRunnerError,
)
from recovery_service import (
    run_incident_recovery,
    RecoveryRunnerError,
)

# SQLite DB 및 테이블 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(title="WHO BROKE THE RACK API")

# React에서 FastAPI 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.100.206:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# DB 연결
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


servers = [
    {
        "server_id": "server-205",
        "hostname": "dca-target01",
        "role": "Target Server A",
        "ip": "192.168.100.205",
        "status": "UNKNOWN"
    },
    {
        "server_id": "server-206",
        "hostname": "dca-mgmt01",
        "role": "Management / Automation",
        "ip": "192.168.100.206",
        "status": "UNKNOWN"
    },
    {
        "server_id": "server-207",
        "hostname": "dca-target02",
        "role": "Target Server B",
        "ip": "192.168.100.207",
        "status": "UNKNOWN"
    },
    {
        "server_id": "server-208",
        "hostname": "dca-spare01",
        "role": "Spare / PXE Rebuild Target",
        "ip": "192.168.100.208",
        "status": "UNKNOWN"
    }
]


@app.get("/")
def root():
    return {
        "project": "WHO BROKE THE RACK",
        "status": "running"
    }


@app.get("/servers")
def get_servers():
    return {"servers": servers}


@app.get("/incidents")
def get_incidents(db: Session = Depends(get_db)):
    incidents = db.query(models.Incident).all()

    return {
        "incidents": [
            {
                "incident_id": i.incident_id,
                "server_id": i.server_id,
                "status": i.status,
                "root_cause": i.root_cause,
                "started_at": i.started_at,
                "ended_at": i.ended_at
            }
            for i in incidents
        ]
    }


@app.get("/evidence")
def get_evidence(db: Session = Depends(get_db)):
    evidence_list = db.query(models.Evidence).all()

    return {
        "evidence": [
            {
                "incident_id": e.incident_id,
                "server_id": e.server_id,
                "layer": e.layer,
                "check_name": e.check_name,
                "result": e.result,
                "severity": e.severity,
                "details": e.details,
                "timestamp": e.timestamp
            }
            for e in evidence_list
        ]
    }


@app.get("/actions")
def get_actions(db: Session = Depends(get_db)):
    actions = db.query(models.Action).all()

    return {
        "actions": [
            {
                "incident_id": a.incident_id,
                "action_type": a.action_type,
                "status": a.status,
                "details": a.details,
                "timestamp": a.timestamp
            }
            for a in actions
        ]
    }


@app.post("/collect/{server_id}")
def collect_evidence(
    server_id: str,
    db: Session = Depends(get_db)
):
    try:
        return collect_server_evidence(
            db,
            server_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/incidents/start/{server_id}")
def start_incident(
    server_id: str,
    db: Session = Depends(get_db)
):
    try:
        return create_incident(
            db,
            server_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/incidents/{incident_id}/timeline")
def incident_timeline(
    incident_id: str,
    db: Session = Depends(get_db)
):
    try:
        return get_incident_timeline(
            db,
            incident_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/incidents/{incident_id}/diagnose")
def diagnose_incident(
    incident_id: str,
    db: Session = Depends(get_db)
):
    try:
        return run_incident_workflow(
            db,
            incident_id
        )

    except ValueError as e:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except IncidentRunnerError as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/incidents/{incident_id}/recovery")
def recover_incident(
    incident_id: str,
    payload: dict,
    db: Session = Depends(get_db)
):
    recovery_vars = payload.get("recovery_vars")
    execute = payload.get("execute", False)

    if not isinstance(recovery_vars, dict):
        raise HTTPException(
            status_code=400,
            detail="recovery_vars가 필요합니다."
        )

    if not isinstance(execute, bool):
        raise HTTPException(
            status_code=400,
            detail="execute는 boolean이어야 합니다."
        )

    try:
        return run_incident_recovery(
            db=db,
            incident_id=incident_id,
            recovery_vars=recovery_vars,
            execute=execute,
        )

    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except RecoveryRunnerError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# Day 6 - Escalation Status
# =========================

@app.get("/incidents/{incident_id}/escalation")
def get_escalation_status(
    incident_id: str,
    db: Session = Depends(get_db)
):
    incident = (
        db.query(models.Incident)
        .filter(
            models.Incident.incident_id == incident_id
        )
        .first()
    )

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident를 찾을 수 없습니다: {incident_id}"
        )

    return {
        "incident_id": incident.incident_id,
        "server_id": incident.server_id,
        "incident_status": incident.status,
        "escalation_level": incident.escalation_level,
        "escalation_status": incident.escalation_status,
    }


@app.post("/incidents/{incident_id}/escalation")
def update_escalation_status(
    incident_id: str,
    payload: dict,
    db: Session = Depends(get_db)
):
    incident = (
        db.query(models.Incident)
        .filter(
            models.Incident.incident_id == incident_id
        )
        .first()
    )

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident를 찾을 수 없습니다: {incident_id}"
        )

    level = payload.get("level")
    status = payload.get("status")

    allowed_levels = {
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
    }

    allowed_statuses = {
        "SOFTWARE_RECOVERY_FAILED",
        "ESCALATION_REQUIRED",
        "SPARE_ACTIVATING",
        "PXE",
        "CONFIGURING",
        "READY",
    }

    if level is not None and level not in allowed_levels:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 escalation level: {level}"
        )

    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 escalation status: {status}"
        )

    incident.escalation_level = level
    incident.escalation_status = status

    if status == "ESCALATION_REQUIRED":
        incident.status = "ESCALATED"

    db.commit()
    db.refresh(incident)

    return {
        "incident_id": incident.incident_id,
        "server_id": incident.server_id,
        "incident_status": incident.status,
        "escalation_level": incident.escalation_level,
        "escalation_status": incident.escalation_status,
    }
