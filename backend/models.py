from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String, unique=True, index=True, nullable=False)
    server_id = Column(String, nullable=False)
    status = Column(String, default="DETECTED")
    root_cause = Column(Text, nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String, index=True, nullable=False)
    server_id = Column(String, nullable=False)
    layer = Column(String, nullable=False)
    check_name = Column(String, nullable=False)
    result = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())


class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String, index=True, nullable=False)
    action_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())
