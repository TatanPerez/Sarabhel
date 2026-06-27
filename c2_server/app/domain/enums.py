"""Enumerations used across the application."""

from enum import Enum

class EventType(str, Enum):
    AGENT_REGISTERED = "agent_registered"
    COMMAND_DISPATCHED = "command_dispatched"
    COMMAND_COMPLETED = "command_completed"
    HEARTBEAT_RECEIVED = "heartbeat_received"
    LOG_ENTRY = "log_entry"