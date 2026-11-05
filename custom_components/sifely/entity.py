"""Shared base entity for Sifely lock devices."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SifelyCoordinator


class SifelyLockEntity(CoordinatorEntity[SifelyCoordinator]):
    """Base for entities attached to one Sifely lock."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SifelyCoordinator, lock_id: int) -> None:
        super().__init__(coordinator)
        self._lock_id = lock_id

    @property
    def lock_data(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self._lock_id, {})

    @property
    def available(self) -> bool:
        return super().available and self._lock_id in (self.coordinator.data or {})

    @property
    def device_info(self) -> DeviceInfo:
        lock = self.lock_data.get("list", {})
        detail = self.lock_data.get("detail", {})
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._lock_id))},
            manufacturer="Sifely",
            model=lock.get("lockName"),
            name=lock.get("lockAlias") or lock.get("lockName") or f"Sifely {self._lock_id}",
            sw_version=detail.get("firmwareRevision"),
        )


class SifelyAccountEntity(CoordinatorEntity[SifelyCoordinator]):
    """Base for entities that describe the Sifely API account, not a lock."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SifelyCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"account_{entry_id}")},
            manufacturer="Sifely",
            name="Sifely API",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://connect.sifely.com",
        )
