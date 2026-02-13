"""Capteurs pour ACIT ThermACEC."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ACITThermACECCoordinator
from .models import ACITFeature

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ACITSensorEntityDescription(SensorEntityDescription):
    """Describes ACIT sensor entity."""

    exists_fn: Callable[[dict[str, Any]], bool] = lambda _: True
    value_fn: Callable[[dict[str, Any]], StateType]
    required_feature: ACITFeature | None = None


# Définition de tous les capteurs disponibles
SENSORS: tuple[ACITSensorEntityDescription, ...] = (
    # Capteurs climat (ThermACEC, Accubloc)
    ACITSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        exists_fn=lambda data: data.get("temperature") is not None,
        value_fn=lambda data: data.get("temperature"),
        required_feature=ACITFeature.TEMPERATURE,
    ),
    ACITSensorEntityDescription(
        key="target_temperature",
        translation_key="target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        exists_fn=lambda data: data.get("target_temperature") is not None,
        value_fn=lambda data: data.get("target_temperature"),
        required_feature=ACITFeature.TARGET_TEMPERATURE,
    ),
    ACITSensorEntityDescription(
        key="heater_level",
        translation_key="heater_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        exists_fn=lambda data: data.get("heater_level") is not None,
        value_fn=lambda data: data.get("heater_level"),
        required_feature=ACITFeature.HEATING,
    ),
    ACITSensorEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        exists_fn=lambda data: data.get("fan_speed") is not None,
        value_fn=lambda data: data.get("fan_speed"),
        required_feature=ACITFeature.FAN,
    ),
    # Capteurs énergie (EMS)
    ACITSensorEntityDescription(
        key="power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        exists_fn=lambda data: data.get("power") is not None,
        value_fn=lambda data: data.get("power"),
        required_feature=ACITFeature.POWER_MONITORING,
    ),
    ACITSensorEntityDescription(
        key="energy_import",
        translation_key="energy_import",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        exists_fn=lambda data: data.get("energy_import") is not None,
        value_fn=lambda data: data.get("energy_import"),
        required_feature=ACITFeature.ENERGY_IMPORT,
    ),
    ACITSensorEntityDescription(
        key="energy_export",
        translation_key="energy_export",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        exists_fn=lambda data: data.get("energy_export") is not None,
        value_fn=lambda data: data.get("energy_export"),
        required_feature=ACITFeature.ENERGY_EXPORT,
    ),
    ACITSensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        exists_fn=lambda data: data.get("battery_level") is not None,
        value_fn=lambda data: data.get("battery_level"),
        required_feature=ACITFeature.BATTERY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurer les capteurs ACIT."""
    coordinator: ACITThermACECCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Récupérer les features supportées par l'appareil
    from .models import get_supported_features
    supported_features = get_supported_features(coordinator.device_info)

    _LOGGER.debug(
        f"Configuration des capteurs pour {coordinator.device_info.get('model')} "
        f"avec features: {supported_features}"
    )

    # Créer les entités selon les features supportées
    entities = []
    for description in SENSORS:
        # Vérifier si la feature est requise et supportée
        if description.required_feature is not None:
            if description.required_feature not in supported_features:
                _LOGGER.debug(
                    f"Capteur {description.key} ignoré (feature {description.required_feature} non supportée)"
                )
                continue

        # Vérifier si les données existent
        if description.exists_fn(coordinator.data):
            entities.append(ACITSensorEntity(coordinator, entry, description))

    async_add_entities(entities)


class ACITSensorEntity(CoordinatorEntity, SensorEntity):
    """Représente un capteur ACIT ThermACEC."""

    entity_description: ACITSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ACITThermACECCoordinator,
        entry: ConfigEntry,
        entity_description: ACITSensorEntityDescription,
    ) -> None:
        """Initialiser le capteur."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        device_info = coordinator.device_info
        mac_address = device_info.get("mac_address", entry.entry_id)

        self._attr_unique_id = f"{mac_address}_{entity_description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac_address)},
            "name": entry.data.get("device_name", "ACIT ThermACEC"),
            "manufacturer": device_info.get("manufacturer", "ACIT"),
            "model": device_info.get("model", "ThermACEC"),
            "sw_version": device_info.get("version", "Unknown"),
        }

    @property
    def native_value(self) -> StateType:
        """Retourner la valeur du capteur."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Retourner si l'entité est disponible."""
        return (
            self.coordinator.data.get("available", False)
            and self.native_value is not None
        )

