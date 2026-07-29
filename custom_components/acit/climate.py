"""Climate entity for ACIT ThermACEC."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MAX_TEMP, MIN_TEMP, TEMP_STEP
from .coordinator import ACITThermACECCoordinator
from .models import ACITFeature, get_model_name, get_supported_features

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ACIT ThermACEC climate entity."""
    coordinator: ACITThermACECCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Check if the device supports climate
    supported_features = get_supported_features(coordinator.device_info)

    # Create the climate entity only if supported
    if ACITFeature.TEMPERATURE in supported_features:
        async_add_entities([
            ACITThermACECClimate(coordinator, entry),
        ])
    else:
        _LOGGER.debug(
            f"Climate entity not created for {coordinator.device_info.get('model')} "
            f"(temperature feature not supported)"
        )


class ACITThermACECClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity for ACIT ThermACEC."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT]  # Simplified mode for v2.0
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = TEMP_STEP
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ACITThermACECCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        device_info = coordinator.device_info
        mac_address = device_info.get("mac_address", entry.entry_id)

        self._attr_unique_id = f"{mac_address}_climate"
        self._attr_translation_key = "thermacec"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac_address)},
            "name": entry.data.get("device_name", "ACIT ThermACEC"),
            "manufacturer": device_info.get("manufacturer", "ACIT"),
            "model": get_model_name(device_info.get("model")),
            "sw_version": device_info.get("version", "Unavailable"),
        }

        # Update temperature limits from device config
        if device_info:
            self._attr_min_temp = device_info.get("min_temp", MIN_TEMP)
            self._attr_max_temp = device_info.get("max_temp", MAX_TEMP)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.get("temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.coordinator.data.get("target_temperature")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        # For v2.0, simplified mode based on heater_level
        heater_level = self.coordinator.data.get("heater_level", 0)
        return HVACMode.HEAT if heater_level > 0 else HVACMode.HEAT

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.data.get("available", False)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        _LOGGER.debug(f"Setting target temperature: {temperature}°C")
        await self.coordinator.async_set_target_temperature(temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        # For v2.0, the mode is always HEAT (automatically managed by the device)
        _LOGGER.debug(f"HVAC mode: {hvac_mode} (automatically managed by the device)")

    @property
    def icon(self) -> str:
        """Return the entity icon."""
        return "mdi:thermostat"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "heater_level": self.coordinator.data.get("heater_level"),
            "fan_speed": self.coordinator.data.get("fan_speed"),
        }
