"""SQLAlchemy ORM models that map to the domain entities.
These are used by the repository layer and are kept separate from the
pure domain dataclasses defined in ``app/domain/entities.py``.
"""

from datetime import datetime
from typing import List

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship

from .Base import Base

from ..domain.entities import CommandStatus, CommandType


class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, unique=True, index=True, nullable=False)
    capabilities = Column(JSON, nullable=False)
    last_seen = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # relationships
    commands = relationship("CommandModel", back_populates="agent", cascade="all, delete-orphan")
    results = relationship("ResultModel", back_populates="agent", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AgentModel(agent_id={self.agent_id})>"


class CommandModel(Base):
    __tablename__ = "commands"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False, index=True)
    command_type = Column(SAEnum(CommandType), nullable=False)
    args = Column(JSON, default=dict, nullable=False)
    status = Column(SAEnum(CommandStatus), default=CommandStatus.QUEUED, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    # relationship back to agent
    agent = relationship("AgentModel", back_populates="commands")
    # one‑to‑many result (normally one result per command)
    result = relationship("ResultModel", uselist=False, back_populates="command", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CommandModel(id={self.id}, type={self.command_type})>"


class ResultModel(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    command_id = Column(Integer, ForeignKey("commands.id"), nullable=False, unique=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    stdout = Column(Text, default="", nullable=False)
    stderr = Column(Text, default="", nullable=False)
    exit_code = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # relationships
    command = relationship("CommandModel", back_populates="result")
    agent = relationship("AgentModel", back_populates="results")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ResultModel(id={self.id}, command_id={self.command_id})>"
