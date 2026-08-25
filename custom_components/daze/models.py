"""Data models for the Daze Wallbox integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ------------------------------------------------------------------
# Response models — GET endpoints
# ------------------------------------------------------------------


@dataclass
class Network:
    """A network (installation) from the Daze API."""

    uid: str
    name: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Network:
        """Create a Network from the raw API response dict."""
        return cls(
            uid=str(data.get("uid", "")),
            name=data.get("name"),
            raw=data,
        )


@dataclass
class Evse:
    """An EVSE (charger) from the Daze API."""

    evse_name: str | None = None
    serial_number: str | None = None
    device_profile: str | None = None
    firmware_version: str | None = None
    software_version: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evse:
        """Create an Evse from the raw API response dict."""
        return cls(
            evse_name=data.get("evseName"),
            serial_number=data.get("serialNumber"),
            device_profile=data.get("deviceProfile"),
            firmware_version=data.get("firmwareVersion"),
            software_version=data.get("softwareVersion"),
            raw=data,
        )


@dataclass
class SocketRemoteInfo:
    """Live socket remote info (metrics, state) from the Daze API."""

    evse_status: str | None = None
    instant_power_as_watt: float | None = None
    delivered_energy_as_watt_hour: float | None = None
    last_charging_current_instant_l1: float | None = None
    last_charging_current_instant_l2: float | None = None
    last_charging_current_instant_l3: float | None = None
    last_ac_voltage_l1: float | None = None
    last_ac_voltage_l2: float | None = None
    last_ac_voltage_l3: float | None = None
    board_temperature: float | None = None
    case_temperature: float | None = None
    grid_max_power: float | None = None
    is_photovoltaic: bool | None = None
    evse_is_three_phase: bool | None = None
    max_external_charging_current_in_milli_amps: int | None = None
    last_max_charging_current: int | None = None
    eco_mode_enabled: bool | None = None
    operation_mode: str | None = None
    next_scheduled_charge: datetime | None = None
    scheduled_charge_time: datetime | None = None
    scheduled_start: datetime | None = None
    schedule_time: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SocketRemoteInfo:
        """Create a SocketRemoteInfo from the raw API response dict."""
        return cls(
            evse_status=data.get("evseStatus"),
            instant_power_as_watt=_safe_float(data.get("instantPowerAsWatt")),
            delivered_energy_as_watt_hour=_safe_float(
                data.get("deliveredEnergyAsWattHour")
            ),
            last_charging_current_instant_l1=_safe_float(
                data.get("lastChargingCurrentInstantL1")
            ),
            last_charging_current_instant_l2=_safe_float(
                data.get("lastChargingCurrentInstantL2")
            ),
            last_charging_current_instant_l3=_safe_float(
                data.get("lastChargingCurrentInstantL3")
            ),
            last_ac_voltage_l1=_safe_float(data.get("lastACVoltageL1")),
            last_ac_voltage_l2=_safe_float(data.get("lastACVoltageL2")),
            last_ac_voltage_l3=_safe_float(data.get("lastACVoltageL3")),
            board_temperature=_safe_float(data.get("boardTemperature")),
            case_temperature=_safe_float(data.get("caseTemperature")),
            grid_max_power=_safe_float(data.get("gridMaxPower")),
            is_photovoltaic=data.get("isPhotovoltaic"),
            evse_is_three_phase=data.get("evseIsThreePhase"),
            max_external_charging_current_in_milli_amps=_safe_int(
                data.get("maxExternalChargingCurrentInMilliAmps")
            ),
            last_max_charging_current=_safe_int(
                data.get("lastMaxChargingCurrent")
            ),
            eco_mode_enabled=data.get("ecoModeEnabled"),
            operation_mode=data.get("operationMode"),
            next_scheduled_charge=_parse_datetime(
                data.get("nextScheduledCharge")
            ),
            scheduled_charge_time=_parse_datetime(
                data.get("scheduledChargeTime")
            ),
            scheduled_start=_parse_datetime(data.get("scheduledStart")),
            schedule_time=_parse_datetime(data.get("scheduleTime")),
            raw=data,
        )


# ------------------------------------------------------------------
# Recharge session model
# ------------------------------------------------------------------


@dataclass
class RechargeSession:
    """A single recharge session from the Daze API.

    Handles both v3 and v4 response shapes. All fields except
    session_uid are optional since in-progress sessions lack
    end_time and cost.
    """

    session_uid: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    energy_wh: float | None = None
    cost: float | None = None
    currency: str | None = None
    status: str | None = None
    evse_serial: str | None = None
    # v4-only fields
    average_power: float | None = None
    charge_time: str | None = None
    computed_energy_cost_mul_by_thousand: int | None = None
    currency_symbol: str | None = None
    session_type: int | None = None
    authentication_status: int | None = None
    user_name: str | None = None
    email: str | None = None
    network_name: str | None = None
    evse_name: str | None = None
    is_average_power_valid: bool | None = None
    timezone: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RechargeSession:
        """Create a RechargeSession from v3 or v4 API response dict."""
        currency_raw = data.get("currency")
        if isinstance(currency_raw, dict):
            currency = currency_raw.get("code")
            currency_symbol = currency_raw.get("symbol")
        else:
            currency = currency_raw
            currency_symbol = None

        return cls(
            session_uid=str(data.get("id") or data.get("sessionUid") or ""),
            start_time=_parse_datetime(data.get("startDate")),
            end_time=_parse_datetime(data.get("endDate")),
            energy_wh=_safe_float(
                data.get("totEnergy") if "totEnergy" in data
                else data.get("energyInWh")
            ),
            cost=_safe_float(
                data.get("computedEnergyCost") if "computedEnergyCost" in data
                else data.get("totalCost")
            ),
            currency=currency,
            status=data.get("status"),
            evse_serial=(
                data.get("serialNumber") or data.get("evseSerialNumber")
            ),
            average_power=_safe_float(data.get("averagePow")),
            charge_time=data.get("chargeTime"),
            computed_energy_cost_mul_by_thousand=_safe_int(
                data.get("computedEnergyCostMulByThousand")
            ),
            currency_symbol=currency_symbol,
            session_type=_safe_int(data.get("sessionType")),
            authentication_status=_safe_int(data.get("authenticationStatus")),
            user_name=data.get("user"),
            email=data.get("email"),
            network_name=data.get("networkName"),
            evse_name=data.get("evseName"),
            is_average_power_valid=data.get("isAveragePowValid"),
            timezone=data.get("timezone"),
            raw=data,
        )

    @property
    def is_in_progress(self) -> bool:
        """Return True if this session has not ended."""
        return self.end_time is None


def _parse_datetime(value: Any) -> datetime | None:
    """Try to parse a datetime string from the API.

    The Daze API may return ISO 8601 strings, timestamps, or None.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    # Try ISO 8601 string parsing
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass

    return None


def _safe_float(value: Any) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> int | None:
    """Safely convert a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------------
# Coordinator data model
# ------------------------------------------------------------------


@dataclass
class SessionComputedFields:
    """Derived session sensor values computed by the coordinator."""

    last_session_energy: float | None = None
    last_session_duration: float | None = None
    last_session_cost: float | None = None
    last_session_start: datetime | None = None
    last_session_end: datetime | None = None
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


# ------------------------------------------------------------------
# Request payload models — POST endpoints
# ------------------------------------------------------------------


@dataclass
class SetMaxChargingCurrentRequest:
    """Payload for POST .../maxExternalChargingCurrent."""

    evse_serial_number: str
    max_external_charging_current_in_milli_amps: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the API-expected JSON shape."""
        return {
            "evseSerialNumber": self.evse_serial_number,
            "maxExternalChargingCurrentInMilliAmps": (
                self.max_external_charging_current_in_milli_amps
            ),
        }


@dataclass
class SetEcoModeRequest:
    """Payload for POST .../ecoMode."""

    evse_serial_number: str
    eco_mode_enabled: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the API-expected JSON shape."""
        return {
            "evseSerialNumber": self.evse_serial_number,
            "ecoModeEnabled": self.eco_mode_enabled,
        }
