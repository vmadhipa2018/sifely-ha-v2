"""Sensor platform for Sifely smart locks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import SifelyCoordinator
from .entity import SifelyLockEntity

RECENT_ACTIVITY_COUNT = 10


def _ms_to_datetime(ms: int | None) -> datetime | None:
    if not ms:
        return None
    return dt_util.utc_from_timestamp(ms / 1000)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SifelyCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for lock_id in coordinator.lock_ids():
        entities.append(SifelyBatterySensor(coordinator, lock_id))
        entities.append(SifelyPasscodeCountSensor(coordinator, lock_id))
        entities.append(SifelyLastActivitySensor(coordinator, lock_id))
    async_add_entities(entities)


class SifelyBatterySensor(SifelyLockEntity, SensorEntity):
    """Battery percentage, refreshed hourly from the lock list."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Battery"

    def __init__(self, coordinator: SifelyCoordinator, lock_id: int) -> None:
        super().__init__(coordinator, lock_id)
        self._attr_unique_id = f"{lock_id}_battery"

    @property
    def native_value(self) -> int | None:
        return self.lock_data.get("list", {}).get("electricQuantity")


class SifelyPasscodeCountSensor(SifelyLockEntity, SensorEntity):
    """Number of passcodes on the lock. Codes themselves are never exposed."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Passcodes"
    _attr_icon = "mdi:keypad"

    def __init__(self, coordinator: SifelyCoordinator, lock_id: int) -> None:
        super().__init__(coordinator, lock_id)
        self._attr_unique_id = f"{lock_id}_passcode_count"

    @property
    def native_value(self) -> int | None:
        if "passcodes" not in self.lock_data:
            return None
        return len(self.lock_data.get("passcodes") or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "passcodes": [
                {
                    "name": p.get("keyboardPwdName"),
                    "type": p.get("keyboardPwdType"),
                    "start_date": _ms_to_datetime(p.get("startDate")),
                    "end_date": _ms_to_datetime(p.get("endDate")),
                }
                for p in self.lock_data.get("passcodes") or []
            ]
        }


class SifelyLastActivitySensor(SifelyLockEntity, SensorEntity):
    """Time of the most recent lock event, with recent history as attributes."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "Last activity"
    _attr_icon = "mdi:history"

    def __init__(self, coordinator: SifelyCoordinator, lock_id: int) -> None:
        super().__init__(coordinator, lock_id)
        self._attr_unique_id = f"{lock_id}_last_activity"

    @property
    def native_value(self) -> datetime | None:
        records = self.lock_data.get("records") or []
        if not records:
            return None
        latest = max(records, key=lambda r: r.get("lockDate") or 0)
        return _ms_to_datetime(latest.get("lockDate"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        records = self.lock_data.get("records") or []
        return {
            "recent_activity": [
                {
                    "time": _ms_to_datetime(r.get("lockDate")),
                    "record_type": r.get("recordType"),
                    "user": r.get("username"),
                    "success": bool(r.get("success")),
                }
                for r in records[:RECENT_ACTIVITY_COUNT]
            ]
        }
