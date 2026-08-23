"""Daze Cognito IDP authentication client (email/password flow)."""

from __future__ import annotations

import logging
import time
from typing import Any

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientError

from ..const import CLIENT_ID, COGNITO_IDP_URL
from .auth import AuthError, DazeAuthClient

_LOGGER = logging.getLogger(__name__)

_IDP_HEADERS = {
    "Content-Type": "application/x-amz-json-1.1",
    "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
}


class CognitoAuthError(AuthError):
    """Raised for Cognito IDP-specific auth failures."""

    def __init__(self, message: str, error_type: str | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type


class DazeCognitoAuthClient(DazeAuthClient):
    """Auth client using Cognito IDP InitiateAuth for login and refresh."""

    @classmethod
    async def async_authenticate(
        cls,
        session: ClientSession,
        email: str,
        password: str,
    ) -> DazeCognitoAuthClient:
        """Authenticate via Cognito IDP USER_PASSWORD_AUTH.

        Returns a fully-initialized client with valid tokens.
        """
        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": CLIENT_ID,
            "AuthParameters": {
                "USERNAME": email,
                "PASSWORD": password,
            },
        }

        _LOGGER.debug("Authenticating via Cognito IDP for %s", email)

        try:
            async with session.post(
                COGNITO_IDP_URL, headers=_IDP_HEADERS, json=payload
            ) as response:
                body: dict[str, Any] = await response.json(
                    content_type=None
                )

                if response.status != 200:
                    error_type = body.get("__type", "").rsplit("#", 1)[-1]
                    message = body.get("message", "Authentication failed")
                    _LOGGER.warning(
                        "Cognito IDP auth failed (%s): %s",
                        error_type,
                        message,
                    )
                    raise CognitoAuthError(message, error_type=error_type)

                result = body["AuthenticationResult"]
                access_token = result["AccessToken"]
                refresh_token = result["RefreshToken"]
                expires_in = result.get("ExpiresIn", 3600)

                _LOGGER.debug(
                    "Cognito IDP auth successful (expires in %ss)",
                    expires_in,
                )

                return cls(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expiry=time.time() + expires_in,
                )

        except CognitoAuthError:
            raise
        except ClientError as err:
            _LOGGER.warning("Network error during Cognito IDP auth: %s", err)
            raise CognitoAuthError(
                f"Network error during authentication: {err}",
                error_type="NetworkError",
            ) from err

    async def async_refresh_access_token(
        self, session: ClientSession
    ) -> str:
        """Refresh access token via Cognito IDP REFRESH_TOKEN_AUTH."""
        payload = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": CLIENT_ID,
            "AuthParameters": {
                "REFRESH_TOKEN": self._refresh_token,
            },
        }

        _LOGGER.debug("Refreshing access token via Cognito IDP")

        try:
            async with session.post(
                COGNITO_IDP_URL, headers=_IDP_HEADERS, json=payload
            ) as response:
                body: dict[str, Any] = await response.json(
                    content_type=None
                )

                if response.status != 200:
                    error_type = body.get("__type", "").rsplit("#", 1)[-1]
                    message = body.get("message", "Token refresh failed")
                    _LOGGER.warning(
                        "Cognito IDP refresh failed (%s): %s",
                        error_type,
                        message,
                    )
                    raise AuthError(
                        f"Cognito IDP token refresh failed ({error_type}): "
                        f"{message}"
                    )

                result = body["AuthenticationResult"]
                self._access_token = result["AccessToken"]
                expires_in = result.get("ExpiresIn", 3600)
                self._token_expiry = time.time() + expires_in

                _LOGGER.debug(
                    "Access token refreshed via IDP (expires in %ss)",
                    expires_in,
                )

                return self._access_token

        except AuthError:
            raise
        except ClientError as err:
            _LOGGER.warning(
                "Network error during Cognito IDP refresh: %s", err
            )
            raise AuthError(
                f"Network error during token refresh: {err}"
            ) from err
