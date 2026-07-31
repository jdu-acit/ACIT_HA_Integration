"""Update entity for ACIT ThermACEC - OTA updates."""
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
from .models import get_model_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ACIT update entity."""
    coordinator: ACITThermACECCoordinator = hass.data[DOMAIN][entry.entry_id]

    # All ACIT devices support OTA
    async_add_entities([ACITUpdateEntity(coordinator, entry)])


class ACITUpdateEntity(CoordinatorEntity, UpdateEntity):
    """Update entity for ACIT ThermACEC - OTA management."""

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
        """Initialize the update entity."""
        super().__init__(coordinator)
        device_info = coordinator.device_info
        mac_address = device_info.get("mac_address", entry.entry_id)

        self._attr_unique_id = f"{mac_address}_update"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac_address)},
            "name": entry.data.get("device_name", "ACIT ThermACEC"),
            "manufacturer": device_info.get("manufacturer", "ACIT"),
            "model": get_model_name(device_info.get("model")),
            "sw_version": device_info.get("version", "Unavailable"),
        }

    @property
    def installed_version(self) -> str | None:
        """Currently installed version."""
        version = self.coordinator.device_info.get("version")
        _LOGGER.debug(f"Update entity - installed_version called, version = {version}")
        _LOGGER.debug(f"Update entity - full device_info = {self.coordinator.device_info}")

        # Return None if no valid version (Home Assistant will show "unknown")
        if not version or version == "Unavailable":
            _LOGGER.warning("No valid firmware version found in device_info")
            return None

        return version

    @property
    def latest_version(self) -> str | None:
        """Latest available version."""
        ota_data = self.coordinator.data.get("ota", {})
        available_version = ota_data.get("available_version")

        # If no update is available, return the current version
        # so the entity state is "off" instead of "unknown"
        if not available_version:
            return self.installed_version

        return available_version

    @property
    def release_summary(self) -> str | None:
        """Release summary."""
        ota_data = self.coordinator.data.get("ota", {})
        if ota_data.get("update_available"):
            channel = ota_data.get("channel", "stable")
            return f"New version available on the {channel} channel"
        return None

    # No release_url property, deliberately.
    #
    # The OTA server only serves files: it returns 404 on a directory, so there
    # is no page to link to. The previous implementation derived a GitHub release
    # page from the binary URL, which stopped meaning anything when the fleet
    # moved to the ACIT server -- and became a broken link the day the release
    # repository went private (ACIT_SmartEnergy#28).
    #
    # What the user needs before installing -- which version, from which channel,
    # how large, which fingerprint -- is in async_release_notes() below. The day
    # System.CheckUpdate reports a notes URL of its own, showing it is three
    # lines; inventing one is what this removes.

    @property
    def in_progress(self) -> bool | None:
        """Whether an update is in progress."""
        ota_data = self.coordinator.data.get("ota", {})
        state = ota_data.get("state", "idle")
        return state in ["checking", "downloading", "applying"]

    @property
    def update_percentage(self) -> int | None:
        """Update progress (0-100%)."""
        ota_data = self.coordinator.data.get("ota", {})
        return ota_data.get("progress")

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an OTA update."""
        _LOGGER.info(
            "Starting OTA update to version %s",
            version or "latest"
        )

        try:
            # Call the System.StartOTA RPC method
            await self.coordinator.call_rpc("System.StartOTA", {})

            # Refresh data to get the current state
            await self.coordinator.async_request_refresh()

        except Exception as err:
            _LOGGER.error("Error starting OTA update: %s", err)
            raise

    async def async_release_notes(self) -> str | None:
        """Return what is known about the pending update.

        These are not release notes in the usual sense -- nobody writes any --
        but they answer the question the dialog actually raises: what am I about
        to install? Every value here is reported by the device itself.
        """
        ota_data = self.coordinator.data.get("ota", {})

        notes = [f"## Version {self.latest_version}\n"]

        if channel := ota_data.get("channel"):
            notes.append(f"**Channel:** {channel}\n")

        if size := ota_data.get("size"):
            size_mb = size / (1024 * 1024)
            notes.append(f"**Size:** {size_mb:.2f} MB\n")

        # Short fingerprint: enough to tell two builds apart, and to match what
        # the OTA server publishes. The device verifies the full hash against the
        # manifest before switching partitions.
        if sha256 := ota_data.get("sha256"):
            notes.append(f"**Fingerprint:** `{sha256[:12]}`\n")

        notes.append("\n---\n")
        notes.append("The update will be downloaded and installed automatically.")
        notes.append("\nThe device will restart after installation.")

        return "\n".join(notes)

