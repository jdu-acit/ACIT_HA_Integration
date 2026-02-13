"""ACIT ThermACEC Integration pour Home Assistant."""
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

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CLIMATE, Platform.UPDATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configurer l'intégration ACIT ThermACEC à partir d'une entrée de configuration."""
    _LOGGER.debug("Configuration de l'intégration ACIT ThermACEC")

    # Créer le coordinateur de données
    coordinator = ACITThermACECCoordinator(hass, entry)

    # Initialiser la connexion
    await coordinator.async_config_entry_first_refresh()

    # Stocker le coordinateur
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Enregistrer l'appareil
    device_info = coordinator.device_info
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_info.get("mac_address", entry.entry_id))},
        manufacturer=device_info.get("manufacturer", "ACIT"),
        name=entry.data.get("device_name", "ACIT ThermACEC"),
        model=device_info.get("model", "ThermACEC"),
        sw_version=device_info.get("version", "Unknown"),
    )

    # Configurer les plateformes
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Enregistrer les services
    async def async_check_update(call: ServiceCall) -> None:
        """Service pour vérifier manuellement les mises à jour."""
        device_id = call.data.get("device_id")

        if not device_id:
            _LOGGER.error("Aucun device_id fourni pour le service check_update")
            return

        # Récupérer le device registry pour trouver l'entry_id
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(device_id)

        if not device_entry:
            _LOGGER.error("Appareil non trouvé: %s", device_id)
            return

        # Trouver le coordinateur correspondant
        for entry_id in device_entry.config_entries:
            coordinator = hass.data[DOMAIN].get(entry_id)
            if coordinator and isinstance(coordinator, ACITThermACECCoordinator):
                await coordinator.async_check_ota_update()
                await coordinator.async_request_refresh()
                _LOGGER.info("Vérification des mises à jour OTA lancée pour %s", device_id)
                return

        _LOGGER.error("Coordinateur non trouvé pour l'appareil: %s", device_id)

    hass.services.async_register(DOMAIN, "check_update", async_check_update)

    _LOGGER.info("Intégration ACIT ThermACEC configurée avec succès")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharger une entrée de configuration."""
    _LOGGER.debug("Déchargement de l'intégration ACIT ThermACEC")

    # Décharger les plateformes
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Arrêter le coordinateur
        coordinator: ACITThermACECCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()

        # Supprimer les données
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharger l'entrée de configuration."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

