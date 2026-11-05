"""Sifely Open API client using API key authentication."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_LOCK_DETAIL,
    API_LOCK_LIST,
    API_LOCK_LOCK,
    API_LOCK_OPEN_STATE,
    API_LOCK_UNLOCK,
    API_PASSCODE_LIST,
    API_RECORD_LIST,
    ERR_GATEWAY_REQUIRED,
    RECORD_PAGE_SIZE,
    RECORD_WINDOW_DAYS,
)

_LOGGER = logging.getLogger(__name__)
REQUEST_TIMEOUT = 15


class SifelyError(Exception):
    """Base error for the Sifely API."""


class SifelyConnectionError(SifelyError):
    """Network failure or timeout."""


class SifelyAuthError(SifelyError):
    """API key missing, invalid, or revoked (HTTP 401/403)."""


class SifelySubscriptionError(SifelyError):
    """Subscription inactive (HTTP 402)."""


class SifelyRateLimitError(SifelyError):
    """Quota or rate limit exceeded (HTTP 429)."""


class SifelyGatewayRequiredError(SifelyError):
    """Lock is not connected to a gateway (code -2012)."""


class SifelyApiError(SifelyError):
    """Any other error returned by the API."""


class SifelyClient:
    """Thin async client for the Sifely Open API."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession) -> None:
        self._api_key = api_key
        self._session = session

    # ── HTTP ────────────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{API_BASE_URL}{path}"
        # Raw key, no "Bearer" prefix (per Sifely docs)
        headers = {"Authorization": self._api_key, "Accept": "application/json"}
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                status = resp.status
                text = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SifelyConnectionError(f"Network error: {err}") from err

        try:
            body: Any = json.loads(text) if text else {}
        except ValueError:
            body = {}

        # Status-based errors first
        if status in (401, 403):
            raise SifelyAuthError(f"HTTP {status}: check the API key")
        if status == 402:
            raise SifelySubscriptionError("Subscription is not active")
        if status == 429:
            raise SifelyRateLimitError("Quota or rate limit exceeded")

        # Body-level errors. Some are returned with HTTP 400, so check these
        # before the generic status check.
        if isinstance(body, dict):
            code = body.get("code")
            if code not in (None, 0, 200):
                message = body.get("message") or ""
                if code == ERR_GATEWAY_REQUIRED:
                    raise SifelyGatewayRequiredError(message)
                raise SifelyApiError(f"Error {code}: {message}")

        if status >= 400:
            raise SifelyApiError(f"HTTP {status}: {text[:200]}")

        return body

    # ── Discovery and reads (no gateway needed) ─────────────────────────────

    async def get_locks(self) -> list[dict[str, Any]]:
        """Return every lock on the account (one POST per page of 20)."""
        locks: list[dict[str, Any]] = []
        page = 1
        while True:
            data = await self._request(
                "POST", API_LOCK_LIST, {"pageNo": page, "pageSize": 20}
            )
            items = data.get("list") or []
            locks.extend(items)
            total = data.get("total") or 0
            if not items or len(locks) >= total:
                break
            page += 1
        return locks

    async def get_lock_detail(self, lock_id: int) -> dict[str, Any]:
        return await self._request("GET", API_LOCK_DETAIL, {"lockId": lock_id})

    async def get_passcodes(self, lock_id: int) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            API_PASSCODE_LIST,
            {"lockId": lock_id, "pageNo": 1, "pageSize": 50},
        )
        return data.get("list") or []

    async def get_records(
        self, lock_id: int, limit: int = 20, days: int = RECORD_WINDOW_DAYS
    ) -> list[dict[str, Any]]:
        """Return the newest activity records from the last `days` days.

        The API does not document its sort order, so one page of up to
        RECORD_PAGE_SIZE records is fetched for an explicit date range and
        sorted newest-first here.
        """
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - days * 86_400_000
        data = await self._request(
            "GET",
            API_RECORD_LIST,
            {
                "lockId": lock_id,
                "pageNo": 1,
                "pageSize": RECORD_PAGE_SIZE,
                "startDate": start_ms,
                "endDate": end_ms,
            },
        )
        records = data.get("list") or []
        records.sort(key=lambda r: r.get("lockDate") or 0, reverse=True)
        return records[:limit]

    # ── Gateway-dependent calls ─────────────────────────────────────────────

    async def get_open_state(self, lock_id: int) -> int:
        data = await self._request("GET", API_LOCK_OPEN_STATE, {"lockId": lock_id})
        return int(data.get("state", 2))

    async def lock(self, lock_id: int) -> None:
        await self._command(API_LOCK_LOCK, lock_id)

    async def unlock(self, lock_id: int) -> None:
        await self._command(API_LOCK_UNLOCK, lock_id)

    async def _command(self, path: str, lock_id: int) -> None:
        data = await self._request("POST", path, {"lockId": lock_id})
        errcode = data.get("errcode", 0) if isinstance(data, dict) else 0
        if errcode not in (0, None):
            raise SifelyApiError(
                f"Command failed ({errcode}): {data.get('errmsg', '')}"
            )
