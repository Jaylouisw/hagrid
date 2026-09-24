"""Config flow for HAGrid integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import CarbonIntensityClient, GeocoderUnavailable, PostcodesIoClient
from .const import (
    CARBON_REGIONS,
    CONF_AESO_API_KEY,
    CONF_ALBERTA_ENABLED,
    CONF_BELGIUM_ENABLED,
    CONF_DENMARK_ENABLED,
    CONF_DNO,
    CONF_EIA_API_KEY,
    # Global API keys
    CONF_ELECTRICITY_MAPS_API_KEY,
    CONF_ENABLED_REGIONS,
    CONF_ENERGY_DASHBOARD_API_KEY,
    CONF_ENTSOE_API_KEY,
    # New additional API keys
    CONF_FINGRID_API_KEY,
    # Regional toggles
    CONF_FINLAND_ENABLED,
    CONF_GERMANY_ENABLED,
    CONF_INCLUDE_OSM_DATA,
    CONF_ITALY_ENABLED,
    CONF_NATIONAL_GRID_API_KEY,
    CONF_NEW_ZEALAND_ENABLED,
    CONF_ONTARIO_ENABLED,
    CONF_OSM_RADIUS_KM,
    CONF_POLAND_ENABLED,
    CONF_POSTCODE,
    CONF_REGION_ID,
    CONF_RTE_CLIENT_ID,
    CONF_RTE_CLIENT_SECRET,
    CONF_SHOW_INFRASTRUCTURE,
    CONF_SHOW_LIVE_FAULTS,
    CONF_SSEN_NERDA_API_KEY,
    CONF_UPDATE_INTERVAL,
    CONF_USE_HOME_LOCATION,
    CONF_WATTTIME_ENABLED,
    CONF_WATTTIME_PASSWORD,
    CONF_WATTTIME_USERNAME,
    CONF_ZONE,
    DEFAULT_INCLUDE_OSM_DATA,
    DEFAULT_OSM_RADIUS_KM,
    DEFAULT_SHOW_INFRASTRUCTURE,
    DEFAULT_SHOW_LIVE_FAULTS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ELECTRICITY_MAPS_ZONES,
)

_LOGGER = logging.getLogger(__name__)


async def validate_postcode(hass: HomeAssistant, postcode: str) -> dict[str, Any]:
    """Validate postcode against Carbon Intensity API."""
    async with aiohttp.ClientSession() as session:
        client = CarbonIntensityClient(session)
        data = await client.get_regional_data(postcode=postcode)

        if data:
            return {
                "region_id": data.region_id,
                "region_name": data.short_name,
                "dno": data.dno_region,
            }
        raise ValueError("Invalid postcode or region not found")


class HAGridConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HAGrid."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._postcode: str | None = None
        self._region_id: int | None = None
        self._region_info: dict[str, Any] = {}
        self._use_home_location: bool = False
        self._resolution_error: str | None = None
        self._home_location: str = "unknown"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # A region was picked by hand instead.
            region_id = user_input.get(CONF_REGION_ID)
            if not region_id:
                errors["base"] = "no_region_selected"
            else:
                self._region_id = int(region_id)
                self._use_home_location = False
                await self.async_set_unique_id(f"hagrid_region_{self._region_id}")
                self._abort_if_unique_id_configured()
                self._region_info = {
                    "region_id": self._region_id,
                    "region_name": CARBON_REGIONS.get(self._region_id, "Unknown"),
                    "dno": "Unknown",
                }
                return await self.async_step_confirm()
        elif await self._async_resolve_home_location():
            return await self.async_step_confirm()
        else:
            errors["base"] = self._resolution_error or "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_REGION_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=str(k), label=v)
                            for k, v in CARBON_REGIONS.items()
                            if k <= 14  # Exclude aggregate regions (England, Scotland, Wales)
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            errors=errors,
            description_placeholders={"location": self._home_location},
        )

    async def _async_resolve_home_location(self) -> bool:
        """Work out the grid region from the Home Assistant home location.

        Returns True when the flow can carry on, or False with self._resolution_error set to an error
        key for the form. It never raises: a config flow that raises leaves the user watching a
        spinner instead of reading a message.
        """
        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude
        self._home_location = f"{latitude:.4f}, {longitude:.4f}"

        try:
            async with aiohttp.ClientSession() as session:
                location = await PostcodesIoClient(session).reverse_geocode(latitude, longitude)
        except GeocoderUnavailable as err:
            _LOGGER.error("Postcode lookup failed for %s: %s", self._home_location, err)
            self._resolution_error = "cannot_connect"
            return False

        if location is None or location.country == "Northern Ireland":
            # postcodes.io answers with a null result outside Great Britain. Northern Ireland it does
            # resolve, but the Carbon Intensity API has no region for it: a BT postcode comes back
            # HTTP 400 "No postcode match can be found" (measured 2026-09-19), so both cases end up in
            # the same place, which is the region picker with an explanation.
            _LOGGER.info(
                "Home Assistant home location %s is not in a covered region; asking for one",
                self._home_location,
            )
            self._resolution_error = "location_not_in_gb"
            return False

        try:
            self._region_info = await validate_postcode(self.hass, location.outcode)
        except ValueError:
            self._resolution_error = "region_not_found"
            return False
        except Exception as err:
            _LOGGER.error("Could not resolve a region for %s: %s", location.outcode, err)
            self._resolution_error = "cannot_connect"
            return False

        self._postcode = location.outcode
        self._region_id = self._region_info.get("region_id")
        self._use_home_location = True
        await self.async_set_unique_id(f"hagrid_{location.outcode}")
        self._abort_if_unique_id_configured()
        _LOGGER.info(
            "Took %s (%s) from the Home Assistant home location %s",
            location.outcode,
            self._region_info.get("region_name", "unknown region"),
            self._home_location,
        )
        return True

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle confirmation step with API keys."""
        if user_input is not None:
            # The keys go into the entry's data, which Home Assistant writes as plain text to
            # config/.storage/core.config_entries — see the README's "API key storage" section.
            title = self._region_info.get("region_name", "HAGrid")
            if self._postcode:
                title = f"HAGrid - {self._postcode}"

            return self.async_create_entry(
                title=title,
                data={
                    CONF_POSTCODE: self._postcode,
                    CONF_REGION_ID: self._region_id,
                    # Stored because it decides which network operator's power cuts to ask for, and
                    # it cannot be re-derived from the region id alone for every operator.
                    CONF_DNO: self._region_info.get("dno", ""),
                    # UK API keys
                    CONF_NATIONAL_GRID_API_KEY: user_input.get(CONF_NATIONAL_GRID_API_KEY, ""),
                    CONF_SSEN_NERDA_API_KEY: user_input.get(CONF_SSEN_NERDA_API_KEY, ""),
                    CONF_ENERGY_DASHBOARD_API_KEY: user_input.get(CONF_ENERGY_DASHBOARD_API_KEY, ""),
                    # Global API keys
                    CONF_ELECTRICITY_MAPS_API_KEY: user_input.get(CONF_ELECTRICITY_MAPS_API_KEY, ""),
                    CONF_EIA_API_KEY: user_input.get(CONF_EIA_API_KEY, ""),
                    CONF_ENTSOE_API_KEY: user_input.get(CONF_ENTSOE_API_KEY, ""),
                    CONF_RTE_CLIENT_ID: user_input.get(CONF_RTE_CLIENT_ID, ""),
                    CONF_RTE_CLIENT_SECRET: user_input.get(CONF_RTE_CLIENT_SECRET, ""),
                    # Additional API keys (new)
                    CONF_FINGRID_API_KEY: user_input.get(CONF_FINGRID_API_KEY, ""),
                    CONF_AESO_API_KEY: user_input.get(CONF_AESO_API_KEY, ""),
                    CONF_WATTTIME_USERNAME: user_input.get(CONF_WATTTIME_USERNAME, ""),
                    CONF_WATTTIME_PASSWORD: user_input.get(CONF_WATTTIME_PASSWORD, ""),
                    # Zone configuration
                    CONF_ZONE: user_input.get(CONF_ZONE, "GB"),
                    CONF_ENABLED_REGIONS: user_input.get(CONF_ENABLED_REGIONS, []),
                    # Regional toggles (free APIs - no auth required)
                    CONF_FINLAND_ENABLED: user_input.get(CONF_FINLAND_ENABLED, False),
                    CONF_DENMARK_ENABLED: user_input.get(CONF_DENMARK_ENABLED, False),
                    CONF_BELGIUM_ENABLED: user_input.get(CONF_BELGIUM_ENABLED, False),
                    CONF_GERMANY_ENABLED: user_input.get(CONF_GERMANY_ENABLED, False),
                    CONF_POLAND_ENABLED: user_input.get(CONF_POLAND_ENABLED, False),
                    CONF_ITALY_ENABLED: user_input.get(CONF_ITALY_ENABLED, False),
                    CONF_ONTARIO_ENABLED: user_input.get(CONF_ONTARIO_ENABLED, False),
                    CONF_ALBERTA_ENABLED: user_input.get(CONF_ALBERTA_ENABLED, False),
                    CONF_NEW_ZEALAND_ENABLED: user_input.get(CONF_NEW_ZEALAND_ENABLED, False),
                    CONF_WATTTIME_ENABLED: user_input.get(CONF_WATTTIME_ENABLED, False),
                },
                options={
                    CONF_USE_HOME_LOCATION: self._use_home_location,
                    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                    CONF_SHOW_INFRASTRUCTURE: DEFAULT_SHOW_INFRASTRUCTURE,
                    CONF_SHOW_LIVE_FAULTS: DEFAULT_SHOW_LIVE_FAULTS,
                    CONF_INCLUDE_OSM_DATA: DEFAULT_INCLUDE_OSM_DATA,
                    CONF_OSM_RADIUS_KM: DEFAULT_OSM_RADIUS_KM,
                },
            )

        # Build zone options from Electricity Maps zones
        zone_options = [
            selector.SelectOptionDict(value=k, label=f"{v['name']} ({k})")
            for k, v in ELECTRICITY_MAPS_ZONES.items()
        ]

        # Show form for API keys (all optional except Electricity Maps if using global data)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({
                # Primary zone selection
                vol.Optional(CONF_ZONE, default="GB"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                # === Global APIs ===
                vol.Optional(CONF_ELECTRICITY_MAPS_API_KEY): str,
                vol.Optional(CONF_WATTTIME_USERNAME): str,
                vol.Optional(CONF_WATTTIME_PASSWORD): str,
                vol.Optional(CONF_WATTTIME_ENABLED, default=False): bool,
                # === UK-specific APIs ===
                vol.Optional(CONF_NATIONAL_GRID_API_KEY): str,
                vol.Optional(CONF_SSEN_NERDA_API_KEY): str,
                vol.Optional(CONF_ENERGY_DASHBOARD_API_KEY): str,
                # === European APIs ===
                # ENTSO-E (EU-wide)
                vol.Optional(CONF_ENTSOE_API_KEY): str,
                # France - RTE (OAuth)
                vol.Optional(CONF_RTE_CLIENT_ID): str,
                vol.Optional(CONF_RTE_CLIENT_SECRET): str,
                # Finland - Fingrid (API key required)
                vol.Optional(CONF_FINGRID_API_KEY): str,
                vol.Optional(CONF_FINLAND_ENABLED, default=False): bool,
                # Denmark - Energinet (free, no auth)
                vol.Optional(CONF_DENMARK_ENABLED, default=False): bool,
                # Belgium - Elia (free, no auth)
                vol.Optional(CONF_BELGIUM_ENABLED, default=False): bool,
                # Germany - SMARD (free, no auth)
                vol.Optional(CONF_GERMANY_ENABLED, default=False): bool,
                # Poland - PSE (free, no auth)
                vol.Optional(CONF_POLAND_ENABLED, default=False): bool,
                # Italy - Terna (free, no auth)
                vol.Optional(CONF_ITALY_ENABLED, default=False): bool,
                # === North America APIs ===
                # USA - EIA API
                vol.Optional(CONF_EIA_API_KEY): str,
                # Canada - Ontario IESO (free, no auth)
                vol.Optional(CONF_ONTARIO_ENABLED, default=False): bool,
                # Canada - Alberta AESO (API key required)
                vol.Optional(CONF_AESO_API_KEY): str,
                vol.Optional(CONF_ALBERTA_ENABLED, default=False): bool,
                # === Oceania APIs ===
                # New Zealand - Transpower (free, no auth)
                vol.Optional(CONF_NEW_ZEALAND_ENABLED, default=False): bool,
            }),
            description_placeholders={
                "region": self._region_info.get("region_name", "Unknown"),
                "dno": self._region_info.get("dno", "Unknown"),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return HAGridOptionsFlow(config_entry)


class HAGridOptionsFlow(config_entries.OptionsFlow):
    """Handle HAGrid options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_USE_HOME_LOCATION,
                    default=self.config_entry.options.get(CONF_USE_HOME_LOCATION, False),
                ): bool,
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60,
                        max=3600,
                        step=60,
                        unit_of_measurement="seconds",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Required(
                    CONF_SHOW_INFRASTRUCTURE,
                    default=self.config_entry.options.get(
                        CONF_SHOW_INFRASTRUCTURE, DEFAULT_SHOW_INFRASTRUCTURE
                    ),
                ): bool,
                vol.Required(
                    CONF_SHOW_LIVE_FAULTS,
                    default=self.config_entry.options.get(
                        CONF_SHOW_LIVE_FAULTS, DEFAULT_SHOW_LIVE_FAULTS
                    ),
                ): bool,
                vol.Required(
                    CONF_INCLUDE_OSM_DATA,
                    default=self.config_entry.options.get(
                        CONF_INCLUDE_OSM_DATA, DEFAULT_INCLUDE_OSM_DATA
                    ),
                ): bool,
                vol.Required(
                    CONF_OSM_RADIUS_KM,
                    default=self.config_entry.options.get(
                        CONF_OSM_RADIUS_KM, DEFAULT_OSM_RADIUS_KM
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=50,
                        step=1,
                        unit_of_measurement="km",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
            }),
        )

    async def async_step_api_keys(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage API keys (stored in entry.data)."""
        if user_input is not None:
            # Update the config entry data with new API keys
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(
            step_id="api_keys",
            data_schema=vol.Schema({
                # === Global APIs ===
                vol.Optional(
                    CONF_ELECTRICITY_MAPS_API_KEY,
                    default=self.config_entry.data.get(CONF_ELECTRICITY_MAPS_API_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_WATTTIME_USERNAME,
                    default=self.config_entry.data.get(CONF_WATTTIME_USERNAME, ""),
                ): str,
                vol.Optional(
                    CONF_WATTTIME_PASSWORD,
                    default=self.config_entry.data.get(CONF_WATTTIME_PASSWORD, ""),
                ): str,
                vol.Optional(
                    CONF_WATTTIME_ENABLED,
                    default=self.config_entry.data.get(CONF_WATTTIME_ENABLED, False),
                ): bool,
                # === UK APIs ===
                vol.Optional(
                    CONF_NATIONAL_GRID_API_KEY,
                    default=self.config_entry.data.get(CONF_NATIONAL_GRID_API_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_SSEN_NERDA_API_KEY,
                    default=self.config_entry.data.get(CONF_SSEN_NERDA_API_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_ENERGY_DASHBOARD_API_KEY,
                    default=self.config_entry.data.get(CONF_ENERGY_DASHBOARD_API_KEY, ""),
                ): str,
                # === European APIs ===
                vol.Optional(
                    CONF_ENTSOE_API_KEY,
                    default=self.config_entry.data.get(CONF_ENTSOE_API_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_RTE_CLIENT_ID,
                    default=self.config_entry.data.get(CONF_RTE_CLIENT_ID, ""),
                ): str,
                vol.Optional(
                    CONF_RTE_CLIENT_SECRET,
                    default=self.config_entry.data.get(CONF_RTE_CLIENT_SECRET, ""),
                ): str,
                vol.Optional(
                    CONF_FINGRID_API_KEY,
                    default=self.config_entry.data.get(CONF_FINGRID_API_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_FINLAND_ENABLED,
                    default=self.config_entry.data.get(CONF_FINLAND_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_DENMARK_ENABLED,
                    default=self.config_entry.data.get(CONF_DENMARK_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_BELGIUM_ENABLED,
                    default=self.config_entry.data.get(CONF_BELGIUM_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_GERMANY_ENABLED,
                    default=self.config_entry.data.get(CONF_GERMANY_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_POLAND_ENABLED,
                    default=self.config_entry.data.get(CONF_POLAND_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_ITALY_ENABLED,
                    default=self.config_entry.data.get(CONF_ITALY_ENABLED, False),
                ): bool,
                # === North America APIs ===
                vol.Optional(
                    CONF_EIA_API_KEY,
                    default=self.config_entry.data.get(CONF_EIA_API_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_ONTARIO_ENABLED,
                    default=self.config_entry.data.get(CONF_ONTARIO_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_AESO_API_KEY,
                    default=self.config_entry.data.get(CONF_AESO_API_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_ALBERTA_ENABLED,
                    default=self.config_entry.data.get(CONF_ALBERTA_ENABLED, False),
                ): bool,
                # === Oceania APIs ===
                vol.Optional(
                    CONF_NEW_ZEALAND_ENABLED,
                    default=self.config_entry.data.get(CONF_NEW_ZEALAND_ENABLED, False),
                ): bool,
            }),
        )
