"""Data coordinator for ACIT ThermACEC."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    RPC_ENDPOINT,
    RPC_METHOD_GET_CONFIG,
    RPC_METHOD_GET_STATUS,
    RPC_METHOD_SET_TARGET_TEMP,
    RPC_TIMEOUT,
    UPDATE_INTERVAL,
    WS_ENDPOINT,
    WS_NOTIFY_STATUS,
    WS_RECONNECT_DELAY,
)

_LOGGER = logging.getLogger(__name__)

# GitHub asset URL announced by the device, e.g.
# https://github.com/<owner>/<repo>/releases/download/<tag>/<file>.bin
_GITHUB_ASSET_URL = re.compile(
    r"^(?P<repo>https://github\.com/[^/]+/[^/]+)/releases/download/(?P<tag>[^/]+)/"
)


def _release_page_url(asset_url: str | None) -> str | None:
    """Derive the release page from the binary URL the device reports.

    The device is the authority on where its firmware comes from -- it is the
    one that downloads it. Building the URL from the model name here produced
    links to repositories that never existed.

    Returns None when the URL has an unexpected shape: no link is better than a
    dead one.
    """
    if not asset_url:
        return None

    if (match := _GITHUB_ASSET_URL.match(asset_url)) is None:
        _LOGGER.debug("OTA URL '%s' is not a GitHub asset, no release link", asset_url)
        return None

    return f"{match['repo']}/releases/tag/{match['tag']}"


class ACITThermACECCoordinator(DataUpdateCoordinator):
    """Coordinator to manage ACIT ThermACEC data via HTTP RPC + WebSocket."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.entry = entry
        self._host = entry.data[CONF_HOST]
        self._port = entry.data.get(CONF_PORT, 80)
        self._token: str | None = entry.data.get(CONF_TOKEN)
        self._rpc_id = 1

        # HTTP session
        self._session: aiohttp.ClientSession | None = None

        # WebSocket
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_task: asyncio.Task | None = None
        self._ws_connected = False

        # Device info
        self._device_info: dict[str, Any] = {}

        # Consecutive error counter
        self._consecutive_errors = 0
        self._max_consecutive_errors = 3  # Max errors before marking as unavailable

        # Device data
        self.data: dict[str, Any] = {
            "temperature": None,
            "target_temperature": None,
            "heater_level": None,
            "fan_speed": None,
            "core_charge_pct": None,
            "available": False,
            "ota": {
                "update_available": False,
                "available_version": None,
                "state": "idle",
                "progress": None,
                "channel": "stable",
                "size": None,
                "mandatory": False,
                "release_url": None,
            },
        }

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self._device_info

    async def async_config_entry_first_refresh(self) -> None:
        """First refresh during setup."""
        # Create HTTP session
        self._session = aiohttp.ClientSession()

        # Retrieve device configuration
        await self._async_get_device_config()

        # Check for available OTA updates
        await self.async_check_ota_update()

        # Start WebSocket
        self._ws_task = self.hass.async_create_task(self._async_websocket_loop())

        # First data refresh
        await super().async_config_entry_first_refresh()

    async def _async_rpc_call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Effectuer un appel RPC."""
        if self._session is None:
            raise UpdateFailed("HTTP session not initialized")

        url = f"http://{self._host}:{self._port}{RPC_ENDPOINT}"
        payload = {
            "jsonrpc": "2.0",
            "id": self._rpc_id,
            "method": method,
            "params": params or {},
        }
        self._rpc_id += 1

        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        _LOGGER.debug(f"RPC call: {method} - {params}")

        try:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=RPC_TIMEOUT),
            ) as response:
                if response.status == 401:
                    _LOGGER.warning("Device rejected the token — re-pairing required")
                    self.entry.async_start_reauth(self.hass)
                    raise UpdateFailed("Authorization required — re-pair the device")

                if response.status != 200:
                    raise UpdateFailed(f"HTTP error {response.status}")

                result = await response.json()

                if "error" in result:
                    error = result["error"]
                    raise UpdateFailed(f"RPC error: {error.get('message', 'Unknown error')}")

                _LOGGER.debug(f"RPC response: {result.get('result')}")
                return result.get("result", {})

        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"RPC call timeout: {method}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

    async def _async_get_device_config(self) -> None:
        """Retrieve device configuration."""
        try:
            config = await self._async_rpc_call(RPC_METHOD_GET_CONFIG)

            # Log raw response for debug
            _LOGGER.info(f"Raw Thermostat.GetConfig response: {config}")

            # Check if version is present
            version = config.get("version")
            if version:
                _LOGGER.info(f"✅ Firmware version received: {version}")
            else:
                _LOGGER.warning(f"⚠️ No firmware version in response! Full response: {config}")

            self._device_info = {
                # No default: an unnamed device resolves to the minimal profile
                # rather than silently inheriting the storage-radiator one.
                "model": config.get("model", ""),
                "version": config.get("version", "Unavailable"),
                "manufacturer": config.get("manufacturer", "ACIT"),
                "mac_address": config.get("mac_address", ""),
                "min_temp": config.get("min_temp", 5),
                "max_temp": config.get("max_temp", 35),
                "features": config.get("features", []),
            }
            _LOGGER.info(f"Device configuration: {self._device_info}")
        except UpdateFailed as err:
            _LOGGER.error(f"Error retrieving device configuration: {err}")
            # Use default values
            self._device_info = {
                "model": "",
                "version": "Unavailable",
                "manufacturer": "ACIT",
                "mac_address": "",
                "min_temp": 5,
                "max_temp": 35,
                "features": [],
            }

    async def _async_websocket_loop(self) -> None:
        """WebSocket connection loop."""
        while True:
            try:
                await self._async_connect_websocket()
            except asyncio.CancelledError:
                _LOGGER.debug("WebSocket task cancelled")
                break
            except Exception as err:
                _LOGGER.error(f"WebSocket error: {err}")
                self._ws_connected = False
                self.data["available"] = False
                self.async_set_updated_data(self.data)

            # Wait before reconnecting
            _LOGGER.info(f"Reconnecting WebSocket in {WS_RECONNECT_DELAY}s...")
            await asyncio.sleep(WS_RECONNECT_DELAY)

    async def _async_connect_websocket(self) -> None:
        """Connect to the WebSocket."""
        if self._session is None:
            return

        token_param = f"?token={self._token}" if self._token else ""
        url = f"ws://{self._host}:{self._port}{WS_ENDPOINT}{token_param}"
        _LOGGER.info(f"Connecting WebSocket to ws://{self._host}:{self._port}{WS_ENDPOINT}")

        try:
            async with self._session.ws_connect(url) as ws:
                self._ws = ws
                self._ws_connected = True
                self.data["available"] = True
                self.async_set_updated_data(self.data)

                _LOGGER.info("WebSocket connected")

                # Listen for messages
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._async_handle_ws_message(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error(f"WebSocket error: {ws.exception()}")
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        _LOGGER.warning("WebSocket closed")
                        break

        except aiohttp.ClientError as err:
            _LOGGER.error(f"WebSocket connection error: {err}")
            raise
        finally:
            self._ws = None
            self._ws_connected = False

    async def _async_handle_ws_message(self, message: str) -> None:
        """Handle a WebSocket message."""
        try:
            data = json.loads(message)

            # Check if it's a notification
            if data.get("method") == WS_NOTIFY_STATUS:
                params = data.get("params", {})
                _LOGGER.debug(f"Notification received: {params}")

                # Update data
                self.data["temperature"] = params.get("temperature")
                self.data["target_temperature"] = params.get("target_temperature")
                self.data["heater_level"] = params.get("heater_level")
                self.data["fan_speed"] = params.get("fan_speed")
                self.data["core_charge_pct"] = params.get("core_charge_pct")
                self.data["available"] = True

                # Notify entities
                self.async_set_updated_data(self.data)

        except json.JSONDecodeError as err:
            _LOGGER.error(f"JSON decode error: {err}")

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via RPC (fallback if WebSocket fails)."""
        if self._ws_connected:
            # If WebSocket is connected, data is updated automatically
            # But we still check OTA status
            await self.async_get_ota_status()
            return self.data

        # Otherwise, fetch data via RPC
        try:
            status = await self._async_rpc_call(RPC_METHOD_GET_STATUS)

            self.data["temperature"] = status.get("temperature")
            self.data["target_temperature"] = status.get("target_temperature")
            self.data["heater_level"] = status.get("heater_level")
            self.data["fan_speed"] = status.get("fan_speed")
            self.data["core_charge_pct"] = status.get("core_charge_pct")
            self.data["available"] = True

            # Check OTA status
            await self.async_get_ota_status()

            return self.data

        except UpdateFailed as err:
            _LOGGER.error(f"Error during data update: {err}")
            self.data["available"] = False
            return self.data

    async def async_set_target_temperature(self, temperature: float) -> None:
        """Set the target temperature via RPC."""
        try:
            await self._async_rpc_call(
                RPC_METHOD_SET_TARGET_TEMP,
                {"temperature": temperature}
            )
            _LOGGER.info(f"Target temperature set to {temperature}°C")
        except UpdateFailed as err:
            _LOGGER.error(f"Error changing target temperature: {err}")
            raise

    async def call_rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call an RPC method (public method for entities)."""
        return await self._async_rpc_call(method, params)

    async def async_check_ota_update(self) -> None:
        """Check for available OTA updates."""
        try:
            result = await self._async_rpc_call("System.CheckUpdate")

            # Field names as returned by System.CheckUpdate:
            #   ok, available, current_version, latest_version, channel, url,
            #   size, sha256
            self.data["ota"]["update_available"] = result.get("available", False)
            self.data["ota"]["available_version"] = result.get("latest_version")
            self.data["ota"]["channel"] = result.get("channel") or "stable"
            self.data["ota"]["size"] = result.get("size")
            self.data["ota"]["mandatory"] = result.get("mandatory", False)

            # Release page, derived from the URL the device itself reports.
            self.data["ota"]["release_url"] = _release_page_url(result.get("url"))

            _LOGGER.debug(f"OTA check: {self.data['ota']}")

        except UpdateFailed as err:
            _LOGGER.error(f"Error checking OTA update: {err}")

    async def async_get_ota_status(self) -> None:
        """Retrieve the current OTA status."""
        try:
            result = await self._async_rpc_call("System.GetOTAStatus")

            self.data["ota"]["state"] = result.get("state", "idle")
            self.data["ota"]["progress"] = result.get("progress")

            _LOGGER.debug(f"OTA status: {result.get('state')} - {result.get('progress')}%")

        except UpdateFailed as err:
            _LOGGER.debug(f"Unable to retrieve OTA status: {err}")

    async def async_shutdown(self) -> None:
        """Shut down the coordinator."""
        _LOGGER.debug("Shutting down coordinator")

        # Stop the WebSocket task
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        # Close the WebSocket
        if self._ws and not self._ws.closed:
            await self._ws.close()

        # Close the HTTP session
        if self._session and not self._session.closed:
            await self._session.close()
