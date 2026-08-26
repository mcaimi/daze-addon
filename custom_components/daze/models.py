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
    description: str | None = None
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    country: str | None = None
    network_type: int | None = None
    grid_is_three_phase: bool | None = None
    supply_max_power: float | None = None
    is_photovoltaic: bool | None = None
    energy_cost: float | None = None
    currency_code: str | None = None
    currency_symbol: str | None = None
    time_zone: str | None = None
    eco_mode_enabled: bool | None = None
    eco_mode_type: int | None = None
    smart_tariff_enabled: bool | None = None
    num_evses_in_network: int | None = None
    num_users_in_network: int | None = None
    is_admin: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Network:
        """Create a Network from the raw API response dict."""
        currency_raw = data.get("currency")
        if isinstance(currency_raw, dict):
            currency_code = currency_raw.get("code")
            currency_symbol = currency_raw.get("symbol")
        else:
            currency_code = None
            currency_symbol = None

        return cls(
            uid=str(data.get("uid", "")),
            name=data.get("name"),
            description=data.get("description"),
            address=data.get("address"),
            city=data.get("city"),
            zip_code=data.get("zipCode"),
            country=data.get("country"),
            network_type=_safe_int(data.get("networkType")),
            grid_is_three_phase=data.get("gridIsThreePhase"),
            supply_max_power=_safe_float(data.get("supplyMaxPower")),
            is_photovoltaic=data.get("isPhotovoltaic"),
            energy_cost=_safe_float(data.get("energyCost")),
            currency_code=currency_code,
            currency_symbol=currency_symbol,
            time_zone=data.get("timeZone"),
            eco_mode_enabled=data.get("ecoModeEnabled"),
            eco_mode_type=_safe_int(data.get("ecoModeType")),
            smart_tariff_enabled=data.get("smartTariffEnabled"),
            num_evses_in_network=_safe_int(data.get("numEvsesInNetwork")),
            num_users_in_network=_safe_int(data.get("numUsersInNetwork")),
            is_admin=data.get("isAdmin"),
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
    evse_is_three_phase: bool | None = None
    supply_grid_max_power: float | None = None
    max_external_charging_current_in_milli_amps: int | None = None
    eco_mode_enabled: bool | None = None
    operation_mode: int | None = None
    last_status: int | None = None
    active: bool | None = None
    wifi_enabled: bool | None = None
    wifi_ssid: str | None = None
    warranty_expiration: datetime | None = None
    scheduling: bool | None = None
    is_dynamic_load_management_on: bool | None = None
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
            evse_is_three_phase=data.get("evseIsThreePhase"),
            supply_grid_max_power=_safe_float(data.get("supplyGridMaxPower")),
            max_external_charging_current_in_milli_amps=_safe_int(
                data.get("maxExternalChargingCurrentInMilliAmps")
            ),
            eco_mode_enabled=data.get("ecoModeEnabled"),
            operation_mode=_safe_int(data.get("operationMode")),
            last_status=_safe_int(data.get("lastStatus")),
            active=data.get("active"),
            wifi_enabled=data.get("wifiEnabled"),
            wifi_ssid=data.get("wifiSSID"),
            warranty_expiration=_parse_datetime(data.get("warrantyExpiration")),
            scheduling=data.get("scheduling"),
            is_dynamic_load_management_on=data.get("isDynamicLoadManagementOn"),
            raw=data,
        )


@dataclass
class SocketRemoteInfo:
    """Live socket remote info (metrics, state) from the Daze API.

    The v3 API returned all fields at the top level. The current API
    nests measurement fields inside a ``chargeSession`` sub-object and
    uses ``evseState`` (int) instead of ``evseStatus`` (str).
    ``from_dict`` handles both shapes.
    """

    evse_status: str | int | None = None
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
    operation_mode: int | None = None
    next_scheduled_charge: datetime | None = None
    scheduled_charge_time: datetime | None = None
    scheduled_start: datetime | None = None
    schedule_time: datetime | None = None
    active: bool | None = None
    is_paused: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SocketRemoteInfo:
        """Create a SocketRemoteInfo from the raw API response dict.

        Measurement fields are looked up first in the ``chargeSession``
        sub-object (current API), then at the top level (legacy v3).
        """
        charge = data.get("chargeSession") or {}

        def _pick(key: str) -> Any:
            """Return value from chargeSession if present, else top-level."""
            if key in charge:
                return charge[key]
            return data.get(key)

        schedule = data.get("nextScheduleInfo") or {}

        return cls(
            evse_status=data.get("evseStatus") or data.get("evseState"),
            instant_power_as_watt=_safe_float(_pick("instantPowerAsWatt")),
            delivered_energy_as_watt_hour=_safe_float(
                _pick("deliveredEnergyAsWattHour")
            ),
            last_charging_current_instant_l1=_safe_float(
                _pick("lastChargingCurrentInstantL1")
            ),
            last_charging_current_instant_l2=_safe_float(
                _pick("lastChargingCurrentInstantL2")
            ),
            last_charging_current_instant_l3=_safe_float(
                _pick("lastChargingCurrentInstantL3")
            ),
            last_ac_voltage_l1=_safe_float(_pick("lastACVoltageL1")),
            last_ac_voltage_l2=_safe_float(_pick("lastACVoltageL2")),
            last_ac_voltage_l3=_safe_float(_pick("lastACVoltageL3")),
            board_temperature=_safe_float(_pick("boardTemperature")),
            case_temperature=_safe_float(_pick("caseTemperature")),
            grid_max_power=_safe_float(_pick("gridMaxPower")),
            is_photovoltaic=data.get("isPhotovoltaic"),
            evse_is_three_phase=data.get("evseIsThreePhase"),
            max_external_charging_current_in_milli_amps=_safe_int(
                _pick("maxExternalChargingCurrentInMilliAmps")
            ),
            last_max_charging_current=_safe_int(
                _pick("lastMaxChargingCurrent")
            ),
            eco_mode_enabled=data.get("ecoModeEnabled"),
            operation_mode=_safe_int(data.get("operationMode")),
            next_scheduled_charge=_parse_datetime(
                schedule.get("nextScheduledCharge")
                or data.get("nextScheduledCharge")
            ),
            scheduled_charge_time=_parse_datetime(
                schedule.get("scheduledChargeTime")
                or data.get("scheduledChargeTime")
            ),
            scheduled_start=_parse_datetime(
                schedule.get("scheduledStart")
                or data.get("scheduledStart")
            ),
            schedule_time=_parse_datetime(
                schedule.get("scheduleTime")
                or data.get("scheduleTime")
            ),
            active=data.get("active"),
            is_paused=data.get("isPaused"),
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
    socket_serial_number: str | None = None
    session_id: int | None = None
    telemetry_date: datetime | None = None
    rfid_serial_number: str | None = None
    smart_tariff_session: dict[str, Any] | None = None
    price_mul_by_thousand: int | None = None
    price: float | None = None
    is_admin: bool | None = None
    stripe_session_id: str | None = None
    session_details: list[Any] | None = None
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
            socket_serial_number=data.get("socketSerialNumber"),
            session_id=_safe_int(data.get("sessionId")),
            telemetry_date=_parse_datetime(data.get("telemetryDate")),
            rfid_serial_number=data.get("rfidSerialNumber"),
            smart_tariff_session=data.get("smartTariffSession"),
            price_mul_by_thousand=_safe_int(data.get("priceMulByThousand")),
            price=_safe_float(data.get("price")),
            is_admin=data.get("isAdmin"),
            stripe_session_id=data.get("stripeSessionId"),
            session_details=data.get("sessionDetails"),
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
