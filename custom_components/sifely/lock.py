"""Lock platform for Sifely smart locks."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SifelyError, SifelyGatewayRequiredError
from .const import DOMAIN, OPEN_STATE_LOCKED, OPEN_STATE_UNLOCKED
from .coordinator import SifelyCoordinator
from .entity import SifelyLockEntity

GATEWAY_MESSAGE = (
    "This lock is not connected to a Sifely gateway, so remote control is unavailable."
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SifelyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SifelyLock(coordinator, lock_id) for lock_id in coordinator.lock_ids())


class SifelyLock(SifelyLockEntity, LockEntity):
    """A Sifely lock. State is unknown until a gateway is connected."""

    _attr_name = None  # Use the device name as the entity name

    def __init__(self, coordinator: SifelyCoordinator, lock_id: int) -> None:
        super().__init__(coordinator, lock_id)
        self._attr_unique_id = f"{lock_id}_lock"

    @property
    def is_locked(self) -> bool | None:
        state = self.lock_data.get("open_state")
        if state == OPEN_STATE_LOCKED:
            return True
        if state == OPEN_STATE_UNLOCKED:
            return False
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lock = self.lock_data.get("list", {})
        detail = self.lock_data.get("detail", {})
        return {
            "battery": lock.get("electricQuantity"),
            "has_gateway": bool(lock.get("hasGateway")),
            "auto_lock_time": detail.get("autoLockTime"),
            "sound_volume": detail.get("soundVolume"),
            "passage_mode": detail.get("passageMode"),
            "firmware_revision": detail.get("firmwareRevision"),
        }

    async def async_lock(self, **kwargs: Any) -> None:
        await self._send(self.coordinator.client.lock(self._lock_id))

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._send(self.coordinator.client.unlock(self._lock_id))

    async def _send(self, call: Awaitable[None]) -> None:
        try:
            await call
        except SifelyGatewayRequiredError as err:
            raise HomeAssistantError(GATEWAY_MESSAGE) from err
        except SifelyError as err:
            raise HomeAssistantError(f"Sifely command failed: {err}") from err
        await self.coordinator.async_request_refresh()
