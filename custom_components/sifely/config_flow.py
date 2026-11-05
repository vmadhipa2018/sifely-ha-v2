"""Config flow for the Sifely Smart Lock integration (API key only)."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SifelyAuthError,
    SifelyClient,
    SifelyError,
    SifelyRateLimitError,
    SifelySubscriptionError,
)
from .const import CONF_API_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class SifelyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up Sifely with an Open API key from connect.sifely.com."""

    VERSION = 2

    async def _validate(self, api_key: str) -> str | None:
        """Return an error key, or None if the key works."""
        client = SifelyClient(api_key, async_get_clientsession(self.hass))
        try:
            await client.get_locks()
        except SifelyAuthError:
            return "invalid_auth"
        except SifelySubscriptionError:
            return "subscription_inactive"
        except SifelyRateLimitError:
            return "rate_limited"
        except SifelyError as err:
            _LOGGER.warning("Sifely validation failed: %s", err)
            return "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            error = await self._validate(api_key)
            if error:
                errors["base"] = error
            else:
                # Hash the key for the unique ID so the key itself is not stored there
                unique_id = hashlib.sha256(api_key.encode()).hexdigest()[:16]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Sifely Smart Lock",
                    data={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            error = await self._validate(api_key)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_DATA_SCHEMA,
            errors=errors,
        )
