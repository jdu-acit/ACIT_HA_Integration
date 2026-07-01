"""Number entity for ACIT ThermACEC — target temperature setpoint."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MAX_TEMP, MIN_TEMP, TEMP_STEP
from .coordinator import ACITThermACECCoordinator
from .models import ACITFeature, get_supported_features

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ACIT number entities."""
    coordinator: ACITThermACECCoordinator = hass.data[DOMAIN][entry.entry_id]

    supported_features = get_supported_features(coordinator.device_info)

    if ACITFeature.TARGET_TEMPERATURE in supported_features:
        async_add_entities([ACITTargetTemperatureNumber(coordinator, entry)])


class ACITTargetTemperatureNumber(CoordinatorEntity, NumberEntity):
    """Number entity for the target temperature setpoint."""

    _attr_has_entity_name = True
    _attr_translation_key = "target_temperature_setpoint"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX
    _attr_native_step = TEMP_STEP
    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(
        self,
        coordinator: ACITThermACECCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        device_info = coordinator.device_info
        mac_address = device_info.get("mac_address", entry.entry_id)

        self._attr_unique_id = f"{mac_address}_target_temperature_setpoint"
        self._attr_native_min_value = device_info.get("min_temp", MIN_TEMP)
        self._attr_native_max_value = device_info.get("max_temp", MAX_TEMP)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac_address)},
            "name": entry.data.get("device_name", "ACIT ThermACEC"),
            "manufacturer": device_info.get("manufacturer", "ACIT"),
            "model": device_info.get("model", "ThermACEC"),
            "sw_version": device_info.get("version", "Unavailable"),
        }

    @property
    def native_value(self) -> float | None:
        """Return the current target temperature."""
        return self.coordinator.data.get("target_temperature")

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return (
            self.coordinator.data.get("available", False)
            and self.native_value is not None
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the target temperature."""
        _LOGGER.debug(f"Setting target temperature setpoint: {value}°C")
        await self.coordinator.async_set_target_temperature(value)
