"""Domain entities representing core business objects."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class CommandStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    COMPLETED = "completed"
    FAILED = "failed"


class CommandType(str, Enum):
    SYSTEM_INFO = "system_info"
    FILE_OP = "file_op"
    NET_TOOL = "net_tool"


class EventTopic(str, Enum):
    REGISTER = "c2/register"
    COMMAND = "c2/commands/{agent_id}"
    RESULT = "c2/results/{agent_id}"
    HEARTBEAT = "c2/heartbeat/{agent_id}"
    LOG = "c2/logs/{source}"


@dataclass(frozen=True)
class Agent:
    agent_id: str
    capabilities: list[str] = field(default_factory=list)
    last_seen: Optional[datetime] = None
    registered_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class Command:
    agent_id: str
    command_type: CommandType
    id: int | None = None
    args: dict = field(default_factory=dict)
    status: CommandStatus = CommandStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass(frozen=True)
class Result:
    command_id: int
    agent_id: str
    id: int | None = None
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
