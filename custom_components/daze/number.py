"""Number platform for Daze Wallbox.

Exposes a number entity to set the maximum charging current limit on the
wallbox, in milliamps (mA). Appears as a config entity under the device.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory, UnitOfElectricCurrent
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pydaze import ApiAuthError, ApiError

from .const import DOMAIN
from .coordinator import DazeDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DazeConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Industry-standard range for EVSE charging current limits
NATIVE_MIN_VALUE = 6000  # 6 A
NATIVE_MAX_VALUE = 32000  # 32 A
NATIVE_STEP = 100  # 0.1 A increments


class DazeWallboxNumberEntity(  # type: ignore[reportIncompatibleVariableOverride]
    CoordinatorEntity[DazeDataUpdateCoordinator], NumberEntity
):
    """Number entity to set the max charging current on a Daze wallbox."""

    _attr_has_entity_name = True
    _attr_translation_key = "max_charging_current"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = NATIVE_MIN_VALUE
    _attr_native_max_value = NATIVE_MAX_VALUE
    _attr_native_step = NATIVE_STEP
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.MILLIAMPERE

    def __init__(
        self,
        coordinator: DazeDataUpdateCoordinator,
        api_client: Any,
        serial_number: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialise the number entity.

        Args:
            coordinator: The Daze data coordinator.
            api_client: The Daze API client.
            serial_number: The wallbox serial number.
            device_info: Device info for the wallbox device registry.

        """
        super().__init__(coordinator)
        self._api_client = api_client
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_max_charging_current"
        self._attr_device_info = device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update native value from coordinator data."""
        if self.coordinator.data is None:
            self._attr_native_value = None
        else:
            socket = self.coordinator.data.socket
            self._attr_native_value = (
                socket.max_external_charging_current_in_milli_amps
                if socket.max_external_charging_current_in_milli_amps is not None
                else socket.last_max_charging_current
            )
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set the max charging current on the wallbox.

        Skips the API call if the value matches the current reading to
        avoid unnecessary writes.
        """
        int_value = int(value)

        # Skip API call if value hasn't changed
        current = self.native_value
        if current is not None and int_value == current:
            _LOGGER.debug(
                "Set current called with same value %d — skipping",
                int_value,
            )
            return

        try:
            _LOGGER.info(
                "Setting max charging current on %s to %d mA",
                self._serial_number,
                int_value,
            )
            await self._api_client.async_set_max_charging_current(
                self._serial_number, int_value
            )
            await self.coordinator.async_request_refresh()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed when setting charging current. "
                "Please re-authenticate the Daze integration."
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                f"Failed to set charging current: {err}"
            ) from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DazeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daze Wallbox number entity."""
    coordinator = entry.runtime_data.coordinator
    api_client = entry.runtime_data.api_client
    serial_number = entry.runtime_data.serial_number

    device_info = DeviceInfo(
        identifiers={(DOMAIN, serial_number)},
    )

    async_add_entities(
        [
            DazeWallboxNumberEntity(
                coordinator=coordinator,
                api_client=api_client,
                serial_number=serial_number,
                device_info=device_info,
            )
        ]
    )
