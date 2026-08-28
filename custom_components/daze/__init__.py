"""Init for Daze Wallbox integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pydaze import DazeApiClient

from .const import (
    CONF_DEVICE_PROFILE,
    CONF_EVSE_NAME,
    CONF_FIRMWARE_VERSION,
    CONF_NETWORK_UID,
    CONF_SERIAL_NUMBER,
    CONF_SOFTWARE_VERSION,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import DazeDataUpdateCoordinator, async_setup_coordinator


@dataclass
class DazeRuntimeData:
    """Runtime data stored in the config entry."""

    coordinator: DazeDataUpdateCoordinator
    api_client: DazeApiClient
    serial_number: str
    network_uid: str


type DazeConfigEntry = ConfigEntry[DazeRuntimeData]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: DazeConfigEntry) -> bool:
    """Set up Daze Wallbox from a config entry."""
    _LOGGER.debug("Setting up Daze Wallbox config entry %s", entry.entry_id)

    coordinator = await async_setup_coordinator(hass, entry)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[CONF_SERIAL_NUMBER])},
        manufacturer="Daze",
        model=entry.data.get(CONF_DEVICE_PROFILE),
        name=entry.data.get(CONF_EVSE_NAME, "Daze Wallbox"),
        sw_version=entry.data.get(CONF_SOFTWARE_VERSION),
        hw_version=entry.data.get(CONF_FIRMWARE_VERSION),
        configuration_url="https://webportal.dazeservice.com",
    )

    entry.runtime_data = DazeRuntimeData(
        coordinator=coordinator,
        api_client=coordinator.api_client,
        serial_number=entry.data[CONF_SERIAL_NUMBER],
        network_uid=entry.data[CONF_NETWORK_UID],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DazeConfigEntry) -> bool:
    """Unload a Daze Wallbox config entry."""
    _LOGGER.debug("Unloading Daze Wallbox config entry %s", entry.entry_id)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: DazeConfigEntry
) -> None:
    """Handle config entry update (e.g., re-auth token update)."""
    _LOGGER.debug("Config entry updated for %s — reloading", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)
