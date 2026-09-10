"""Climate entity for ACIT ThermACEC."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
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

# ── The two axes, mapped onto the Home Assistant vocabulary ──────────────────
#
# The firmware publishes them separately (ACIT_SmartEnergy#142, rule R1) and they
# must NOT be flattened back here: `auto` says WHO decides, the target says WHAT is
# aimed at, and both coexist -- "AUTO, and the current slot aims at Comfort".
#
# Home Assistant has exactly the same split, which is why the model was chosen:
#   hvac_mode   <- who decides   : OFF / AUTO (a schedule runs) / HEAT (a fixed mode)
#   preset_mode <- what is aimed : comfort / eco / away(frost protection) / none(manual)
#
# The override does NOT become a preset. It is time-bound and superimposed on the
# mode -- turning it into a preset would lose both its deadline and the mode it
# will hand back to. It is exposed as attributes instead, which is the option
# question 6 of #142 leaves open.
#
# Machine names come from the firmware and are stable: the numeric values behind
# them are published (MQTT, Firestore, Modbus) and never renumbered.
_MODE_TO_PRESET: dict[str, str] = {
    "comfort": PRESET_COMFORT,
    "eco": PRESET_ECO,
    # Frost protection is the reduced setpoint of a prolonged absence, and the
    # Holiday override imposes it -- `away` is its Home Assistant counterpart.
    "frost_protection": PRESET_AWAY,
    # Manual means "a temperature set by hand, with no preset behind it", which is
    # precisely what PRESET_NONE means here.
    "manual": PRESET_NONE,
}
_PRESET_TO_MODE: dict[str, str] = {v: k for k, v in _MODE_TO_PRESET.items()}

# Modes that are an hvac_mode rather than a preset.
_MODE_OFF = "off"
_MODE_PROGRAM = "program"


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
    # `hvac_modes` and `preset_modes` are NOT class attributes any more: they are
    # built from what the device declares in Thermostat.GetConfig. A hardcoded list
    # would offer modes an older firmware rejects, and hide those a newer one gained.
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

        # What this device declares, resolved once at setup.
        declared: list[str] = device_info.get("operating_modes", []) or []
        self._declared_modes = declared

        features = ClimateEntityFeature.TARGET_TEMPERATURE
        hvac_modes = [HVACMode.HEAT]
        if _MODE_OFF in declared:
            hvac_modes.append(HVACMode.OFF)
        if _MODE_PROGRAM in declared:
            # AUTO is Home Assistant's "a schedule or learned behaviour decides",
            # which is exactly what the Programme mode means.
            hvac_modes.append(HVACMode.AUTO)
        self._attr_hvac_modes = hvac_modes

        presets = [_MODE_TO_PRESET[m] for m in declared if m in _MODE_TO_PRESET]
        if presets:
            # Keep a stable, readable order rather than the declaration order.
            wanted = [PRESET_COMFORT, PRESET_ECO, PRESET_AWAY, PRESET_NONE]
            self._attr_preset_modes = [p for p in wanted if p in presets]
            features |= ClimateEntityFeature.PRESET_MODE
        self._attr_supported_features = features

        if not declared:
            # A firmware older than the RPC mode contract, or a device with no
            # thermal axis: expose the temperature only, never invented modes.
            _LOGGER.debug(
                f"No operating_modes declared by {device_info.get('model')} - "
                f"exposing target temperature only"
            )

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
        """Return the current HVAC mode, read off the axis that decides.

        Not derived from `heater_level`: a device idling between two cycles is not
        off, and reporting HEAT unconditionally (as this did until now) said
        nothing at all.
        """
        operating = self.coordinator.data.get("operating")
        if operating == _MODE_OFF:
            return HVACMode.OFF
        if self.coordinator.data.get("auto"):
            return HVACMode.AUTO
        return HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        """Return the preset currently aimed at.

        In AUTO this is the target the running slot designates, not the mode name:
        that is the whole point of publishing two axes. While an override is
        running the preset stays the one being overridden -- the deviation shows up
        in the attributes, with its deadline.
        """
        if not self._attr_preset_modes:
            return None
        aimed = self.coordinator.data.get("target") or self.coordinator.data.get("operating")
        if aimed == _MODE_PROGRAM:
            # AUTO with no nameable target: a slot carrying a free temperature.
            # Saying "comfort" would be an invention.
            return None
        return _MODE_TO_PRESET.get(aimed)

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
        """Set the HVAC mode, i.e. choose who decides."""
        if hvac_mode == HVACMode.OFF:
            target = _MODE_OFF
        elif hvac_mode == HVACMode.AUTO:
            target = _MODE_PROGRAM
        else:
            # HEAT means "a fixed mode decides", and the range's default fixed mode
            # is Comfort -- it is also what AUTO falls back to outside any slot.
            # The previous mode is not remembered anywhere, so it cannot be restored.
            target = "comfort"

        if target not in self._declared_modes:
            _LOGGER.warning(f"HVAC mode {hvac_mode} maps to {target}, not declared by this device")
            return

        _LOGGER.debug(f"Setting HVAC mode {hvac_mode} -> operating mode {target}")
        await self.coordinator.async_set_operating_mode(target)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset, i.e. choose what is aimed at."""
        target = _PRESET_TO_MODE.get(preset_mode)
        if target is None or target not in self._declared_modes:
            _LOGGER.warning(f"Preset {preset_mode} is not available on this device")
            return

        _LOGGER.debug(f"Setting preset {preset_mode} -> operating mode {target}")
        await self.coordinator.async_set_operating_mode(target)

    @property
    def icon(self) -> str:
        """Return the entity icon."""
        return "mdi:thermostat"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes.

        The override lives here rather than in `preset_mode`, and the command
        origin with it: together they answer the question the field service asks at
        every visit -- "why is this device heating right now?". A preset alone
        cannot say "the occupant asked for 21 degrees, back to programme in 40 min".
        """
        attributes: dict[str, Any] = {
            "heater_level": self.coordinator.data.get("heater_level"),
            "fan_speed": self.coordinator.data.get("fan_speed"),
        }

        operating = self.coordinator.data.get("operating")
        if operating is not None:
            attributes["operating_mode"] = operating
            attributes["command_origin"] = self.coordinator.data.get("operating_origin")

        override = self.coordinator.data.get("override") or {}
        active = bool(override.get("active"))
        attributes["override_active"] = active
        if active:
            attributes["override_setpoint_c"] = override.get("setpoint_c")
            attributes["override_until"] = override.get("until")
            attributes["override_remaining_s"] = override.get("remaining_s")
            # The mode that will take over once it expires.
            attributes["override_mode"] = override.get("mode")
            attributes["override_origin"] = override.get("origin")

        return attributes
