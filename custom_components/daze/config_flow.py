"""Config flow for Daze Wallbox integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pydaze import (
    AuthError,
    CognitoAuthError,
    DazeApiClient,
    DazeAuthClient,
    DazeCognitoAuthClient,
    Network,
)

from .const import (
    AUTH_METHOD_CREDENTIALS,
    AUTH_METHOD_TOKEN,
    CONF_ACCESS_TOKEN,
    CONF_AUTH_METHOD,
    CONF_DEVICE_PROFILE,
    CONF_EMAIL,
    CONF_EVSE_NAME,
    CONF_FIRMWARE_VERSION,
    CONF_NETWORK_NAME,
    CONF_NETWORK_UID,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_SERIAL_NUMBER,
    CONF_SOFTWARE_VERSION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_TOKEN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Required(CONF_REFRESH_TOKEN): str,
    }
)

STEP_CREDENTIALS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _map_cognito_error(error_type: str | None) -> str:
    """Map a Cognito IDP error type to a config flow error key."""
    mapping = {
        "NotAuthorizedException": "invalid_credentials",
        "UserNotFoundException": "invalid_credentials",
        "UserNotConfirmedException": "user_not_confirmed",
        "PasswordResetRequiredException": "password_reset_required",
        "TooManyRequestsException": "too_many_requests",
    }
    return mapping.get(error_type or "", "unknown")


async def _validate_tokens(
    hass: HomeAssistant, access_token: str, refresh_token: str
) -> dict[str, Any]:
    """Validate tokens and return user info.

    Returns a dict with keys:
        - "email": the user's email address
        - "access_token", "refresh_token" (passed through)

    Raises vol.Invalid if validation fails.
    """
    session = async_get_clientsession(hass)
    auth_client = DazeAuthClient(access_token, refresh_token)

    try:
        await auth_client.async_validate_tokens(session)
    except AuthError as err:
        _LOGGER.warning("Token validation failed: %s", err)
        raise vol.Invalid("invalid_token") from err

    # Fetch user info to get the email address
    api = DazeApiClient(auth_client, session)
    user_info = await api.async_get_user_info()

    return {
        "email": user_info.get("email", ""),
        CONF_ACCESS_TOKEN: access_token,
        CONF_REFRESH_TOKEN: refresh_token,
    }


async def _fetch_networks(
    hass: HomeAssistant,
    api_client: DazeApiClient,
    email: str,
) -> list[Network]:
    """Fetch available networks for the user."""
    try:
        return await api_client.async_get_networks(email)
    except Exception as err:
        _LOGGER.error("Failed to fetch networks: %s", err)
        raise vol.Invalid("network_error") from err


class DazeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Daze Wallbox."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the config flow."""
        self._auth_method: str | None = None
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._email: str | None = None
        self._password: str | None = None
        self._networks: list[Network] = []
        self._network_uid: str | None = None
        self._network_name: str | None = None
        self._evse_name: str | None = None
        self._serial_number: str | None = None
        self._device_profile: str | None = None
        self._firmware_version: str | None = None
        self._software_version: str | None = None

    # ------------------------------------------------------------------
    # Step 1: Auth method selection
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — auth method selection."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["credentials", "token"],
        )

    # ------------------------------------------------------------------
    # Step 1a: Email/password authentication
    # ------------------------------------------------------------------

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle email/password authentication via Cognito IDP."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            try:
                session = async_get_clientsession(self.hass)
                auth_client = await DazeCognitoAuthClient.async_authenticate(
                    session, email, password
                )
            except CognitoAuthError as err:
                errors["base"] = _map_cognito_error(err.error_type)
            except Exception:
                _LOGGER.exception("Unexpected error during credential auth")
                errors["base"] = "network_error"
            else:
                tokens = auth_client.get_tokens_for_store()
                self._auth_method = AUTH_METHOD_CREDENTIALS
                self._access_token = tokens["access_token"]
                self._refresh_token = tokens["refresh_token"]
                self._email = email
                self._password = password
                return await self.async_step_network()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_EMAIL, default=self._email or vol.UNDEFINED
                ): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        if self.source == SOURCE_REAUTH:
            self.context["title_placeholders"] = {
                "name": self._get_reauth_entry().title
            }

        return self.async_show_form(
            step_id="credentials",
            data_schema=schema,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 1b: Token entry
    # ------------------------------------------------------------------

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle access/refresh token authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN]
            refresh_token = user_input[CONF_REFRESH_TOKEN]

            try:
                info = await _validate_tokens(
                    self.hass, access_token, refresh_token
                )
            except vol.Invalid as err:
                errors["base"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected error during token validation")
                errors["base"] = "network_error"
            else:
                self._auth_method = AUTH_METHOD_TOKEN
                self._access_token = info[CONF_ACCESS_TOKEN]
                self._refresh_token = info[CONF_REFRESH_TOKEN]
                self._email = info["email"]
                return await self.async_step_network()

        if self.source == SOURCE_REAUTH:
            self.context["title_placeholders"] = {
                "name": self._get_reauth_entry().title
            }

        return self.async_show_form(
            step_id="token",
            data_schema=STEP_TOKEN_DATA_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Auth client helper
    # ------------------------------------------------------------------

    def _create_auth_client(self) -> DazeAuthClient:
        """Create the appropriate auth client for the selected method."""
        if self._auth_method == AUTH_METHOD_CREDENTIALS:
            return DazeCognitoAuthClient(
                self._access_token, self._refresh_token  # type: ignore[arg-type]
            )
        return DazeAuthClient(
            self._access_token, self._refresh_token  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------------
    # Step 2: Network selection
    # ------------------------------------------------------------------

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the network selection step."""
        errors: dict[str, str] = {}

        # Fetch networks on first load
        if not self._networks:
            session = async_get_clientsession(self.hass)
            auth_client = self._create_auth_client()
            api_client = DazeApiClient(auth_client, session)

            try:
                self._networks = await _fetch_networks(
                    self.hass, api_client, self._email  # type: ignore[arg-type]
                )
            except vol.Invalid as err:
                errors["base"] = str(err)
                return self.async_show_form(
                    step_id="network",
                    data_schema=vol.Schema({}),
                    errors=errors,
                )
            except Exception:
                _LOGGER.exception(
                    "Unexpected error fetching networks"
                )
                errors["base"] = "network_error"
                return self.async_show_form(
                    step_id="network",
                    data_schema=vol.Schema({}),
                    errors=errors,
                )

            if not self._networks:
                errors["base"] = "no_networks"
                return self.async_show_form(
                    step_id="network",
                    data_schema=vol.Schema({}),
                    errors=errors,
                )

        if user_input is not None:
            self._network_uid = user_input[CONF_NETWORK_UID]
            # Find the network name from the selected UID
            for net in self._networks:
                if net.uid == self._network_uid:
                    self._network_name = net.name or ""
                    break

            return await self.async_step_confirm()

        # Build selector options from available networks
        network_options = {
            net.uid: net.name or "Unknown"
            for net in self._networks
        }

        network_schema = vol.Schema(
            {
                vol.Required(CONF_NETWORK_UID): vol.In(network_options),
            }
        )

        return self.async_show_form(
            step_id="network",
            data_schema=network_schema,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 3: Confirmation
    # ------------------------------------------------------------------

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the confirmation step — fetches EVSE info and creates the entry."""
        errors: dict[str, str] = {}

        if user_input is not None or self._serial_number:
            # Apply the user-chosen device name from the form field
            if user_input is not None and CONF_EVSE_NAME in user_input:
                self._evse_name = user_input[CONF_EVSE_NAME]

            # Create the config entry
            data = {
                CONF_AUTH_METHOD: self._auth_method or AUTH_METHOD_TOKEN,
                CONF_ACCESS_TOKEN: self._access_token,
                CONF_REFRESH_TOKEN: self._refresh_token,
                CONF_EMAIL: self._email,
                CONF_NETWORK_UID: self._network_uid,
                CONF_NETWORK_NAME: self._network_name,
                CONF_EVSE_NAME: self._evse_name,
                CONF_SERIAL_NUMBER: self._serial_number,
                CONF_DEVICE_PROFILE: self._device_profile,
                CONF_FIRMWARE_VERSION: self._firmware_version,
                CONF_SOFTWARE_VERSION: self._software_version,
            }
            if self._auth_method == AUTH_METHOD_CREDENTIALS and self._password:
                data[CONF_PASSWORD] = self._password

            if self.source == SOURCE_REAUTH:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=data
                )

            # Set unique ID to prevent duplicate entries
            await self.async_set_unique_id(self._serial_number)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._evse_name or "Daze Wallbox",
                data=data,
            )

        # Fetch EVSE info to populate confirmation details
        session = async_get_clientsession(self.hass)
        auth_client = self._create_auth_client()
        api_client = DazeApiClient(auth_client, session)

        try:
            evses = await api_client.async_get_evses(self._network_uid)  # type: ignore[arg-type]
        except Exception:
            _LOGGER.exception("Failed to fetch EVSEs for confirmation")
            errors["base"] = "network_error"
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        if not evses:
            errors["base"] = "no_evses"
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        evse = evses[0]
        original_evse_name = evse.evse_name or "Daze Wallbox"
        self._evse_name = f"{original_evse_name} Daze"
        self._serial_number = evse.serial_number or ""
        self._device_profile = evse.device_profile or ""
        self._firmware_version = evse.firmware_version or ""
        self._software_version = evse.software_version or ""

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_EVSE_NAME, default=self._evse_name
                ): str,
            }),
            description_placeholders={
                "network_name": self._network_name or "",
                "evse_name": original_evse_name,
                "serial_number": self._serial_number,
                "device_profile": self._device_profile,
            },
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Re-authentication
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication — routes to the correct auth step."""
        self._auth_method = entry_data.get(
            CONF_AUTH_METHOD, AUTH_METHOD_TOKEN
        )
        self._email = entry_data.get(CONF_EMAIL)
        if self._auth_method == AUTH_METHOD_CREDENTIALS:
            return await self.async_step_credentials()
        return await self.async_step_token()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return DazeOptionsFlowHandler()


class DazeOptionsFlowHandler(OptionsFlow):
    """Handle Daze Wallbox options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
