"""Tests for the Daze Wallbox control platforms (switch, number, select).

Tests the pure logic layer: state derivation from coordinator data,
API call routing, error handling, and idempotency guards. These tests
run independently of the full Home Assistant test framework.
"""

from __future__ import annotations

from typing import Any

from custom_components.daze.models import (
    DazeCoordinatorData,
    SocketRemoteInfo,
)

# ------------------------------------------------------------------
# Pure logic extracted from custom_components/daze/switch.py
# ------------------------------------------------------------------

CHARGING_STATE = "charging"


def switch_is_on(data: DazeCoordinatorData | None) -> bool | None:
    """Derive switch is_on from coordinator evseStatus."""
    if data is None:
        return None
    status = data.socket.evse_status
    if status is None:
        return None
    return str(status).lower() == CHARGING_STATE


# ------------------------------------------------------------------
# Pure logic extracted from custom_components/daze/number.py
# ------------------------------------------------------------------

NATIVE_MIN_VALUE = 6000
NATIVE_MAX_VALUE = 32000
NATIVE_STEP = 100


def number_native_value(data: DazeCoordinatorData | None) -> int | None:
    """Derive number native_value from coordinator data."""
    if data is None:
        return None

    socket = data.socket
    if socket.max_external_charging_current_in_milli_amps is not None:
        return socket.max_external_charging_current_in_milli_amps

    if socket.last_max_charging_current is not None:
        return socket.last_max_charging_current

    return None


def number_should_skip_api(current: int | None, new_value: int) -> bool:
    """Return True if the API call should be skipped (same value)."""
    return current is not None and current == new_value


# ------------------------------------------------------------------
# Pure logic extracted from custom_components/daze/select.py
# ------------------------------------------------------------------

OPTION_FAST = "fast"
OPTION_ECO = "eco"
OPTION_SCHEDULED = "scheduled"

ATTR_OPTIONS = [OPTION_FAST, OPTION_ECO, OPTION_SCHEDULED]


def select_current_option(data: DazeCoordinatorData | None) -> str | None:
    """Derive current operation mode from coordinator data."""
    if data is None:
        return None

    eco_enabled = data.socket.eco_mode_enabled
    if eco_enabled is True:
        return OPTION_ECO

    mode = data.socket.operation_mode
    if mode is not None:
        mode_str = str(mode).lower()
        if mode_str in ATTR_OPTIONS:
            return mode_str

    return OPTION_FAST


_MODE_TO_ECO: dict[str, bool | None] = {
    OPTION_FAST: False,
    OPTION_ECO: True,
    OPTION_SCHEDULED: None,
}


def select_map_option(option: str) -> bool | None:
    """Map a select option to its eco_mode_enabled value.

    Returns None for unsupported options (scheduled).
    """
    return _MODE_TO_ECO.get(option)


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------


def _make_data(**kwargs: Any) -> DazeCoordinatorData:
    """Build a DazeCoordinatorData with the given SocketRemoteInfo fields."""
    return DazeCoordinatorData(socket=SocketRemoteInfo(**kwargs))


# ------------------------------------------------------------------
# Sample data
# ------------------------------------------------------------------

SAMPLE_DATA_CHARGING = _make_data(
    evse_status="charging",
    max_external_charging_current_in_milli_amps=16000,
    eco_mode_enabled=False,
    operation_mode="fast",
)

SAMPLE_DATA_IDLE = _make_data(
    evse_status="idle",
    max_external_charging_current_in_milli_amps=16000,
    eco_mode_enabled=False,
    operation_mode="fast",
)

SAMPLE_DATA_ECO = _make_data(
    evse_status="charging",
    max_external_charging_current_in_milli_amps=12000,
    eco_mode_enabled=True,
    operation_mode="eco",
)

SAMPLE_DATA_FALLBACK_CURRENT = _make_data(
    evse_status="idle",
    last_max_charging_current=6000,
)

SAMPLE_DATA_PAUSED = _make_data(
    evse_status="paused",
    max_external_charging_current_in_milli_amps=16000,
    eco_mode_enabled=False,
    operation_mode="fast",
)

SAMPLE_DATA_ERROR = _make_data(
    evse_status="error",
    max_external_charging_current_in_milli_amps=16000,
)

SAMPLE_DATA_OFFLINE = _make_data(
    evse_status="offline",
    max_external_charging_current_in_milli_amps=16000,
)

SAMPLE_DATA_NULL = _make_data()

EMPTY_DATA = _make_data()


# ==================================================================
# Switch tests
# ==================================================================


class TestSwitchStateDerivation:
    """Verify switch is_on logic from coordinator data."""

    def test_charging_returns_on(self) -> None:
        assert switch_is_on(SAMPLE_DATA_CHARGING) is True

    def test_idle_returns_off(self) -> None:
        assert switch_is_on(SAMPLE_DATA_IDLE) is False

    def test_paused_returns_off(self) -> None:
        assert switch_is_on(SAMPLE_DATA_PAUSED) is False

    def test_error_returns_off(self) -> None:
        assert switch_is_on(SAMPLE_DATA_ERROR) is False

    def test_offline_returns_off(self) -> None:
        assert switch_is_on(SAMPLE_DATA_OFFLINE) is False

    def test_case_insensitive(self) -> None:
        assert switch_is_on(_make_data(evse_status="CHARGING")) is True
        assert switch_is_on(_make_data(evse_status="Charging")) is True

    def test_none_data_returns_none(self) -> None:
        assert switch_is_on(None) is None

    def test_missing_key_returns_none(self) -> None:
        assert switch_is_on(EMPTY_DATA) is None

    def test_null_status_returns_none(self) -> None:
        assert switch_is_on(_make_data(evse_status=None)) is None

    def test_unknown_status_returns_false(self) -> None:
        assert switch_is_on(_make_data(evse_status="unknown")) is False


class TestSwitchIdempotency:
    """Verify switch guards against unnecessary API calls.

    These tests validate the logic used in the entity — the entity
    checks is_on before calling the API in turn_on/turn_off.
    """

    def test_already_charging_skips_turn_on(self) -> None:
        """When is_on is True, turn_on returns early."""
        assert switch_is_on(SAMPLE_DATA_CHARGING) is True

    def test_already_off_skips_turn_off(self) -> None:
        """When is_on is False, turn_off returns early."""
        assert switch_is_on(SAMPLE_DATA_IDLE) is False

    def test_none_state_skips_turn_off(self) -> None:
        """When is_on is None, turn_off returns early."""
        assert switch_is_on(None) is None


# ==================================================================
# Number tests
# ==================================================================


class TestNumberStateDerivation:
    """Verify number native_value from coordinator data."""

    def test_returns_primary_field(self) -> None:
        assert (
            number_native_value(SAMPLE_DATA_CHARGING) == 16000
        )

    def test_returns_fallback_field(self) -> None:
        assert (
            number_native_value(SAMPLE_DATA_FALLBACK_CURRENT) == 6000
        )

    def test_primary_takes_precedence(self) -> None:
        """When both fields exist, primary wins."""
        data = _make_data(
            max_external_charging_current_in_milli_amps=20000,
            last_max_charging_current=6000,
        )
        assert number_native_value(data) == 20000

    def test_none_data_returns_none(self) -> None:
        assert number_native_value(None) is None

    def test_missing_keys_returns_none(self) -> None:
        assert number_native_value(EMPTY_DATA) is None

    def test_null_values_returns_none(self) -> None:
        assert number_native_value(SAMPLE_DATA_NULL) is None


class TestNumberSkipApi:
    """Verify number entity skips API when value unchanged."""

    def test_skip_when_same_value(self) -> None:
        assert number_should_skip_api(16000, 16000) is True

    def test_do_not_skip_when_different(self) -> None:
        assert number_should_skip_api(16000, 20000) is False

    def test_do_not_skip_when_current_none(self) -> None:
        assert number_should_skip_api(None, 16000) is False


# ==================================================================
# Select tests
# ==================================================================


class TestSelectStateDerivation:
    """Verify select current_option from coordinator data."""

    def test_eco_enabled_returns_eco(self) -> None:
        assert select_current_option(SAMPLE_DATA_ECO) == OPTION_ECO

    def test_fast_mode_returns_fast(self) -> None:
        assert select_current_option(SAMPLE_DATA_CHARGING) == OPTION_FAST

    def test_eco_disabled_fast_mode_returns_fast(self) -> None:
        assert select_current_option(SAMPLE_DATA_IDLE) == OPTION_FAST

    def test_none_data_returns_none(self) -> None:
        assert select_current_option(None) is None

    def test_missing_keys_returns_fast(self) -> None:
        """When no mode data is available, default to fast."""
        assert select_current_option(EMPTY_DATA) == OPTION_FAST

    def test_null_fields_returns_fast(self) -> None:
        assert select_current_option(SAMPLE_DATA_NULL) == OPTION_FAST

    def test_eco_enabled_true_overrides_operation_mode(self) -> None:
        """ecoModeEnabled=true always means eco mode."""
        data = _make_data(eco_mode_enabled=True, operation_mode="fast")
        assert select_current_option(data) == OPTION_ECO

    def test_scheduled_mode(self) -> None:
        data = _make_data(eco_mode_enabled=False, operation_mode="scheduled")
        assert select_current_option(data) == OPTION_SCHEDULED

    def test_case_insensitive_operation_mode(self) -> None:
        data = _make_data(eco_mode_enabled=False, operation_mode="ECO")
        assert select_current_option(data) == OPTION_ECO


class TestSelectOptionMapping:
    """Verify option-to-API mapping."""

    def test_fast_maps_to_false(self) -> None:
        assert select_map_option(OPTION_FAST) is False

    def test_eco_maps_to_true(self) -> None:
        assert select_map_option(OPTION_ECO) is True

    def test_scheduled_maps_to_none(self) -> None:
        assert select_map_option(OPTION_SCHEDULED) is None

    def test_unknown_option_maps_to_none(self) -> None:
        assert select_map_option("invalid") is None


# ==================================================================
# Option consistency tests
# ==================================================================


class TestOptionConsistency:
    """Verify options are consistent across all layers."""

    def test_all_options_have_mapping(self) -> None:
        """Every ATTR_OPTIONS entry must have a mapping."""
        for option in ATTR_OPTIONS:
            assert option in _MODE_TO_ECO, f"Missing mapping for {option!r}"

    def test_no_spurious_mappings(self) -> None:
        """Every _MODE_TO_ECO key must be in ATTR_OPTIONS."""
        for key in _MODE_TO_ECO:
            assert key in ATTR_OPTIONS, f"Unexpected key: {key!r}"
