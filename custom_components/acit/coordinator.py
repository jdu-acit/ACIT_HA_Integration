"""Coordinateur de données pour ACIT ThermACEC."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
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


class ACITThermACECCoordinator(DataUpdateCoordinator):
    """Coordinateur pour gérer les données ACIT ThermACEC via HTTP RPC + WebSocket."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialiser le coordinateur."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.entry = entry
        self._host = entry.data[CONF_HOST]
        self._port = entry.data.get(CONF_PORT, 80)
        self._rpc_id = 1

        # Session HTTP
        self._session: aiohttp.ClientSession | None = None

        # WebSocket
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_task: asyncio.Task | None = None
        self._ws_connected = False

        # Device info
        self._device_info: dict[str, Any] = {}

        # Données de l'appareil
        self.data: dict[str, Any] = {
            "temperature": None,
            "target_temperature": None,
            "heater_level": None,
            "fan_speed": None,
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
        """Retourner les informations de l'appareil."""
        return self._device_info

    async def async_config_entry_first_refresh(self) -> None:
        """Première actualisation lors de la configuration."""
        # Créer la session HTTP
        self._session = aiohttp.ClientSession()

        # Récupérer la configuration de l'appareil
        await self._async_get_device_config()

        # Vérifier les mises à jour OTA disponibles
        await self.async_check_ota_update()

        # Démarrer le WebSocket
        self._ws_task = self.hass.async_create_task(self._async_websocket_loop())

        # Première actualisation des données
        await super().async_config_entry_first_refresh()

    async def _async_rpc_call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Effectuer un appel RPC."""
        if self._session is None:
            raise UpdateFailed("Session HTTP non initialisée")

        url = f"http://{self._host}:{self._port}{RPC_ENDPOINT}"
        payload = {
            "jsonrpc": "2.0",
            "id": self._rpc_id,
            "method": method,
            "params": params or {},
        }
        self._rpc_id += 1

        _LOGGER.debug(f"Appel RPC: {method} - {params}")

        try:
            async with self._session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=RPC_TIMEOUT),
            ) as response:
                if response.status != 200:
                    raise UpdateFailed(f"Erreur HTTP {response.status}")

                result = await response.json()

                if "error" in result:
                    error = result["error"]
                    raise UpdateFailed(f"Erreur RPC: {error.get('message', 'Unknown error')}")

                _LOGGER.debug(f"Réponse RPC: {result.get('result')}")
                return result.get("result", {})

        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout lors de l'appel RPC: {method}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Erreur de connexion: {err}") from err

    async def _async_get_device_config(self) -> None:
        """Récupérer la configuration de l'appareil."""
        try:
            config = await self._async_rpc_call(RPC_METHOD_GET_CONFIG)
            self._device_info = {
                "model": config.get("model", "ThermACEC"),
                "version": config.get("version", "Unknown"),
                "manufacturer": config.get("manufacturer", "ACIT"),
                "mac_address": config.get("mac_address", ""),
                "min_temp": config.get("min_temp", 5),
                "max_temp": config.get("max_temp", 35),
                "features": config.get("features", []),
            }
            _LOGGER.info(f"Configuration appareil: {self._device_info}")
        except UpdateFailed as err:
            _LOGGER.error(f"Erreur lors de la récupération de la configuration: {err}")
            # Utiliser des valeurs par défaut
            self._device_info = {
                "model": "ThermACEC",
                "version": "Unknown",
                "manufacturer": "ACIT",
                "mac_address": "",
                "min_temp": 5,
                "max_temp": 35,
                "features": [],
            }

    async def _async_websocket_loop(self) -> None:
        """Boucle de connexion WebSocket."""
        while True:
            try:
                await self._async_connect_websocket()
            except asyncio.CancelledError:
                _LOGGER.debug("Tâche WebSocket annulée")
                break
            except Exception as err:
                _LOGGER.error(f"Erreur WebSocket: {err}")
                self._ws_connected = False
                self.data["available"] = False
                self.async_set_updated_data(self.data)

            # Attendre avant de reconnecter
            _LOGGER.info(f"Reconnexion WebSocket dans {WS_RECONNECT_DELAY}s...")
            await asyncio.sleep(WS_RECONNECT_DELAY)

    async def _async_connect_websocket(self) -> None:
        """Se connecter au WebSocket."""
        if self._session is None:
            return

        url = f"ws://{self._host}:{self._port}{WS_ENDPOINT}"
        _LOGGER.info(f"Connexion WebSocket à {url}")

        try:
            async with self._session.ws_connect(url) as ws:
                self._ws = ws
                self._ws_connected = True
                self.data["available"] = True
                self.async_set_updated_data(self.data)

                _LOGGER.info("WebSocket connecté")

                # Écouter les messages
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._async_handle_ws_message(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error(f"Erreur WebSocket: {ws.exception()}")
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        _LOGGER.warning("WebSocket fermé")
                        break

        except aiohttp.ClientError as err:
            _LOGGER.error(f"Erreur de connexion WebSocket: {err}")
            raise
        finally:
            self._ws = None
            self._ws_connected = False

    async def _async_handle_ws_message(self, message: str) -> None:
        """Traiter un message WebSocket."""
        try:
            data = json.loads(message)

            # Vérifier si c'est une notification
            if data.get("method") == WS_NOTIFY_STATUS:
                params = data.get("params", {})
                _LOGGER.debug(f"Notification reçue: {params}")

                # Mettre à jour les données
                self.data["temperature"] = params.get("temperature")
                self.data["target_temperature"] = params.get("target_temperature")
                self.data["heater_level"] = params.get("heater_level")
                self.data["fan_speed"] = params.get("fan_speed")
                self.data["available"] = True

                # Notifier les entités
                self.async_set_updated_data(self.data)

        except json.JSONDecodeError as err:
            _LOGGER.error(f"Erreur de décodage JSON: {err}")

    async def _async_update_data(self) -> dict[str, Any]:
        """Mettre à jour les données via RPC (fallback si WebSocket échoue)."""
        if self._ws_connected:
            # Si WebSocket est connecté, les données sont mises à jour automatiquement
            # Mais on vérifie quand même l'état OTA
            await self.async_get_ota_status()
            return self.data

        # Sinon, récupérer les données via RPC
        try:
            status = await self._async_rpc_call(RPC_METHOD_GET_STATUS)

            self.data["temperature"] = status.get("temperature")
            self.data["target_temperature"] = status.get("target_temperature")
            self.data["heater_level"] = status.get("heater_level")
            self.data["fan_speed"] = status.get("fan_speed")
            self.data["available"] = True

            # Vérifier l'état OTA
            await self.async_get_ota_status()

            return self.data

        except UpdateFailed as err:
            _LOGGER.error(f"Erreur lors de la mise à jour: {err}")
            self.data["available"] = False
            return self.data

    async def async_set_target_temperature(self, temperature: float) -> None:
        """Définir la température cible via RPC."""
        try:
            await self._async_rpc_call(
                RPC_METHOD_SET_TARGET_TEMP,
                {"temperature": temperature}
            )
            _LOGGER.info(f"Consigne définie à {temperature}°C")
        except UpdateFailed as err:
            _LOGGER.error(f"Erreur lors du changement de consigne: {err}")
            raise

    async def call_rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Appeler une méthode RPC (méthode publique pour les entités)."""
        return await self._async_rpc_call(method, params)

    async def async_check_ota_update(self) -> None:
        """Vérifier les mises à jour OTA disponibles."""
        try:
            result = await self._async_rpc_call("System.CheckUpdate")

            # Mettre à jour les données OTA
            self.data["ota"]["update_available"] = result.get("update_available", False)
            self.data["ota"]["available_version"] = result.get("version")
            self.data["ota"]["channel"] = result.get("channel", "stable")
            self.data["ota"]["size"] = result.get("size")
            self.data["ota"]["mandatory"] = result.get("mandatory", False)

            # Construire l'URL de release (GitHub)
            if self.data["ota"]["update_available"]:
                version = self.data["ota"]["available_version"]
                model = self._device_info.get("model", "ThermACEC").lower()
                self.data["ota"]["release_url"] = (
                    f"https://github.com/jdu-acit/ACIT_ACCU_{model.upper()}_OTA/releases/tag/v{version}"
                )

            _LOGGER.debug(f"Vérification OTA: {self.data['ota']}")

        except UpdateFailed as err:
            _LOGGER.error(f"Erreur lors de la vérification OTA: {err}")

    async def async_get_ota_status(self) -> None:
        """Récupérer l'état actuel de l'OTA."""
        try:
            result = await self._async_rpc_call("System.GetOTAStatus")

            self.data["ota"]["state"] = result.get("state", "idle")
            self.data["ota"]["progress"] = result.get("progress")

            _LOGGER.debug(f"État OTA: {result.get('state')} - {result.get('progress')}%")

        except UpdateFailed as err:
            _LOGGER.debug(f"Impossible de récupérer l'état OTA: {err}")

    async def async_shutdown(self) -> None:
        """Arrêter le coordinateur."""
        _LOGGER.debug("Arrêt du coordinateur")

        # Arrêter la tâche WebSocket
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        # Fermer le WebSocket
        if self._ws and not self._ws.closed:
            await self._ws.close()

        # Fermer la session HTTP
        if self._session and not self._session.closed:
            await self._session.close()
