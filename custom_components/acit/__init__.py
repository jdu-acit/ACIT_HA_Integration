"""ACIT ThermACEC Integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import ACITThermACECCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CLIMATE, Platform.UPDATE, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the ACIT ThermACEC integration from a config entry."""
    _LOGGER.debug("Setting up ACIT ThermACEC integration")

    # Create the data coordinator
    coordinator = ACITThermACECCoordinator(hass, entry)

    # Initialize the connection
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register the device
    device_info = coordinator.device_info
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_info.get("mac_address", entry.entry_id))},
        manufacturer=device_info.get("manufacturer", "ACIT"),
        name=entry.data.get("device_name", "ACIT ThermACEC"),
        model=device_info.get("model", "ThermACEC"),
        sw_version=device_info.get("version", "Unavailable"),
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def async_check_update(call: ServiceCall) -> None:
        """Service to manually check for OTA updates."""
        device_id = call.data.get("device_id")

        if not device_id:
            _LOGGER.error("No device_id provided for check_update service")
            return

        # Get the device registry to find the entry_id
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(device_id)

        if not device_entry:
            _LOGGER.error("Device not found: %s", device_id)
            return

        # Find the corresponding coordinator
        for entry_id in device_entry.config_entries:
            coordinator = hass.data[DOMAIN].get(entry_id)
            if coordinator and isinstance(coordinator, ACITThermACECCoordinator):
                await coordinator.async_check_ota_update()
                await coordinator.async_request_refresh()
                _LOGGER.info("OTA update check triggered for %s", device_id)
                return

        _LOGGER.error("Coordinator not found for device: %s", device_id)

    hass.services.async_register(DOMAIN, "check_update", async_check_update)

    _LOGGER.info("ACIT ThermACEC integration set up successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading ACIT ThermACEC integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Shut down the coordinator
        coordinator: ACITThermACECCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()

        # Remove the data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

