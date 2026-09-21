"""HAGrid integration - Electrical Grid Map for Home Assistant."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import HAGridCoordinator

_LOGGER = logging.getLogger(__name__)

_MAP_CARD_URL = "/hagrid/hagrid-map.js"
_MAP_CARD_PATH = Path(__file__).parent / "www" / "hagrid-map.js"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass(slots=True)
class _StaticPathConfigCompat:
    """Runtime shape accepted by newer Home Assistant static-path registration."""

    url_path: str
    path: str
    cache_headers: bool = True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the map-card JavaScript so HACS installs work without manual steps."""
    if not _MAP_CARD_PATH.is_file():
        _LOGGER.warning("Map card JS not found at %s", _MAP_CARD_PATH)
        return True

    if register_static_paths := getattr(hass.http, "async_register_static_paths", None):
        await register_static_paths(
            [_StaticPathConfigCompat(_MAP_CARD_URL, str(_MAP_CARD_PATH), cache_headers=False)]
        )
    else:
        hass.http.register_static_path(_MAP_CARD_URL, str(_MAP_CARD_PATH), False)

    add_extra_js_url(hass, _MAP_CARD_URL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HAGrid from a config entry."""
    coordinator = HAGridCoordinator(hass, entry)

    # Set up the session and clients
    await coordinator._async_setup()

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: HAGridCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
