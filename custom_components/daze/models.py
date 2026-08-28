"""Data models for the Daze Wallbox integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pydaze import RechargeSession, SocketRemoteInfo


@dataclass
class SessionComputedFields:
    """Derived session sensor values computed by the coordinator."""

    last_session_energy: float | None = None
    last_session_duration: float | None = None
    last_session_cost: float | None = None
    last_session_start: datetime | None = None
    last_session_end: datetime | None = None
    last_session_average_power: float | None = None
    last_session_charge_time: str | None = None
    last_session_currency: str | None = None
    last_session_currency_symbol: str | None = None
    lifetime_energy: float = 0.0
    total_sessions: int = 0


@dataclass
class DazeCoordinatorData:
    """Typed coordinator data combining socket info and session data."""

    socket: SocketRemoteInfo
    sessions: list[RechargeSession] = field(default_factory=list)
    session_fields: SessionComputedFields = field(
        default_factory=SessionComputedFields
    )
