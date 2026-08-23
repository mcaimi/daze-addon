"""Init for Daze Wallbox integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .api import ApiAuthError, ApiError, DazeApiClient
from .const import (
    CONF_DEVICE_PROFILE,
    CONF_EVSE_NAME,
    CONF_FIRMWARE_VERSION,
    CONF_NETWORK_UID,
    CONF_SERIAL_NUMBER,
    CONF_SOFTWARE_VERSION,
    DOMAIN,
    PLATFORMS,
    SERVICE_SET_CHARGING_CURRENT,
    SERVICE_START_CHARGE,
    SERVICE_STOP_CHARGE,
)
from .coordinator import DazeDataUpdateCoordinator, async_setup_coordinator

from homeassistant.core import HomeAssistant, ServiceCall


@dataclass
class DazeRuntimeData:
    """Runtime data stored in the config entry."""

    coordinator: DazeDataUpdateCoordinator
    api_client: DazeApiClient
    serial_number: str
    network_uid: str


type DazeConfigEntry = ConfigEntry[DazeRuntimeData]

_LOGGER = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Service definitions
# ------------------------------------------------------------------

SET_CHARGING_CURRENT_SCHEMA = vol.Schema({
    vol.Required("current"): vol.All(
        cv.positive_int, vol.Range(min=6000, max=32000)
    ),
})


def _get_runtime_data(hass: HomeAssistant) -> DazeRuntimeData:
    """Resolve runtime data from the first loaded config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    for e in entries:
        if hasattr(e, "runtime_data") and e.runtime_data is not None:
            return e.runtime_data
    raise HomeAssistantError("No loaded Daze config entry found")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Daze Wallbox integration (services registration)."""

    async def _handle_start_charge(call: ServiceCall) -> None:
        """Start charging."""
        rd = _get_runtime_data(hass)
        try:
            await rd.api_client.async_start_charge(rd.serial_number)
            await rd.coordinator.async_request_refresh()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed when starting charge. "
                "Please re-authenticate the Daze integration."
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                f"Failed to start charging: {err}"
            ) from err

    async def _handle_stop_charge(call: ServiceCall) -> None:
        """Stop charging."""
        rd = _get_runtime_data(hass)
        try:
            await rd.api_client.async_stop_charge(rd.serial_number)
            await rd.coordinator.async_request_refresh()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed when stopping charge. "
                "Please re-authenticate the Daze integration."
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                f"Failed to stop charging: {err}"
            ) from err

    async def _handle_set_charging_current(call: ServiceCall) -> None:
        """Set the maximum charging current."""
        rd = _get_runtime_data(hass)
        current: int = call.data["current"]
        try:
            await rd.api_client.async_set_max_charging_current(
                rd.serial_number, current
            )
            await rd.coordinator.async_request_refresh()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed when setting charging current. "
                "Please re-authenticate the Daze integration."
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                f"Failed to set charging current: {err}"
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_CHARGE,
        _handle_start_charge,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_CHARGE,
        _handle_stop_charge,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CHARGING_CURRENT,
        _handle_set_charging_current,
        schema=SET_CHARGING_CURRENT_SCHEMA,
    )

    return True


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
