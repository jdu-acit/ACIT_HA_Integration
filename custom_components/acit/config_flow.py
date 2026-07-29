"""Config flow for ACIT ThermaControl."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    RPC_ENDPOINT,
    RPC_METHOD_GET_CONFIG,
    RPC_METHOD_REQUEST_TOKEN,
    RPC_TIMEOUT,
)
from .models import MODEL_CONFIGS, resolve_model

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


class NotAuthorizedError(Exception):
    """Raised when the device requires authorization (no valid token)."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    """Validate user input by testing the RPC connection."""
    host = data[CONF_HOST]
    port = data.get(CONF_PORT, DEFAULT_PORT)

    url = f"http://{host}:{port}{RPC_ENDPOINT}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": RPC_METHOD_GET_CONFIG,
        "params": {},
    }
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=RPC_TIMEOUT),
            ) as response:
                if response.status == 401:
                    raise NotAuthorizedError()

                if response.status != 200:
                    raise ValueError(f"HTTP error {response.status}")

                result = await response.json()

                if "error" in result:
                    raise ValueError(f"RPC error: {result['error'].get('message')}")

                config = result.get("result", {})
                mac_address = config.get("mac_address", "")
                # No default here: an unnamed device must resolve to the minimal
                # profile, not silently inherit the storage-radiator one.
                model = config.get("model", "")

                return {
                    "title": data[CONF_NAME],
                    "mac_address": mac_address,
                    "model": model,
                }

    except asyncio.TimeoutError as err:
        raise ValueError("Connection timeout") from err
    except aiohttp.ClientError as err:
        raise ValueError(f"Connection error: {err}") from err


async def request_token(host: str, port: int) -> str | None:
    """Request a pairing token from the device.

    The device must be in provisioning mode (activated via its menu).
    Returns the token string on success, or None if not in provisioning mode.
    """
    url = f"http://{host}:{port}{RPC_ENDPOINT}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": RPC_METHOD_REQUEST_TOKEN,
        "params": {},
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=RPC_TIMEOUT),
            ) as response:
                if response.status != 200:
                    return None

                result = await response.json()

                if "error" in result:
                    return None

                return result.get("result", {}).get("token")

    except Exception:
        return None


class ACITThermaControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for ACIT ThermaControl."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, dict[str, Any]] = {}
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._name: str = DEFAULT_NAME
        # Product identifier announced by the device; empty until discovery.
        self._model: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user-initiated step."""
        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manual configuration by IP address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input.get(CONF_PORT, DEFAULT_PORT)
            self._name = user_input[CONF_NAME]

            try:
                info = await validate_input(self.hass, user_input)
            except NotAuthorizedError:
                return await self.async_step_authorize()
            except ValueError as err:
                _LOGGER.error(f"Validation error: {err}")
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during validation")
                errors["base"] = "unknown"
            else:
                mac_address = info.get("mac_address", self._host)
                await self.async_set_unique_id(mac_address)
                self._abort_if_unique_id_configured()

                user_input["device_name"] = self._name
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "name": DEFAULT_NAME,
                "host": "10.0.0.41",
                "port": str(DEFAULT_PORT),
            },
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Provisioning step: user activates pairing mode on the device, then confirms."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = await request_token(self._host, self._port)

            if token is None:
                errors["base"] = "authorization_failed"
            else:
                data = {
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_NAME: self._name,
                    CONF_TOKEN: token,
                    "device_name": self._name,
                }
                try:
                    info = await validate_input(self.hass, data, token=token)
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    mac_address = info.get("mac_address", self._host)
                    await self.async_set_unique_id(mac_address)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=info["title"], data=data)

        return self.async_show_form(step_id="authorize", errors=errors)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle re-auth when the stored token is rejected by the device."""
        self._host = entry_data[CONF_HOST]
        self._port = entry_data.get(CONF_PORT, DEFAULT_PORT)
        self._name = entry_data.get(CONF_NAME, DEFAULT_NAME)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-pairing by requesting a new token from the device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = await request_token(self._host, self._port)

            if token is None:
                errors["base"] = "authorization_failed"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_TOKEN: token},
                )

        return self.async_show_form(step_id="reauth_confirm", errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle Zeroconf/mDNS discovery."""
        _LOGGER.info(f"ACIT device discovered via mDNS: {discovery_info}")

        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        hostname = discovery_info.hostname

        # Extract device name from hostname
        device_name = hostname.replace(".local.", "").replace("_", " ").title()

        # The mDNS TXT record carries the product identifier (model=NOS_ThermACEC,
        # ACCU_ThermACEC, ...). Use it rather than assuming a product.
        properties = discovery_info.properties or {}
        self._model = properties.get("model") or ""

        self._host = host
        self._port = port
        self._name = device_name

        # Use host as a temporary unique_id until we can read the MAC after pairing
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": device_name}

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery, then proceed to pairing."""
        if user_input is not None:
            return await self.async_step_authorize()

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self._name,
                "host": self._host,
                "model": MODEL_CONFIGS[resolve_model(self._model)].name,
            },
        )

