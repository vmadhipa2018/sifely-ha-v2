"""Tiered polling coordinator for Sifely locks (Open API).

One coordinator wakes every COORDINATOR_INTERVAL seconds. Each data category
(lock list, detail, records, passcodes, open state) runs only when its own
interval has elapsed, so the call budget stays predictable.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any, Awaitable, TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SifelyAuthError,
    SifelyClient,
    SifelyError,
    SifelyGatewayRequiredError,
    SifelyRateLimitError,
    SifelySubscriptionError,
)
from .const import (
    COORDINATOR_INTERVAL,
    DETAIL_FIELDS,
    DETAIL_INTERVAL,
    DOMAIN,
    EVENT_ACTIVITY,
    LIST_INTERVAL,
    PASSCODE_FIELDS,
    PASSCODE_INTERVAL,
    RECORD_FIELDS,
    RECORD_INTERVAL,
    STATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


def _pick(source: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Keep only allowlisted fields so secrets never reach memory or attributes."""
    return {key: source[key] for key in fields if key in source}


def _empty_cache() -> dict[str, Any]:
    return {
        "list": {},
        "detail": {},
        "passcodes": [],
        "records": [],
        "open_state": None,
    }


class SifelyCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Polls the Sifely API on tiered schedules."""

    def __init__(self, hass: HomeAssistant, client: SifelyClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=COORDINATOR_INTERVAL),
        )
        self.client = client
        self._locks: list[dict[str, Any]] = []
        self._cache: dict[int, dict[str, Any]] = {}
        self._last_run: dict[str, float] = {}
        self._last_record_id: dict[int, int] = {}

    # ── Public helpers ──────────────────────────────────────────────────────

    def lock_ids(self) -> list[int]:
        return [int(lock["lockId"]) for lock in self._locks]

    # ── Scheduling helpers ──────────────────────────────────────────────────

    def _due(self, key: str, interval: int) -> bool:
        last = self._last_run.get(key)
        return last is None or time.monotonic() - last >= interval

    def _mark(self, key: str) -> None:
        # Mark before the call, so a failing endpoint does not retry every cycle
        self._last_run[key] = time.monotonic()

    async def _guard(self, label: str, call: Awaitable[T]) -> T | None:
        """Run one category. Auth, quota, and subscription errors stop the update.
        Other errors are logged and the category keeps its last good data."""
        try:
            return await call
        except (SifelyAuthError, SifelySubscriptionError, SifelyRateLimitError):
            raise
        except SifelyGatewayRequiredError:
            return None
        except SifelyError as err:
            _LOGGER.warning("Sifely %s failed: %s", label, err)
            return None

    # ── Update ──────────────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        try:
            await self._refresh()
        except SifelyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (SifelySubscriptionError, SifelyRateLimitError, SifelyError) as err:
            raise UpdateFailed(str(err)) from err
        return dict(self._cache)

    async def _refresh(self) -> None:
        if not self._locks or self._due("list", LIST_INTERVAL):
            self._mark("list")
            self._locks = await self.client.get_locks()

        for lock in self._locks:
            lid = int(lock["lockId"])
            cache = self._cache.setdefault(lid, _empty_cache())
            # The list is refreshed hourly and carries battery and gateway flags
            cache["list"] = lock

            if self._due(f"detail:{lid}", DETAIL_INTERVAL):
                self._mark(f"detail:{lid}")
                detail = await self._guard(
                    f"detail {lid}", self.client.get_lock_detail(lid)
                )
                if detail is not None:
                    cache["detail"] = _pick(detail, DETAIL_FIELDS)

            if self._due(f"records:{lid}", RECORD_INTERVAL):
                self._mark(f"records:{lid}")
                records = await self._guard(
                    f"records {lid}", self.client.get_records(lid)
                )
                if records is not None:
                    self._process_records(lid, cache, records)

            if self._due(f"passcodes:{lid}", PASSCODE_INTERVAL):
                self._mark(f"passcodes:{lid}")
                passcodes = await self._guard(
                    f"passcodes {lid}", self.client.get_passcodes(lid)
                )
                if passcodes is not None:
                    cache["passcodes"] = [_pick(p, PASSCODE_FIELDS) for p in passcodes]

            # Open state only works with a gateway, so skip it otherwise
            if lock.get("hasGateway") == 1 and self._due(f"state:{lid}", STATE_INTERVAL):
                self._mark(f"state:{lid}")
                cache["open_state"] = await self._guard(
                    f"open state {lid}", self.client.get_open_state(lid)
                )

            self._cache[lid] = cache

    # ── Activity records ────────────────────────────────────────────────────

    def _process_records(
        self, lid: int, cache: dict[str, Any], records: list[dict[str, Any]]
    ) -> None:
        cache["records"] = [_pick(r, RECORD_FIELDS) for r in records]
        if not records:
            return

        newest = max(int(r.get("recordId", 0)) for r in records)
        previous = self._last_record_id.get(lid)

        # First poll after startup only sets the baseline, so restarting HA
        # does not replay old events.
        if previous is not None:
            new_records = sorted(
                (r for r in records if int(r.get("recordId", 0)) > previous),
                key=lambda r: int(r.get("recordId", 0)),
            )
            for record in new_records:
                # Keypad codes are not included in the event
                self.hass.bus.async_fire(
                    EVENT_ACTIVITY,
                    {
                        "lock_id": lid,
                        "lock_alias": cache["list"].get("lockAlias"),
                        "record_id": record.get("recordId"),
                        "record_type": record.get("recordType"),
                        "success": bool(record.get("success")),
                        "username": record.get("username"),
                        "lock_date": record.get("lockDate"),
                    },
                )

        self._last_record_id[lid] = max(newest, previous or 0)
