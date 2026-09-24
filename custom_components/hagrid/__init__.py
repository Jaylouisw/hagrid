"""HAGrid integration - Electrical Grid Map for Home Assistant."""
from __future__ import annotations

import logging
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the map-card JavaScript from the integration.

    HACS delivers only ``custom_components/hagrid/``, so the card cannot live in ``www/``: that
    folder is never installed, and the old instructions told every user to copy the file by hand
    and add a Lovelace resource. Registering the file here means an install that HACS performs is
    a working card, with no manual step.
    """
    if not _MAP_CARD_PATH.is_file():
        _LOGGER.warning(
            "HAGrid map card JS is missing at %s — sensors will work, the card will not",
            _MAP_CARD_PATH,
        )
        return True

    if register_static_paths := getattr(hass.http, "async_register_static_paths", None):
        # Home Assistant 2024.7+ replaced register_static_path with this call and its
        # StaticPathConfig. The import is deliberately lazy: on the declared floor (2024.1) that
        # class does not exist, and a top-level import would break the whole integration there.
        from homeassistant.components.http import StaticPathConfig

        await register_static_paths(
            [StaticPathConfig(_MAP_CARD_URL, str(_MAP_CARD_PATH), cache_headers=False)]
        )
    else:
        hass.http.register_static_path(_MAP_CARD_URL, str(_MAP_CARD_PATH), cache_headers=False)

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
