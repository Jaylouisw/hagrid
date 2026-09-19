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

from .api import CarbonIntensityClient
from .const import (
    DOMAIN,
    CONF_POSTCODE,
    CONF_REGION_ID,
    CONF_UPDATE_INTERVAL,
    CONF_SHOW_INFRASTRUCTURE,
    CONF_SHOW_LIVE_FAULTS,
    CONF_INCLUDE_OSM_DATA,
    CONF_OSM_RADIUS_KM,
    CONF_NATIONAL_GRID_API_KEY,
    CONF_SSEN_NERDA_API_KEY,
    CONF_ENERGY_DASHBOARD_API_KEY,
    # Global API keys
    CONF_ELECTRICITY_MAPS_API_KEY,
    CONF_EIA_API_KEY,
    CONF_ENTSOE_API_KEY,
    CONF_RTE_CLIENT_ID,
    CONF_RTE_CLIENT_SECRET,
    # New additional API keys
    CONF_FINGRID_API_KEY,
    CONF_AESO_API_KEY,
    CONF_WATTTIME_USERNAME,
    CONF_WATTTIME_PASSWORD,
    # Regional toggles
    CONF_FINLAND_ENABLED,
    CONF_DENMARK_ENABLED,
    CONF_BELGIUM_ENABLED,
    CONF_GERMANY_ENABLED,
    CONF_POLAND_ENABLED,
    CONF_ITALY_ENABLED,
    CONF_ONTARIO_ENABLED,
    CONF_ALBERTA_ENABLED,
    CONF_NEW_ZEALAND_ENABLED,
    CONF_WATTTIME_ENABLED,
    CONF_ZONE,
    CONF_ENABLED_REGIONS,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_SHOW_INFRASTRUCTURE,
    DEFAULT_SHOW_LIVE_FAULTS,
    DEFAULT_INCLUDE_OSM_DATA,
    DEFAULT_OSM_RADIUS_KM,
    CARBON_REGIONS,
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
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            postcode = user_input.get(CONF_POSTCODE, "").strip().upper()
            
            if postcode:
                # Extract outward code (first part of postcode)
                outward = postcode.split()[0] if " " in postcode else postcode[:4].rstrip()
                
                try:
                    self._region_info = await validate_postcode(self.hass, outward)
                    self._postcode = outward
                    self._region_id = self._region_info.get("region_id")
                    
                    # Check for existing entry with same postcode
                    await self.async_set_unique_id(f"hagrid_{outward}")
                    self._abort_if_unique_id_configured()
                    
                    return await self.async_step_confirm()
                    
                except ValueError:
                    errors["base"] = "invalid_postcode"
                except Exception as e:
                    _LOGGER.error("Error validating postcode: %s", e)
                    errors["base"] = "cannot_connect"
            else:
                # No postcode - use region selector
                return await self.async_step_region()
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional(CONF_POSTCODE): str,
            }),
            errors=errors,
            description_placeholders={
                "example": "SW1A or RG10",
            },
        )
    
    async def async_step_region(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle region selection step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._region_id = user_input.get(CONF_REGION_ID)
            
            if self._region_id:
                region_name = CARBON_REGIONS.get(self._region_id, "Unknown")
                
                await self.async_set_unique_id(f"hagrid_region_{self._region_id}")
                self._abort_if_unique_id_configured()
                
                self._region_info = {
                    "region_id": self._region_id,
                    "region_name": region_name,
                }
                
                return await self.async_step_confirm()
            else:
                errors["base"] = "no_region_selected"
        
        # Build region options
        region_options = [
            selector.SelectOptionDict(value=str(k), label=v)
            for k, v in CARBON_REGIONS.items()
            if k <= 14  # Exclude aggregate regions (England, Scotland, Wales)
        ]
        
        return self.async_show_form(
            step_id="region",
            data_schema=vol.Schema({
                vol.Required(CONF_REGION_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=region_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            errors=errors,
        )
    
    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle confirmation step with API keys."""
        if user_input is not None:
            # Create the entry with API keys stored securely in data
            title = self._region_info.get("region_name", "HAGrid")
            if self._postcode:
                title = f"HAGrid - {self._postcode}"
            
            return self.async_create_entry(
                title=title,
                data={
                    CONF_POSTCODE: self._postcode,
                    CONF_REGION_ID: self._region_id,
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
