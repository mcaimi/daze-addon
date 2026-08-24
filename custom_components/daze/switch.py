"""Switch platform for Daze Wallbox.

Exposes a switch entity to start and stop charging. The switch state
reflects the live ``evseStatus`` field from the coordinator data:
charging → on, all others → off.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ApiAuthError, ApiError
from .const import DOMAIN
from .coordinator import DazeDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DazeConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

CHARGING_STATE = "charging"


class DazeWallboxSwitchEntity(
    CoordinatorEntity[DazeDataUpdateCoordinator], SwitchEntity
):
    """Switch to start/stop charging on a Daze wallbox."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DazeDataUpdateCoordinator,
        api_client: Any,
        serial_number: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialise the switch entity.

        Args:
            coordinator: The Daze data coordinator.
            api_client: The Daze API client.
            serial_number: The wallbox serial number.
            device_info: Device info for the wallbox device registry.

        """
        super().__init__(coordinator)
        self._api_client = api_client
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_charge_switch"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        """Return True if the wallbox is currently charging."""
        if self.coordinator.data is None:
            return None
        status = self.coordinator.data.socket.evse_status
        if status is None:
            return None
        return str(status).lower() == CHARGING_STATE

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging on the wallbox."""
        # Already charging — idempotent no-op
        if self.is_on:
            _LOGGER.debug(
                "Switch turn_on called but already charging — skipping"
            )
            return

        try:
            _LOGGER.info(
                "Starting charge on wallbox %s", self._serial_number
            )
            await self._api_client.async_start_charge(self._serial_number)
            await self.coordinator.async_request_refresh()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed when starting charge. "
                "Please re-authenticate the Daze integration."
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                f"Failed to start charging: {err}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging on the wallbox."""
        if self.is_on is False or self.is_on is None:
            _LOGGER.debug(
                "Switch turn_off called but not charging — skipping"
            )
            return

        try:
            _LOGGER.info(
                "Stopping charge on wallbox %s", self._serial_number
            )
            await self._api_client.async_stop_charge(self._serial_number)
            await self.coordinator.async_request_refresh()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed when stopping charge. "
                "Please re-authenticate the Daze integration."
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                f"Failed to stop charging: {err}"
            ) from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DazeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daze Wallbox switch entity."""
    coordinator = entry.runtime_data.coordinator
    api_client = entry.runtime_data.api_client
    serial_number = entry.runtime_data.serial_number

    device_info = DeviceInfo(
        identifiers={(DOMAIN, serial_number)},
    )

    async_add_entities(
        [
            DazeWallboxSwitchEntity(
                coordinator=coordinator,
                api_client=api_client,
                serial_number=serial_number,
                device_info=device_info,
            )
        ]
    )
