"""Définitions des modèles d'appareils ACIT."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ACITModel(StrEnum):
    """Modèles d'appareils ACIT supportés."""

    THERMACEC = "ThermACEC"
    ACCUBLOC = "Accubloc"
    EMS = "EMS"
    UNKNOWN = "Unknown"


class ACITFeature(StrEnum):
    """Features disponibles sur les appareils ACIT."""

    # Climat
    TEMPERATURE = "temperature"
    TARGET_TEMPERATURE = "target_temperature"
    HEATING = "heating"
    COOLING = "cooling"
    FAN = "fan"

    # Énergie (EMS)
    POWER_MONITORING = "power_monitoring"
    ENERGY_IMPORT = "energy_import"
    ENERGY_EXPORT = "energy_export"
    BATTERY = "battery"
    SOLAR = "solar"

    # Contrôle (EMS)
    RELAY_CONTROL = "relay_control"
    LOAD_SHEDDING = "load_shedding"


@dataclass
class ACITModelConfig:
    """Configuration d'un modèle d'appareil ACIT."""

    model: ACITModel
    name: str
    supports_climate: bool
    supports_energy: bool
    default_features: list[ACITFeature]
    icon: str


# Configurations des modèles
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
    """Récupérer la configuration d'un modèle."""
    # Normaliser le nom du modèle
    model_name = model_name.strip()

    # Chercher une correspondance exacte
    if model_name in MODEL_CONFIGS:
        return MODEL_CONFIGS[model_name]

    # Chercher une correspondance partielle (case-insensitive)
    model_name_lower = model_name.lower()
    for key, config in MODEL_CONFIGS.items():
        if key.lower() in model_name_lower or model_name_lower in key.lower():
            return config

    # Modèle inconnu - utiliser ThermACEC par défaut
    return MODEL_CONFIGS[ACITModel.THERMACEC]


def get_supported_features(device_info: dict[str, Any]) -> list[ACITFeature]:
    """Déterminer les features supportées par un appareil."""
    model_name = device_info.get("model", "ThermACEC")
    model_config = get_model_config(model_name)

    # Commencer avec les features par défaut du modèle
    features = list(model_config.default_features)

    # Ajouter les features déclarées par l'appareil
    device_features = device_info.get("features", [])
    for feature in device_features:
        try:
            acit_feature = ACITFeature(feature)
            if acit_feature not in features:
                features.append(acit_feature)
        except ValueError:
            # Feature inconnue, ignorer
            pass

    return features

