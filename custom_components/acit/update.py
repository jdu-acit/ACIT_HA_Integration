"""Entité Update pour ACIT ThermACEC - Mises à jour OTA."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ACITThermACECCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurer l'entité update ACIT."""
    coordinator: ACITThermACECCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Tous les appareils ACIT supportent l'OTA
    async_add_entities([ACITUpdateEntity(coordinator, entry)])


class ACITUpdateEntity(CoordinatorEntity, UpdateEntity):
    """Entité Update pour ACIT ThermACEC - Gestion OTA."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )
    _attr_has_entity_name = True
    _attr_translation_key = "firmware"

    def __init__(
        self,
        coordinator: ACITThermACECCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialiser l'entité update."""
        super().__init__(coordinator)
        device_info = coordinator.device_info
        mac_address = device_info.get("mac_address", entry.entry_id)

        self._attr_unique_id = f"{mac_address}_update"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac_address)},
            "name": entry.data.get("device_name", "ACIT ThermACEC"),
            "manufacturer": device_info.get("manufacturer", "ACIT"),
            "model": device_info.get("model", "ThermACEC"),
            "sw_version": device_info.get("version", "Unknown"),
        }

    @property
    def installed_version(self) -> str | None:
        """Version actuellement installée."""
        return self.coordinator.device_info.get("version")

    @property
    def latest_version(self) -> str | None:
        """Dernière version disponible."""
        ota_data = self.coordinator.data.get("ota", {})
        return ota_data.get("available_version")

    @property
    def release_summary(self) -> str | None:
        """Résumé de la release."""
        ota_data = self.coordinator.data.get("ota", {})
        if ota_data.get("update_available"):
            channel = ota_data.get("channel", "stable")
            return f"Nouvelle version disponible sur le canal {channel}"
        return None

    @property
    def release_url(self) -> str | None:
        """URL vers les notes de version complètes."""
        ota_data = self.coordinator.data.get("ota", {})
        return ota_data.get("release_url")

    @property
    def in_progress(self) -> bool | None:
        """Mise à jour en cours."""
        ota_data = self.coordinator.data.get("ota", {})
        state = ota_data.get("state", "idle")
        return state in ["checking", "downloading", "applying"]

    @property
    def update_percentage(self) -> int | None:
        """Progression de la mise à jour (0-100%)."""
        ota_data = self.coordinator.data.get("ota", {})
        return ota_data.get("progress")

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Installer une mise à jour OTA."""
        _LOGGER.info(
            "Démarrage de la mise à jour OTA vers la version %s",
            version or "latest"
        )

        try:
            # Appeler la méthode RPC System.StartOTA
            await self.coordinator.call_rpc("System.StartOTA", {})

            # Rafraîchir les données pour obtenir l'état
            await self.coordinator.async_request_refresh()

        except Exception as err:
            _LOGGER.error("Erreur lors du démarrage de l'OTA: %s", err)
            raise

    async def async_release_notes(self) -> str | None:
        """Retourner les notes de version complètes."""
        ota_data = self.coordinator.data.get("ota", {})

        notes = []
        notes.append(f"## Version {self.latest_version}\n")

        if channel := ota_data.get("channel"):
            notes.append(f"**Canal:** {channel}\n")

        if size := ota_data.get("size"):
            size_mb = size / (1024 * 1024)
            notes.append(f"**Taille:** {size_mb:.2f} MB\n")

        if mandatory := ota_data.get("mandatory"):
            if mandatory:
                notes.append("⚠️ **Mise à jour obligatoire**\n")

        notes.append("\n---\n")
        notes.append("La mise à jour sera téléchargée et installée automatiquement.")
        notes.append("\nL'appareil redémarrera après l'installation.")

        return "\n".join(notes)

