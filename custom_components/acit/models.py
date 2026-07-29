"""ACIT device model definitions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

_LOGGER = logging.getLogger(__name__)


class ACITModel(StrEnum):
    """Supported ACIT device models.

    The values are the identifiers announced by the firmware itself, in
    ``Thermostat.GetConfig`` (field ``model``), in the mDNS TXT record and in
    ``/api/v1/discovery`` (field ``deviceType``). They are matched exactly --
    see :func:`resolve_model`.
    """

    ACCU = "ACCU_ThermACEC"
    NOS = "NOS_ThermACEC"
    EMS = "EMS_ThermACEC"
    ACCUBLOC = "AccuBloc_ThermACEC"
    PREHEATER = "PreHeater_ThermACEC"
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

    # Features the hardware is known not to have. A device announcing one of
    # these is not believed: firmware feature lists get copied between products
    # and go stale, and an entity that reports a fan on a fanless device is
    # worse than a missing entity.
    unsupported_features: list[ACITFeature] = field(default_factory=list)


# Model configurations
#
# A profile must describe what the product physically has. Declaring a feature
# the hardware lacks creates entities that report nothing -- a fan speed on a
# convector, for instance.
MODEL_CONFIGS: dict[str, ACITModelConfig] = {
    # Heat-storage radiator: fan-assisted discharge of a storage core.
    ACITModel.ACCU: ACITModelConfig(
        model=ACITModel.ACCU,
        name="ACCU-ThermACEC",
        supports_climate=True,
        supports_energy=False,
        default_features=[
            ACITFeature.TEMPERATURE,
            ACITFeature.TARGET_TEMPERATURE,
            ACITFeature.HEATING,
            ACITFeature.FAN,
            ACITFeature.CORE_CHARGE,
        ],
        icon="mdi:radiator",
    ),
    # Convector: heating elements only. No fan, no storage core.
    ACITModel.NOS: ACITModelConfig(
        model=ACITModel.NOS,
        name="NOS-ThermACEC",
        supports_climate=True,
        supports_energy=False,
        default_features=[
            ACITFeature.TEMPERATURE,
            ACITFeature.TARGET_TEMPERATURE,
            ACITFeature.HEATING,
        ],
        icon="mdi:heat-wave",
        unsupported_features=[
            ACITFeature.FAN,
            ACITFeature.CORE_CHARGE,
            ACITFeature.COOLING,
        ],
    ),
    ACITModel.ACCUBLOC: ACITModelConfig(
        model=ACITModel.ACCUBLOC,
        name="AccuBloc-ThermACEC",
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
        name="EMS-ThermACEC",
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
    # Unknown hardware: claim nothing beyond what every ACIT device reports.
    # Anything more would be a guess, and a guess is what produced ghost fan
    # and core-charge entities on convectors.
    ACITModel.UNKNOWN: ACITModelConfig(
        model=ACITModel.UNKNOWN,
        name="ThermACEC",
        supports_climate=True,
        supports_energy=False,
        default_features=[
            ACITFeature.TEMPERATURE,
            ACITFeature.TARGET_TEMPERATURE,
        ],
        icon="mdi:thermostat",
    ),
}


# Identifiers used before the firmware exposed a product prefix. Config entries
# created by earlier versions of this integration still carry them.
# "ThermACEC" was only ever served by the storage radiator.
_LEGACY_ALIASES: dict[str, ACITModel] = {
    "thermacec": ACITModel.ACCU,
    "accubloc": ACITModel.ACCUBLOC,
    "ems": ACITModel.EMS,
}


def _normalize(model_name: str) -> str:
    """Reduce an identifier to its comparable form (case and separators)."""
    return model_name.strip().lower().replace("-", "_")


def resolve_model(model_name: str | None) -> ACITModel:
    """Resolve a firmware model string to a known model.

    Matching is exact once case and separators are normalized. Partial matching
    is deliberately not used: "ThermACEC" is a substring of every product name,
    so it would map a convector onto the storage-radiator profile.

    An unrecognized identifier returns :attr:`ACITModel.UNKNOWN` and is logged.
    """
    if not model_name:
        _LOGGER.warning("No model reported by the device, using a minimal profile")
        return ACITModel.UNKNOWN

    normalized = _normalize(model_name)

    for model in ACITModel:
        if _normalize(model.value) == normalized:
            return model

    if (legacy := _LEGACY_ALIASES.get(normalized)) is not None:
        _LOGGER.debug("Legacy model identifier '%s' mapped to %s", model_name, legacy)
        return legacy

    _LOGGER.warning(
        "Unknown device model '%s', using a minimal profile. "
        "Supported models: %s",
        model_name,
        ", ".join(m.value for m in ACITModel if m is not ACITModel.UNKNOWN),
    )
    return ACITModel.UNKNOWN


def get_model_config(model_name: str) -> ACITModelConfig:
    """Get the configuration for a model."""
    return MODEL_CONFIGS[resolve_model(model_name)]


def get_model_name(model_name: str | None) -> str:
    """Human-readable product name, for the device registry and forms."""
    return MODEL_CONFIGS[resolve_model(model_name)].name


def get_supported_features(device_info: dict[str, Any]) -> list[ACITFeature]:
    """Determine the features supported by a device."""
    model_config = get_model_config(device_info.get("model", ""))

    # Start with the model's default features
    features = list(model_config.default_features)

    # Add features declared by the device. A device may legitimately gain
    # capabilities the integration does not know about yet -- except those its
    # profile rules out.
    device_features = device_info.get("features", [])
    for feature in device_features:
        try:
            acit_feature = ACITFeature(feature)
        except ValueError:
            # Unknown feature, skip
            continue

        if acit_feature in model_config.unsupported_features:
            _LOGGER.warning(
                "Device %s announces feature '%s', which this model does not have. "
                "Ignoring it -- the firmware feature list is likely inherited from "
                "another product.",
                model_config.name,
                acit_feature,
            )
            continue

        if acit_feature not in features:
            features.append(acit_feature)

    return features
