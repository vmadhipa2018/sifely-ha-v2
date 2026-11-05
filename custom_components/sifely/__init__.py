"""Sifely Smart Lock integration for Home Assistant (Open API, API key auth)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SifelyClient
from .const import CONF_API_KEY, DOMAIN
from .coordinator import SifelyCoordinator

PLATFORMS: list[Platform] = [Platform.LOCK, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sifely from a config entry."""
    api_key = entry.data.get(CONF_API_KEY)
    if not api_key:
        # Entries from the v1 integration stored a client ID and password.
        # Raising this starts the reauth flow so the user can enter an API key.
        raise ConfigEntryAuthFailed("This entry needs a Sifely API key")

    client = SifelyClient(api_key, async_get_clientsession(hass))
    coordinator = SifelyCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
