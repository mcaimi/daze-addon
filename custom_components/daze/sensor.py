"""Sensor platform for Daze Wallbox.

Exposes wallbox metrics as Home Assistant sensor entities with correct
device classes, state classes, and units of measurement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DazeDataUpdateCoordinator
from .models import DazeCoordinatorData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DazeConfigEntry

PARALLEL_UPDATES = 1


# ------------------------------------------------------------------
# EVSE status mapping
# ------------------------------------------------------------------

EVSE_STATUS_MAP: dict[str, str] = {
    "idle": "idle",
    "charging": "charging",
    "paused": "paused",
    "error": "error",
    "offline": "offline",
    # Potential API values that map to the same HA states
    "waiting_for_car": "idle",
    "waiting_for_charge": "idle",
    "play_charge": "charging",
    "pause_charge": "paused",
    "stop_charge": "idle",
}


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------


def _get_evse_status(data: DazeCoordinatorData) -> str | None:
    """Map raw EVSE status to a human-readable HA state."""
    raw = data.socket.evse_status
    if raw is None:
        return None
    return EVSE_STATUS_MAP.get(str(raw).lower(), str(raw).lower())





# ------------------------------------------------------------------
# Sensor description
# ------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class DazeSensorEntityDescription(SensorEntityDescription):
    """Description for a Daze wallbox sensor.

    Extends SensorEntityDescription with a ``value_fn`` callback that
    extracts the sensor value from the coordinator data dict.
    """

    value_fn: Callable[[DazeCoordinatorData], Any | None] = lambda data: None


# ------------------------------------------------------------------
# Helper functions used by sensor definitions
# ------------------------------------------------------------------


def _get_next_scheduled_charge(data: DazeCoordinatorData) -> Any | None:
    """Extract the next scheduled charge time from coordinator data.

    Tries multiple typed fields to accommodate variations in the
    Daze API response.
    """
    s = data.socket
    return (
        s.next_scheduled_charge
        or s.scheduled_charge_time
        or s.scheduled_start
        or s.schedule_time
    )


def _presence_on_off(value: bool | None) -> str | None:
    """Return 'on' or 'off' for a boolean diagnostic field."""
    if value is None:
        return None
    return "on" if value else "off"


# ------------------------------------------------------------------
# Sensor definitions
# ------------------------------------------------------------------

SENSORS: tuple[DazeSensorEntityDescription, ...] = (
    # --- Measurement sensors ---
    DazeSensorEntityDescription(
        key="instant_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda data: data.socket.instant_power_as_watt,
    ),
    DazeSensorEntityDescription(
        key="delivered_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda data: data.socket.delivered_energy_as_watt_hour,
    ),
    DazeSensorEntityDescription(
        key="charging_current_l1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        value_fn=lambda data: data.socket.last_charging_current_instant_l1,
    ),
    DazeSensorEntityDescription(
        key="charging_current_l2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        value_fn=lambda data: data.socket.last_charging_current_instant_l2,
    ),
    DazeSensorEntityDescription(
        key="charging_current_l3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        value_fn=lambda data: data.socket.last_charging_current_instant_l3,
    ),
    DazeSensorEntityDescription(
        key="ac_voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data.socket.last_ac_voltage_l1,
    ),
    DazeSensorEntityDescription(
        key="ac_voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data.socket.last_ac_voltage_l2,
    ),
    DazeSensorEntityDescription(
        key="ac_voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data.socket.last_ac_voltage_l3,
    ),
    DazeSensorEntityDescription(
        key="board_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.socket.board_temperature,
    ),
    DazeSensorEntityDescription(
        key="case_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.socket.case_temperature,
    ),
    # --- EVSE status sensor ---
    DazeSensorEntityDescription(
        key="evse_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(dict.fromkeys(EVSE_STATUS_MAP.values())),
        value_fn=_get_evse_status,
    ),
    # --- Diagnostic sensors (network-level) ---
    DazeSensorEntityDescription(
        key="grid_max_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.socket.grid_max_power,
    ),
    DazeSensorEntityDescription(
        key="is_photovoltaic",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=["on", "off"],
        value_fn=lambda data: _presence_on_off(data.socket.is_photovoltaic),
    ),
    DazeSensorEntityDescription(
        key="is_three_phase",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=["on", "off"],
        value_fn=lambda data: _presence_on_off(data.socket.evse_is_three_phase),
    ),
    # --- Session sensors ---
    DazeSensorEntityDescription(
        key="last_session_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda data: data.session_fields.last_session_energy,
    ),
    DazeSensorEntityDescription(
        key="last_session_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: data.session_fields.last_session_duration,
    ),
    DazeSensorEntityDescription(
        key="last_session_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        value_fn=lambda data: data.session_fields.last_session_cost,
    ),
    DazeSensorEntityDescription(
        key="last_session_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.session_fields.last_session_start,
    ),
    DazeSensorEntityDescription(
        key="last_session_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.session_fields.last_session_end,
    ),
    # --- Aggregate counters ---
    DazeSensorEntityDescription(
        key="lifetime_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda data: data.session_fields.lifetime_energy,
    ),
    DazeSensorEntityDescription(
        key="total_sessions",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.session_fields.total_sessions,
    ),
    # --- Diagnostic sensors ---
    DazeSensorEntityDescription(
        key="next_scheduled_charge",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_next_scheduled_charge,
    ),
)


# ------------------------------------------------------------------
# Sensors that restore state on HA restart
# ------------------------------------------------------------------

_RESTORE_STATE_KEYS: frozenset[str] = frozenset({
    "delivered_energy",
    "lifetime_energy",
    "total_sessions",
    "last_session_energy",
    "last_session_cost",
    "last_session_duration",
})
"""Sensor keys whose native_value should survive HA restarts.

These are cumulative or infrequently-changing values where losing the
last known state would cause visible gaps in history or dashboards.
"""


# ------------------------------------------------------------------
# Base sensor entity
# ------------------------------------------------------------------


class DazeWallboxSensorEntity(
    CoordinatorEntity[DazeDataUpdateCoordinator], RestoreEntity, SensorEntity
):
    """Base sensor entity for Daze Wallbox metrics.

    All wallbox sensor entities inherit from this class. It provides:
    - ``device_info`` from the registered wallbox device
    - ``_attr_has_entity_name`` so HA prefixes the device name
    - Automatic ``available`` propagation via ``CoordinatorEntity``
    - State restoration for cumulative sensors via ``RestoreEntity``
    """

    entity_description: DazeSensorEntityDescription
    _attr_has_entity_name = True
    _restored_value: Any | None = None

    def __init__(
        self,
        coordinator: DazeDataUpdateCoordinator,
        description: DazeSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialise the sensor entity.

        Args:
            coordinator: The Daze data coordinator.
            description: The sensor entity description.
            device_info: Device info for the wallbox device registry.

        """
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        """Restore last known state on HA restart.

        Only meaningful for cumulative sensors listed in
        ``_RESTORE_STATE_KEYS``. If the coordinator already returned
        data before this entity is added, restoration is skipped.
        """
        await super().async_added_to_hass()

        # Only restore for sensors that need it
        if self.entity_description.key not in _RESTORE_STATE_KEYS:
            return

        # Coordinator already has data — no need to restore
        if self.coordinator.data is not None:
            return

        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (None, "unknown", "unavailable"):
            return

        try:
            # Preserve the state as a float for numeric sensors
            self._restored_value = float(last_state.state)
        except (ValueError, TypeError):
            self._restored_value = last_state.state

    @property
    def native_value(self) -> Any | None:
        """Return the sensor value from the latest coordinator data.

        Falls back to the restored value (from before HA restart) when
        coordinator data is temporarily unavailable, so cumulative
        sensors don't show None during startup delays.
        """
        if self.coordinator.data is not None:
            return self.entity_description.value_fn(self.coordinator.data)
        # Fall back to restored state if available
        if self._restored_value is not None:
            return self._restored_value
        return None


# ------------------------------------------------------------------
# Platform setup
# ------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DazeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daze Wallbox sensor entities."""
    coordinator = entry.runtime_data.coordinator
    serial_number = entry.runtime_data.serial_number

    # Build device info matching the device registered in __init__.py
    device_info = DeviceInfo(
        identifiers={(DOMAIN, serial_number)},
    )

    entities: list[DazeWallboxSensorEntity] = []

    for description in SENSORS:
        entities.append(
            DazeWallboxSensorEntity(
                coordinator=coordinator,
                description=description,
                device_info=device_info,
            )
        )

    async_add_entities(entities)
