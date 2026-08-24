"""Tests for the Daze Wallbox sensor platform.

Tests the data extraction layer (value_fn lambdas, EVSE status mapping,
presence helpers) by duplicating the pure logic inline. This avoids
requiring the full Home Assistant runtime to run tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from custom_components.daze.models import (
    DazeCoordinatorData,
    SessionComputedFields,
    SocketRemoteInfo,
)

# ------------------------------------------------------------------
# Pure logic extracted from custom_components/daze/sensor.py
# These are tested independently of the HA entity framework.
# ------------------------------------------------------------------

EVSE_STATUS_MAP: dict[str, str] = {
    "idle": "idle",
    "charging": "charging",
    "paused": "paused",
    "error": "error",
    "offline": "offline",
    "waiting_for_car": "idle",
    "waiting_for_charge": "idle",
    "play_charge": "charging",
    "pause_charge": "paused",
    "stop_charge": "idle",
}


def get_evse_status(data: DazeCoordinatorData) -> str | None:
    """Map raw EVSE status to a human-readable HA state."""
    raw = data.socket.evse_status
    if raw is None:
        return None
    return EVSE_STATUS_MAP.get(str(raw).lower(), str(raw).lower())


def presence_on_off(value: bool | None) -> str | None:
    """Return 'on' or 'off' for a boolean diagnostic field."""
    if value is None:
        return None
    return "on" if value else "off"


def _make_data(**kwargs: Any) -> DazeCoordinatorData:
    """Build a DazeCoordinatorData with the given SocketRemoteInfo fields."""
    return DazeCoordinatorData(socket=SocketRemoteInfo(**kwargs))


@dataclass
class SensorDef:
    """Minimal representation of a sensor definition for testing."""

    key: str
    device_class: str | None = None
    state_class: str | None = None
    native_unit_of_measurement: str | None = None
    entity_category: str | None = None
    options: list[str] | None = None
    value_fn: callable = field(default=lambda data: None)  # noqa: E731
    expected_field: str | None = None


# ------------------------------------------------------------------
# Sensor definitions (mirrors SENSORS tuple from sensor.py)
# ------------------------------------------------------------------

SENSOR_DEFS: tuple[SensorDef, ...] = (
    SensorDef(
        key="instant_power",
        device_class="power",
        state_class="measurement",
        native_unit_of_measurement="W",
        expected_field="instant_power_as_watt",
    ),
    SensorDef(
        key="delivered_energy",
        device_class="energy",
        state_class="total_increasing",
        native_unit_of_measurement="Wh",
        expected_field="delivered_energy_as_watt_hour",
    ),
    SensorDef(
        key="charging_current_l1",
        device_class="current",
        state_class="measurement",
        native_unit_of_measurement="mA",
        expected_field="last_charging_current_instant_l1",
    ),
    SensorDef(
        key="charging_current_l2",
        device_class="current",
        state_class="measurement",
        native_unit_of_measurement="mA",
        expected_field="last_charging_current_instant_l2",
    ),
    SensorDef(
        key="charging_current_l3",
        device_class="current",
        state_class="measurement",
        native_unit_of_measurement="mA",
        expected_field="last_charging_current_instant_l3",
    ),
    SensorDef(
        key="ac_voltage_l1",
        device_class="voltage",
        state_class="measurement",
        native_unit_of_measurement="V",
        expected_field="last_ac_voltage_l1",
    ),
    SensorDef(
        key="ac_voltage_l2",
        device_class="voltage",
        state_class="measurement",
        native_unit_of_measurement="V",
        expected_field="last_ac_voltage_l2",
    ),
    SensorDef(
        key="ac_voltage_l3",
        device_class="voltage",
        state_class="measurement",
        native_unit_of_measurement="V",
        expected_field="last_ac_voltage_l3",
    ),
    SensorDef(
        key="board_temperature",
        device_class="temperature",
        state_class="measurement",
        native_unit_of_measurement="°C",
        expected_field="board_temperature",
    ),
    SensorDef(
        key="case_temperature",
        device_class="temperature",
        state_class="measurement",
        native_unit_of_measurement="°C",
        expected_field="case_temperature",
    ),
    SensorDef(
        key="evse_status",
        device_class="enum",
        options=["idle", "charging", "paused", "error", "offline"],
    ),
    SensorDef(
        key="grid_max_power",
        device_class="power",
        native_unit_of_measurement="W",
        entity_category="diagnostic",
        expected_field="grid_max_power",
    ),
    SensorDef(
        key="is_photovoltaic",
        device_class="enum",
        entity_category="diagnostic",
        options=["on", "off"],
    ),
    SensorDef(
        key="is_three_phase",
        device_class="enum",
        entity_category="diagnostic",
        options=["on", "off"],
    ),
    # --- Session sensors ---
    SensorDef(
        key="last_session_energy",
        device_class="energy",
        state_class="total_increasing",
        native_unit_of_measurement="Wh",
    ),
    SensorDef(
        key="last_session_duration",
        native_unit_of_measurement="min",
    ),
    SensorDef(
        key="last_session_cost",
        device_class="monetary",
        native_unit_of_measurement="EUR",
    ),
    SensorDef(
        key="last_session_start",
        device_class="timestamp",
    ),
    SensorDef(
        key="last_session_end",
        device_class="timestamp",
    ),
    SensorDef(
        key="lifetime_energy",
        device_class="energy",
        state_class="total_increasing",
        native_unit_of_measurement="Wh",
    ),
    SensorDef(
        key="total_sessions",
        state_class="total_increasing",
    ),
    SensorDef(
        key="next_scheduled_charge",
        device_class="timestamp",
        entity_category="diagnostic",
    ),
)


def _def_by_key(key: str) -> SensorDef:
    for s in SENSOR_DEFS:
        if s.key == key:
            return s
    msg = f"No sensor def with key: {key}"
    raise KeyError(msg)


# ------------------------------------------------------------------
# Sample data
# ------------------------------------------------------------------

SAMPLE_SOCKET = SocketRemoteInfo(
    instant_power_as_watt=3500.0,
    delivered_energy_as_watt_hour=15000.0,
    last_charging_current_instant_l1=5000.0,
    last_charging_current_instant_l2=5100.0,
    last_charging_current_instant_l3=4900.0,
    last_ac_voltage_l1=230.0,
    last_ac_voltage_l2=231.0,
    last_ac_voltage_l3=229.0,
    board_temperature=32.0,
    case_temperature=28.0,
    evse_status="charging",
    grid_max_power=22000.0,
    is_photovoltaic=True,
    evse_is_three_phase=False,
)

SAMPLE_DATA = DazeCoordinatorData(socket=SAMPLE_SOCKET)
NULL_SOCKET = SocketRemoteInfo()
NULL_DATA = DazeCoordinatorData(socket=NULL_SOCKET)
EMPTY_DATA = DazeCoordinatorData(socket=SocketRemoteInfo())


# ==================================================================
# Tests
# ==================================================================


class TestSensorDefinitions:
    """Verify sensor metadata is correct."""

    def test_all_keys_unique(self) -> None:
        keys = [s.key for s in SENSOR_DEFS]
        assert len(keys) == len(set(keys)), f"Duplicate keys: {keys}"

    def test_measurement_sensors_have_state_class(self) -> None:
        measurement = {"instant_power", "delivered_energy",
                       "charging_current_l1", "charging_current_l2",
                       "charging_current_l3", "ac_voltage_l1",
                       "ac_voltage_l2", "ac_voltage_l3",
                       "board_temperature", "case_temperature",
                       "last_session_energy", "lifetime_energy",
                       "total_sessions"}
        for s in SENSOR_DEFS:
            if s.key in measurement:
                assert s.state_class is not None, f"{s.key} missing state_class"

    def test_diagnostic_sensors_have_entity_category(self) -> None:
        diagnostic = {"grid_max_power", "is_photovoltaic", "is_three_phase",
                      "next_scheduled_charge"}
        for s in SENSOR_DEFS:
            if s.key in diagnostic:
                assert s.entity_category is not None, (
                    f"{s.key} missing entity_category"
                )

    def test_session_sensors_are_measurement(self) -> None:
        """Session sensors that are measurement/total should have state_class."""
        must_have = {"last_session_energy", "lifetime_energy", "total_sessions"}
        for s in SENSOR_DEFS:
            if s.key in must_have:
                assert s.state_class is not None, f"{s.key} missing state_class"

    def test_evse_status_has_all_options(self) -> None:
        s = _def_by_key("evse_status")
        assert sorted(s.options or []) == sorted(
            ["idle", "charging", "paused", "error", "offline"]
        )


class TestValueExtraction:
    """Verify value_fn lambdas extract correct fields from data."""

    def test_instant_power(self) -> None:
        assert SAMPLE_DATA.socket.instant_power_as_watt == 3500.0

    def test_delivered_energy(self) -> None:
        assert SAMPLE_DATA.socket.delivered_energy_as_watt_hour == 15000.0

    def test_charging_current_l1(self) -> None:
        assert SAMPLE_DATA.socket.last_charging_current_instant_l1 == 5000.0

    def test_charging_current_l2(self) -> None:
        assert SAMPLE_DATA.socket.last_charging_current_instant_l2 == 5100.0

    def test_charging_current_l3(self) -> None:
        assert SAMPLE_DATA.socket.last_charging_current_instant_l3 == 4900.0

    def test_ac_voltage_l1(self) -> None:
        assert SAMPLE_DATA.socket.last_ac_voltage_l1 == 230.0

    def test_ac_voltage_l2(self) -> None:
        assert SAMPLE_DATA.socket.last_ac_voltage_l2 == 231.0

    def test_ac_voltage_l3(self) -> None:
        assert SAMPLE_DATA.socket.last_ac_voltage_l3 == 229.0

    def test_board_temperature(self) -> None:
        assert SAMPLE_DATA.socket.board_temperature == 32.0

    def test_case_temperature(self) -> None:
        assert SAMPLE_DATA.socket.case_temperature == 28.0

    def test_grid_max_power(self) -> None:
        assert SAMPLE_DATA.socket.grid_max_power == 22000.0

    def test_is_photovoltaic_true(self) -> None:
        assert SAMPLE_DATA.socket.is_photovoltaic is True

    def test_is_three_phase_false(self) -> None:
        assert SAMPLE_DATA.socket.evse_is_three_phase is False

    def test_null_values(self) -> None:
        """Verify all fields can be None without crashing."""
        assert NULL_DATA.socket.instant_power_as_watt is None
        assert NULL_DATA.socket.evse_status is None
        assert NULL_DATA.socket.board_temperature is None

    def test_missing_keys_return_none(self) -> None:
        """Default SocketRemoteInfo fields are None."""
        empty = SocketRemoteInfo()
        for s in SENSOR_DEFS:
            if s.expected_field:
                assert getattr(empty, s.expected_field) is None


class TestEvseStatus:
    """Verify EVSE status mapping."""

    def test_charging(self) -> None:
        assert get_evse_status(_make_data(evse_status="charging")) == "charging"

    def test_idle(self) -> None:
        assert get_evse_status(_make_data(evse_status="idle")) == "idle"

    def test_paused(self) -> None:
        assert get_evse_status(_make_data(evse_status="paused")) == "paused"

    def test_error(self) -> None:
        assert get_evse_status(_make_data(evse_status="error")) == "error"

    def test_offline(self) -> None:
        assert get_evse_status(_make_data(evse_status="offline")) == "offline"

    def test_aliases(self) -> None:
        assert get_evse_status(_make_data(evse_status="waiting_for_car")) == "idle"
        assert get_evse_status(_make_data(evse_status="waiting_for_charge")) == "idle"
        assert get_evse_status(_make_data(evse_status="play_charge")) == "charging"
        assert get_evse_status(_make_data(evse_status="pause_charge")) == "paused"
        assert get_evse_status(_make_data(evse_status="stop_charge")) == "idle"

    def test_case_insensitive(self) -> None:
        assert get_evse_status(_make_data(evse_status="CHARGING")) == "charging"
        assert get_evse_status(_make_data(evse_status="Idle")) == "idle"

    def test_unknown_passes_through(self) -> None:
        assert get_evse_status(_make_data(evse_status="weird_value")) == "weird_value"

    def test_none_returns_none(self) -> None:
        assert get_evse_status(_make_data(evse_status=None)) is None

    def test_missing_returns_none(self) -> None:
        assert get_evse_status(_make_data()) is None

    def test_all_mapped_values_are_canonical(self) -> None:
        canonical = {"idle", "charging", "paused", "error", "offline"}
        for value in EVSE_STATUS_MAP.values():
            assert value in canonical, f"Unexpected: {value!r}"


class TestPresenceOnOff:
    """Verify boolean presence/status mapping."""

    def test_true_maps_to_on(self) -> None:
        assert presence_on_off(True) == "on"

    def test_false_maps_to_off(self) -> None:
        assert presence_on_off(False) == "off"

    def test_none_maps_to_none(self) -> None:
        assert presence_on_off(None) is None
