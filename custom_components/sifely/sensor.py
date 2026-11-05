"""Sensor platform for Sifely smart locks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DEFAULT_CALL_QUOTA, DOMAIN
from .coordinator import SifelyCoordinator
from .entity import SifelyAccountEntity, SifelyLockEntity

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
    entities.append(SifelyCallsRemainingSensor(coordinator, entry.entry_id))
    entities.append(SifelyCallsUsedSensor(coordinator, entry.entry_id))
    entities.append(SifelyCallsByHomeAssistantSensor(coordinator, entry.entry_id))
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


# ── API usage ─────────────────────────────────────────────────────────────


class SifelyCallsRemainingSensor(SifelyAccountEntity, SensorEntity):
    """Calls left in the current billing cycle, from X-RateLimit-Remaining."""

    _attr_name = "Calls remaining"
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "calls"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SifelyCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_api_calls_remaining"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.client.calls_remaining

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        client = self.coordinator.client
        return {
            "call_quota": client.call_limit or DEFAULT_CALL_QUOTA,
            "quota_from_api": client.call_limit is not None,
            "device_count": client.device_count,
        }


class SifelyCallsUsedSensor(SifelyAccountEntity, SensorEntity):
    """Calls used in the current billing cycle (quota minus remaining).

    Counts every client using this API key, not only Home Assistant.
    """

    _attr_name = "Calls used this cycle"
    _attr_icon = "mdi:chart-bar"
    _attr_native_unit_of_measurement = "calls"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SifelyCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_api_calls_used"

    @property
    def native_value(self) -> int | None:
        client = self.coordinator.client
        if client.calls_remaining is None:
            return None
        quota = client.call_limit or DEFAULT_CALL_QUOTA
        return max(0, quota - client.calls_remaining)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        client = self.coordinator.client
        quota = client.call_limit or DEFAULT_CALL_QUOTA
        used = self.native_value
        return {
            "call_quota": quota,
            "percent_used": round(used * 100 / quota, 1) if used is not None else None,
        }


class SifelyCallsByHomeAssistantSensor(SifelyAccountEntity, RestoreSensor):
    """Running total of metered calls made by this integration.

    Survives restarts, so long-term statistics show calls per month.
    """

    _attr_name = "Calls by Home Assistant"
    _attr_icon = "mdi:home-import-outline"
    _attr_native_unit_of_measurement = "calls"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SifelyCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_api_calls_by_ha"
        self._base = 0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._base = int(float(last.native_value))
            except (TypeError, ValueError):
                self._base = 0

    @property
    def native_value(self) -> int:
        return self._base + self.coordinator.client.calls_made
