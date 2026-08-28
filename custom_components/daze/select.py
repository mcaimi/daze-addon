"""Select platform for Daze Wallbox.

Exposes a select entity to choose the wallbox operation mode: fast, eco,
or scheduled. Fast mode disables eco mode, eco mode enables it, and
scheduled mode is reserved for future schedule-based control.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pydaze import ApiAuthError, ApiError

from .const import DOMAIN
from .coordinator import DazeDataUpdateCoordinator
from .models import DazeCoordinatorData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DazeConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Operation mode options exposed in the HA frontend
OPTION_FAST = "fast"
OPTION_ECO = "eco"
OPTION_SCHEDULED = "scheduled"

ATTR_OPTIONS = [OPTION_FAST, OPTION_ECO, OPTION_SCHEDULED]

OPERATION_MODE_MAP: dict[int, str] = {
    1: OPTION_ECO,
    2: OPTION_SCHEDULED,
    3: OPTION_FAST,
}


def _current_option_from_data(data: DazeCoordinatorData) -> str:
    """Derive the current operation mode from coordinator data.

    Uses ``ecoModeEnabled`` and ``operationMode`` fields to determine
    the current mode:
    - ``ecoModeEnabled`` is True → eco mode
    - ``operationMode`` integer maps via OPERATION_MODE_MAP

    Falls back to "fast" if no data is available.
    """
    eco_enabled = data.socket.eco_mode_enabled
    if eco_enabled is True:
        return OPTION_ECO

    mode = data.socket.operation_mode
    if mode is not None:
        mapped = OPERATION_MODE_MAP.get(mode)
        if mapped is not None:
            return mapped
        _LOGGER.warning(
            "Unknown operationMode value %r from API; defaulting to 'fast'",
            mode,
        )

    return OPTION_FAST


_MODE_TO_ECO: dict[str, bool | None] = {
    OPTION_FAST: False,
    OPTION_ECO: True,
    OPTION_SCHEDULED: None,  # not yet mapped to an API call
}


class DazeWallboxSelectEntity(
    CoordinatorEntity[DazeDataUpdateCoordinator], SelectEntity
):
    """Select entity to choose the Daze wallbox operation mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "operation_mode"
    _attr_options = ATTR_OPTIONS

    def __init__(
        self,
        coordinator: DazeDataUpdateCoordinator,
        api_client: Any,
        serial_number: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialise the select entity.

        Args:
            coordinator: The Daze data coordinator.
            api_client: The Daze API client.
            serial_number: The wallbox serial number.
            device_info: Device info for the wallbox device registry.

        """
        super().__init__(coordinator)
        self._api_client = api_client
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_operation_mode"
        self._attr_device_info = device_info

    @property
    def current_option(self) -> str | None:
        """Return the current operation mode."""
        if self.coordinator.data is None:
            return None
        return _current_option_from_data(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        """Set the operation mode on the wallbox.

        Maps the selected option to the appropriate API call:
        - "fast" → disables eco mode
        - "eco" → enables eco mode
        - "scheduled" → currently unsupported, shows notification
        """
        if option not in ATTR_OPTIONS:
            _LOGGER.warning(
                "Unknown operation mode option: %s", option
            )
            return

        eco_value = _MODE_TO_ECO.get(option)
        if eco_value is None:
            raise HomeAssistantError(
                "Scheduled operation mode is not yet supported via the "
                "Daze API. Please use 'Fast' or 'Eco' mode."
            )

        try:
            _LOGGER.info(
                "Setting operation mode to '%s' on wallbox %s "
                "(ecoModeEnabled=%s)",
                option,
                self._serial_number,
                eco_value,
            )
            await self._api_client.async_set_eco_mode(
                self._serial_number, eco_value
            )
            await self.coordinator.async_request_refresh()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed when setting operation mode. "
                "Please re-authenticate the Daze integration."
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                f"Failed to set operation mode: {err}"
            ) from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DazeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daze Wallbox select entity."""
    coordinator = entry.runtime_data.coordinator
    api_client = entry.runtime_data.api_client
    serial_number = entry.runtime_data.serial_number

    device_info = DeviceInfo(
        identifiers={(DOMAIN, serial_number)},
    )

    async_add_entities(
        [
            DazeWallboxSelectEntity(
                coordinator=coordinator,
                api_client=api_client,
                serial_number=serial_number,
                device_info=device_info,
            )
        ]
    )
