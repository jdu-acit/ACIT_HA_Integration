"""ACIT device model definitions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ACITModel(StrEnum):
    """Supported ACIT device models."""

    THERMACEC = "ThermACEC"
    ACCUBLOC = "Accubloc"
    EMS = "EMS"
    UNKNOWN = "Unknown"


class ACITFeature(StrEnum):
    """Features available on ACIT devices."""

    # Climate
    TEMPERATURE = "temperature"
    TARGET_TEMPERATURE = "target_temperature"
    HEATING = "heating"
    COOLING = "cooling"
    FAN = "fan"
    CORE_CHARGE = "core_charge"

    # Energy (EMS)
    POWER_MONITORING = "power_monitoring"
    ENERGY_IMPORT = "energy_import"
    ENERGY_EXPORT = "energy_export"
    BATTERY = "battery"
    SOLAR = "solar"

    # Control (EMS)
    RELAY_CONTROL = "relay_control"
    LOAD_SHEDDING = "load_shedding"


@dataclass
class ACITModelConfig:
    """Configuration for an ACIT device model."""

    model: ACITModel
    name: str
    supports_climate: bool
    supports_energy: bool
    default_features: list[ACITFeature]
    icon: str


# Model configurations
MODEL_CONFIGS: dict[str, ACITModelConfig] = {
    ACITModel.THERMACEC: ACITModelConfig(
        model=ACITModel.THERMACEC,
        name="ThermACEC",
        supports_climate=True,
        supports_energy=False,
        default_features=[
            ACITFeature.TEMPERATURE,
            ACITFeature.TARGET_TEMPERATURE,
            ACITFeature.HEATING,
            ACITFeature.FAN,
            ACITFeature.CORE_CHARGE,
        ],
        icon="mdi:thermostat",
    ),
    ACITModel.ACCUBLOC: ACITModelConfig(
        model=ACITModel.ACCUBLOC,
        name="Accubloc",
        supports_climate=True,
        supports_energy=False,
        default_features=[
            ACITFeature.TEMPERATURE,
            ACITFeature.TARGET_TEMPERATURE,
            ACITFeature.HEATING,
            ACITFeature.COOLING,
            ACITFeature.FAN,
        ],
        icon="mdi:thermostat-box",
    ),
    ACITModel.EMS: ACITModelConfig(
        model=ACITModel.EMS,
        name="EMS",
        supports_climate=False,
        supports_energy=True,
        default_features=[
            ACITFeature.POWER_MONITORING,
            ACITFeature.ENERGY_IMPORT,
            ACITFeature.ENERGY_EXPORT,
            ACITFeature.RELAY_CONTROL,
        ],
        icon="mdi:lightning-bolt",
    ),
}


def get_model_config(model_name: str) -> ACITModelConfig:
    """Get the configuration for a model."""
    # Normalize the model name
    model_name = model_name.strip()

    # Look for an exact match
    if model_name in MODEL_CONFIGS:
        return MODEL_CONFIGS[model_name]

    # Look for a partial match (case-insensitive)
    model_name_lower = model_name.lower()
    for key, config in MODEL_CONFIGS.items():
        if key.lower() in model_name_lower or model_name_lower in key.lower():
            return config

    # Unknown model - default to ThermACEC
    return MODEL_CONFIGS[ACITModel.THERMACEC]


def get_supported_features(device_info: dict[str, Any]) -> list[ACITFeature]:
    """Determine the features supported by a device."""
    model_name = device_info.get("model", "ThermACEC")
    model_config = get_model_config(model_name)

    # Start with the model's default features
    features = list(model_config.default_features)

    # Add features declared by the device
    device_features = device_info.get("features", [])
    for feature in device_features:
        try:
            acit_feature = ACITFeature(feature)
            if acit_feature not in features:
                features.append(acit_feature)
        except ValueError:
            # Unknown feature, skip
            pass

    return features

