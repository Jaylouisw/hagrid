"""Data coordinator for HAGrid."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CarbonIntensityClient,
    UKPNClient,
    OverpassClient,
    NESOClient,
    NationalGridClient,
    SSENNerdaClient,
    EnergyDashboardClient,
    ElexonBMRSClient,
    # Global API clients
    ElectricityMapsClient,
    EIAClient,
    ENTSOEClient,
    OpenElectricityClient,
    REEEsiosClient,
    RTEClient,
    # Additional open API clients
    FingridClient,
    EnerginetClient,
    EliaClient,
    SMARDClient,
    PSEClient,
    TernaClient,
    IESOClient,
    AESOClient,
    TranspowerClient,
    WattTimeClient,
    # Data classes
    RegionalData,
    LiveFault,
    Substation,
    PowerLine,
    EmbeddedGeneration,
    OSMPowerFeature,
    SystemData,
    CircuitFlow,
    FuelTypeGeneration,
    InterconnectorFlow,
    SystemFrequency,
    ZoneCarbonIntensity,
    ZonePowerBreakdown,
    CrossBorderFlow,
    PriceData,
    GridFrequency,
    DayAheadPrice,
    ImbalanceData,
)
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
    # Global API configuration
    CONF_ELECTRICITY_MAPS_API_KEY,
    CONF_ELECTRICITY_MAPS_ZONE,
    CONF_EIA_API_KEY,
    CONF_EIA_REGION,
    CONF_ENTSOE_API_KEY,
    CONF_ENTSOE_AREA,
    CONF_RTE_CLIENT_ID,
    CONF_RTE_CLIENT_SECRET,
    CONF_AUSTRALIA_REGION,
    CONF_SPAIN_REGION,
    # Additional API configuration
    CONF_FINGRID_API_KEY,
    CONF_AESO_API_KEY,
    CONF_WATTTIME_USERNAME,
    CONF_WATTTIME_PASSWORD,
    CONF_FINLAND_ENABLED,
    CONF_DENMARK_ENABLED,
    CONF_BELGIUM_ENABLED,
    CONF_GERMANY_ENABLED,
    CONF_POLAND_ENABLED,
    CONF_ITALY_ENABLED,
    CONF_NEW_ZEALAND_ENABLED,
    CONF_CANADA_REGION,
    CONF_US_ISO,
    # Defaults
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_SHOW_INFRASTRUCTURE,
    DEFAULT_SHOW_LIVE_FAULTS,
    DEFAULT_INCLUDE_OSM_DATA,
    DEFAULT_OSM_RADIUS_KM,
)

_LOGGER = logging.getLogger(__name__)


class HAGridCoordinator(DataUpdateCoordinator):
    """Coordinator for HAGrid data updates."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.postcode: str | None = entry.data.get(CONF_POSTCODE)
        self.region_id: int | None = entry.data.get(CONF_REGION_ID)
        self.show_infrastructure: bool = entry.options.get(
            CONF_SHOW_INFRASTRUCTURE, DEFAULT_SHOW_INFRASTRUCTURE
        )
        self.show_live_faults: bool = entry.options.get(
            CONF_SHOW_LIVE_FAULTS, DEFAULT_SHOW_LIVE_FAULTS
        )
        self.include_osm_data: bool = entry.options.get(
            CONF_INCLUDE_OSM_DATA, DEFAULT_INCLUDE_OSM_DATA
        )
        self.osm_radius_km: int = entry.options.get(
            CONF_OSM_RADIUS_KM, DEFAULT_OSM_RADIUS_KM
        )
        
        # API keys from entry.data (stored securely)
        self._national_grid_api_key: str = entry.data.get(CONF_NATIONAL_GRID_API_KEY, "")
        self._ssen_nerda_api_key: str = entry.data.get(CONF_SSEN_NERDA_API_KEY, "")
        self._energy_dashboard_api_key: str = entry.data.get(CONF_ENERGY_DASHBOARD_API_KEY, "")
        
        # Global API keys and zone configuration
        self._electricity_maps_api_key: str = entry.data.get(CONF_ELECTRICITY_MAPS_API_KEY, "")
        self._electricity_maps_zone: str = entry.data.get(CONF_ELECTRICITY_MAPS_ZONE, "GB")
        self._eia_api_key: str = entry.data.get(CONF_EIA_API_KEY, "")
        self._eia_region: str = entry.data.get(CONF_EIA_REGION, "")
        self._entsoe_api_key: str = entry.data.get(CONF_ENTSOE_API_KEY, "")
        self._entsoe_area: str = entry.data.get(CONF_ENTSOE_AREA, "")
        self._rte_client_id: str = entry.data.get(CONF_RTE_CLIENT_ID, "")
        self._rte_client_secret: str = entry.data.get(CONF_RTE_CLIENT_SECRET, "")
        self._australia_region: str = entry.data.get(CONF_AUSTRALIA_REGION, "")
        self._spain_region: str = entry.data.get(CONF_SPAIN_REGION, "")
        
        # Additional open API configuration
        self._fingrid_api_key: str = entry.data.get(CONF_FINGRID_API_KEY, "")
        self._aeso_api_key: str = entry.data.get(CONF_AESO_API_KEY, "")
        self._watttime_username: str = entry.data.get(CONF_WATTTIME_USERNAME, "")
        self._watttime_password: str = entry.data.get(CONF_WATTTIME_PASSWORD, "")
        
        # Region toggles (free APIs, no auth required)
        self._finland_enabled: bool = entry.data.get(CONF_FINLAND_ENABLED, False)
        self._denmark_enabled: bool = entry.data.get(CONF_DENMARK_ENABLED, False)
        self._belgium_enabled: bool = entry.data.get(CONF_BELGIUM_ENABLED, False)
        self._germany_enabled: bool = entry.data.get(CONF_GERMANY_ENABLED, False)
        self._poland_enabled: bool = entry.data.get(CONF_POLAND_ENABLED, False)
        self._italy_enabled: bool = entry.data.get(CONF_ITALY_ENABLED, False)
        self._new_zealand_enabled: bool = entry.data.get(CONF_NEW_ZEALAND_ENABLED, False)
        self._canada_region: str = entry.data.get(CONF_CANADA_REGION, "")
        self._us_iso: str = entry.data.get(CONF_US_ISO, "")
        
        update_interval = entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        
        # Clients will be initialized in async_config_entry_first_refresh
        self._session: aiohttp.ClientSession | None = None
        self.carbon_client: CarbonIntensityClient | None = None
        self.ukpn_client: UKPNClient | None = None
        self.overpass_client: OverpassClient | None = None
        self.neso_client: NESOClient | None = None
        self.national_grid_client: NationalGridClient | None = None
        self.ssen_client: SSENNerdaClient | None = None
        self.energy_dashboard_client: EnergyDashboardClient | None = None
        self.elexon_client: ElexonBMRSClient | None = None
        
        # Global API clients
        self.electricity_maps_client: ElectricityMapsClient | None = None
        self.eia_client: EIAClient | None = None
        self.entsoe_client: ENTSOEClient | None = None
        self.openelectricity_client: OpenElectricityClient | None = None
        self.ree_esios_client: REEEsiosClient | None = None
        self.rte_client: RTEClient | None = None
        
        # Additional open API clients
        self.fingrid_client: FingridClient | None = None
        self.energinet_client: EnerginetClient | None = None
        self.elia_client: EliaClient | None = None
        self.smard_client: SMARDClient | None = None
        self.pse_client: PSEClient | None = None
        self.terna_client: TernaClient | None = None
        self.ieso_client: IESOClient | None = None
        self.aeso_client: AESOClient | None = None
        self.transpower_client: TranspowerClient | None = None
        self.watttime_client: WattTimeClient | None = None
        
        # Cached infrastructure data (doesn't change often)
        self._cached_substations: list[Substation] = []
        self._cached_lines: list[PowerLine] = []
        self._cached_generation: list[EmbeddedGeneration] = []
        self._cached_osm_features: list[OSMPowerFeature] = []
        self._infrastructure_last_update: float = 0
        self._infrastructure_update_interval = 3600  # 1 hour
        
        # Location for OSM queries (will be geocoded from postcode)
        self._location_lat: float | None = None
        self._location_lon: float | None = None
    
    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        self._session = aiohttp.ClientSession()
        
        # Always-available clients (no API key needed)
        self.carbon_client = CarbonIntensityClient(self._session)
        self.ukpn_client = UKPNClient(self._session)
        self.overpass_client = OverpassClient(self._session)
        self.neso_client = NESOClient(self._session)
        self.elexon_client = ElexonBMRSClient(self._session)  # Free, no API key
        
        # API key-gated clients
        if self._national_grid_api_key:
            self.national_grid_client = NationalGridClient(
                self._session, self._national_grid_api_key
            )
        if self._ssen_nerda_api_key:
            self.ssen_client = SSENNerdaClient(
                self._session, self._ssen_nerda_api_key
            )
        if self._energy_dashboard_api_key:
            self.energy_dashboard_client = EnergyDashboardClient(
                self._session, self._energy_dashboard_api_key
            )
        
        # Global API clients
        # Electricity Maps - requires API key for full access
        if self._electricity_maps_api_key:
            self.electricity_maps_client = ElectricityMapsClient(
                self._session, self._electricity_maps_api_key
            )
            _LOGGER.info(
                "Electricity Maps client initialized for zone: %s",
                self._electricity_maps_zone,
            )
        
        # EIA (USA) - requires free API key
        if self._eia_api_key:
            self.eia_client = EIAClient(self._session, self._eia_api_key)
            _LOGGER.info("EIA client initialized for region: %s", self._eia_region)
        
        # ENTSO-E (Europe) - requires free security token
        if self._entsoe_api_key:
            self.entsoe_client = ENTSOEClient(self._session, self._entsoe_api_key)
            _LOGGER.info("ENTSO-E client initialized for area: %s", self._entsoe_area)
        
        # OpenElectricity (Australia) - free, no key required
        if self._australia_region:
            self.openelectricity_client = OpenElectricityClient(self._session)
            _LOGGER.info(
                "OpenElectricity client initialized for region: %s",
                self._australia_region,
            )
        
        # REE Esios (Spain) - free, no auth required for basic data
        if self._spain_region:
            self.ree_esios_client = REEEsiosClient(self._session)
            _LOGGER.info(
                "REE Esios client initialized for region: %s",
                self._spain_region,
            )
        
        # RTE (France) - requires OAuth2 credentials
        if self._rte_client_id and self._rte_client_secret:
            self.rte_client = RTEClient(
                self._session, self._rte_client_id, self._rte_client_secret
            )
            _LOGGER.info("RTE client initialized for France")
        
        # === Additional Open API Clients ===
        
        # Fingrid (Finland) - requires free API key
        if self._fingrid_api_key:
            self.fingrid_client = FingridClient(self._session, self._fingrid_api_key)
            _LOGGER.info("Fingrid client initialized for Finland")
        
        # Energinet (Denmark) - free, no auth required
        if self._denmark_enabled:
            self.energinet_client = EnerginetClient(self._session)
            _LOGGER.info("Energinet client initialized for Denmark")
        
        # Elia (Belgium) - free, no auth required
        if self._belgium_enabled:
            self.elia_client = EliaClient(self._session)
            _LOGGER.info("Elia client initialized for Belgium")
        
        # SMARD (Germany) - free, no auth required
        if self._germany_enabled:
            self.smard_client = SMARDClient(self._session)
            _LOGGER.info("SMARD client initialized for Germany")
        
        # PSE (Poland) - free, no auth required
        if self._poland_enabled:
            self.pse_client = PSEClient(self._session)
            _LOGGER.info("PSE client initialized for Poland")
        
        # Terna (Italy) - free, limited auth
        if self._italy_enabled:
            self.terna_client = TernaClient(self._session)
            _LOGGER.info("Terna client initialized for Italy")
        
        # IESO (Ontario, Canada) - free, no auth required
        if self._canada_region == "IESO":
            self.ieso_client = IESOClient(self._session)
            _LOGGER.info("IESO client initialized for Ontario, Canada")
        
        # AESO (Alberta, Canada) - requires free API key
        if self._aeso_api_key:
            self.aeso_client = AESOClient(self._session, self._aeso_api_key)
            _LOGGER.info("AESO client initialized for Alberta, Canada")
        
        # Transpower (New Zealand) - free, no auth required
        if self._new_zealand_enabled:
            self.transpower_client = TranspowerClient(self._session)
            _LOGGER.info("Transpower client initialized for New Zealand")
        
        # WattTime (Global) - requires free account
        if self._watttime_username and self._watttime_password:
            self.watttime_client = WattTimeClient(
                self._session, self._watttime_username, self._watttime_password
            )
            _LOGGER.info("WattTime client initialized for global emissions")
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from APIs."""
        if not self._session:
            await self._async_setup()
        
        # Guard against uninitialized clients
        if self.carbon_client is None or self.ukpn_client is None:
            raise UpdateFailed("API clients not initialized")
        
        try:
            data: dict[str, Any] = {
                "regional_data": None,
                "all_regions": [],
                "live_faults": [],
                "substations": [],
                "power_lines": [],
                "embedded_generation": [],
                "osm_features": [],
                "forecast": [],
                "neso_data": None,
                "national_grid_data": None,
                "ssen_data": None,
                "energy_dashboard_data": None,
                # Granular metered circuit data from Elexon
                "circuit_flows": [],
                "generation_by_fuel": [],
                "interconnector_flows": [],
                "system_frequency": None,
                "demand": None,
                "grid_summary": None,
                # Global API data
                "global_carbon": None,  # From Electricity Maps
                "global_power_breakdown": None,  # From Electricity Maps
                "global_cross_border_flows": [],  # From Electricity Maps
                "eia_data": None,  # USA grid data
                "entsoe_data": None,  # European grid data
                "australia_data": None,  # Australia NEM/WEM data
                "spain_data": None,  # Spain REE data
                "france_data": None,  # France RTE data
                # Additional open API data
                "finland_data": None,  # Finland Fingrid data
                "denmark_data": None,  # Denmark Energinet data
                "belgium_data": None,  # Belgium Elia data
                "germany_data": None,  # Germany SMARD data
                "poland_data": None,  # Poland PSE data
                "italy_data": None,  # Italy Terna data
                "ontario_data": None,  # Ontario IESO data
                "alberta_data": None,  # Alberta AESO data
                "new_zealand_data": None,  # New Zealand Transpower data
                "watttime_data": None,  # WattTime global emissions
            }
            
            # Get regional carbon intensity data
            if self.postcode or self.region_id:
                data["regional_data"] = await self.carbon_client.get_regional_data(
                    postcode=self.postcode,
                    region_id=self.region_id,
                )
                
                # Store location for OSM queries
                if data["regional_data"]:
                    # Use postcode geocoding from HA or approximate
                    # For now, we'll get it from infrastructure if available
                    pass
                
                # Get 24hr forecast
                data["forecast"] = await self.carbon_client.get_intensity_forecast(
                    hours=24,
                    postcode=self.postcode,
                    region_id=self.region_id,
                )
            
            # Get all regions for the map
            data["all_regions"] = await self.carbon_client.get_all_regions()
            
            # Get live faults if enabled
            if self.show_live_faults:
                data["live_faults"] = await self.ukpn_client.get_live_faults(limit=50)
            
            # Get infrastructure data (cached, less frequent updates)
            if self.show_infrastructure:
                import time
                now = time.time()
                if now - self._infrastructure_last_update > self._infrastructure_update_interval:
                    await self._update_infrastructure()
                    self._infrastructure_last_update = now
                
                data["substations"] = self._cached_substations
                data["power_lines"] = self._cached_lines
                data["embedded_generation"] = self._cached_generation
                data["osm_features"] = self._cached_osm_features
            
            # Fetch from additional APIs (in parallel where possible)
            await self._fetch_additional_data(data)
            
            return data
            
        except Exception as e:
            _LOGGER.error("Error fetching HAGrid data: %s", e)
            raise UpdateFailed(f"Error fetching data: {e}") from e
    
    async def _fetch_additional_data(self, data: dict[str, Any]) -> None:
        """Fetch data from additional API sources."""
        tasks = []
        
        # Elexon BMRS data (free, no API key) - GRANULAR METERED DATA
        if self.elexon_client:
            tasks.append(self._fetch_elexon_data(data))
        
        # NESO data (free, no API key)
        if self.neso_client:
            tasks.append(self._fetch_neso_data(data))
        
        # National Grid data (requires API key)
        if self.national_grid_client:
            tasks.append(self._fetch_national_grid_data(data))
        
        # SSEN data (requires API key)
        if self.ssen_client:
            tasks.append(self._fetch_ssen_data(data))
        
        # Energy Dashboard data (requires API key)
        if self.energy_dashboard_client:
            tasks.append(self._fetch_energy_dashboard_data(data))
        
        # Global API data fetching
        if self.electricity_maps_client:
            tasks.append(self._fetch_electricity_maps_data(data))
        
        if self.eia_client:
            tasks.append(self._fetch_eia_data(data))
        
        if self.entsoe_client:
            tasks.append(self._fetch_entsoe_data(data))
        
        if self.openelectricity_client:
            tasks.append(self._fetch_australia_data(data))
        
        if self.ree_esios_client:
            tasks.append(self._fetch_spain_data(data))
        
        if self.rte_client:
            tasks.append(self._fetch_france_data(data))
        
        # Additional open API data fetching
        if self.fingrid_client:
            tasks.append(self._fetch_finland_data(data))
        
        if self.energinet_client:
            tasks.append(self._fetch_denmark_data(data))
        
        if self.elia_client:
            tasks.append(self._fetch_belgium_data(data))
        
        if self.smard_client:
            tasks.append(self._fetch_germany_data(data))
        
        if self.pse_client:
            tasks.append(self._fetch_poland_data(data))
        
        if self.terna_client:
            tasks.append(self._fetch_italy_data(data))
        
        if self.ieso_client:
            tasks.append(self._fetch_ontario_data(data))
        
        if self.aeso_client:
            tasks.append(self._fetch_alberta_data(data))
        
        if self.transpower_client:
            tasks.append(self._fetch_new_zealand_data(data))
        
        if self.watttime_client:
            tasks.append(self._fetch_watttime_data(data))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _fetch_elexon_data(self, data: dict[str, Any]) -> None:
        """Fetch granular metered circuit data from Elexon BMRS."""
        try:
            if not self.elexon_client:
                return
            
            # Get comprehensive grid summary (includes all metered data)
            grid_summary = await self.elexon_client.get_grid_summary()
            data["grid_summary"] = grid_summary
            
            # Get individual circuit flows
            circuit_flows = await self.elexon_client.get_circuit_flows()
            data["circuit_flows"] = circuit_flows
            
            # Get detailed generation by fuel type
            generation = await self.elexon_client.get_generation_by_fuel_type()
            data["generation_by_fuel"] = generation
            
            # Get interconnector flows
            interconnectors = await self.elexon_client.get_interconnector_flows()
            data["interconnector_flows"] = interconnectors
            
            # Get system frequency
            frequency = await self.elexon_client.get_system_frequency()
            data["system_frequency"] = frequency
            
            # Get national demand
            demand = await self.elexon_client.get_demand_outturn()
            data["demand"] = demand
            
            _LOGGER.debug(
                "Elexon data: %d circuits, %.1f Hz, %.0f MW demand",
                len(circuit_flows),
                frequency.frequency_hz if frequency else 0,
                demand.demand_mw if demand else 0,
            )
        except Exception as e:
            _LOGGER.debug("Error fetching Elexon data: %s", e)
    
    async def _fetch_neso_data(self, data: dict[str, Any]) -> None:
        """Fetch NESO embedded forecasts."""
        try:
            if self.neso_client:
                forecasts = await self.neso_client.get_embedded_forecasts()
                data["neso_data"] = {
                    "embedded_forecasts": forecasts,
                }
        except Exception as e:
            _LOGGER.debug("Error fetching NESO data: %s", e)
    
    async def _fetch_national_grid_data(self, data: dict[str, Any]) -> None:
        """Fetch National Grid ECR data."""
        try:
            if self.national_grid_client:
                substations = await self.national_grid_client.get_primary_substations()
                data["national_grid_data"] = {
                    "substations": substations,
                }
        except Exception as e:
            _LOGGER.debug("Error fetching National Grid data: %s", e)
    
    async def _fetch_ssen_data(self, data: dict[str, Any]) -> None:
        """Fetch SSEN network data."""
        try:
            if self.ssen_client:
                network = await self.ssen_client.get_network_data()
                data["ssen_data"] = {
                    "network": network,
                }
        except Exception as e:
            _LOGGER.debug("Error fetching SSEN data: %s", e)
    
    async def _fetch_energy_dashboard_data(self, data: dict[str, Any]) -> None:
        """Fetch Energy Dashboard data."""
        try:
            if self.energy_dashboard_client:
                generation = await self.energy_dashboard_client.get_generation_latest()
                data["energy_dashboard_data"] = {
                    "generation": generation,
                }
        except Exception as e:
            _LOGGER.debug("Error fetching Energy Dashboard data: %s", e)
    
    # === Global API Data Fetching Methods ===
    
    async def _fetch_electricity_maps_data(self, data: dict[str, Any]) -> None:
        """Fetch data from Electricity Maps API (global coverage)."""
        try:
            if not self.electricity_maps_client:
                return
            
            zone = self._electricity_maps_zone
            
            # Get carbon intensity for configured zone
            carbon = await self.electricity_maps_client.get_carbon_intensity(zone)
            data["global_carbon"] = carbon
            
            # Get power breakdown (generation mix by source)
            power_breakdown = await self.electricity_maps_client.get_power_breakdown(zone)
            data["global_power_breakdown"] = power_breakdown
            
            if carbon:
                _LOGGER.debug(
                    "Electricity Maps (%s): %d gCO2/kWh",
                    zone,
                    carbon.carbon_intensity,
                )
        except Exception as e:
            _LOGGER.debug("Error fetching Electricity Maps data: %s", e)
    
    async def _fetch_eia_data(self, data: dict[str, Any]) -> None:
        """Fetch data from EIA API (USA grid data)."""
        try:
            if not self.eia_client:
                return
            
            region = self._eia_region
            
            # Get hourly grid monitor data (demand, generation, net imports)
            grid_data = await self.eia_client.get_hourly_grid_monitor(region)
            demand = await self.eia_client.get_demand(region)
            
            data["eia_data"] = {
                "region": region,
                "grid_monitor": grid_data,
                "demand": demand,
            }
            
            if demand:
                _LOGGER.debug(
                    "EIA (%s): %.0f MW demand",
                    region,
                    demand.get("value", 0) if isinstance(demand, dict) else 0,
                )
        except Exception as e:
            _LOGGER.debug("Error fetching EIA data: %s", e)
    
    async def _fetch_entsoe_data(self, data: dict[str, Any]) -> None:
        """Fetch data from ENTSO-E API (European grid data)."""
        try:
            if not self.entsoe_client:
                return
            
            area = self._entsoe_area
            
            # Get generation by type and total load
            generation = await self.entsoe_client.get_generation_per_type(area)
            load = await self.entsoe_client.get_total_load(area)
            
            data["entsoe_data"] = {
                "area": area,
                "generation_by_type": generation,
                "total_load": load,
            }
            
            _LOGGER.debug(
                "ENTSO-E (%s): generation and load data retrieved",
                area,
            )
        except Exception as e:
            _LOGGER.debug("Error fetching ENTSO-E data: %s", e)
    
    async def _fetch_australia_data(self, data: dict[str, Any]) -> None:
        """Fetch data from OpenElectricity API (Australia NEM/WEM)."""
        try:
            if not self.openelectricity_client:
                return
            
            region = self._australia_region
            
            # Get network data and carbon intensity
            network_data = await self.openelectricity_client.get_network_data(region)
            carbon = await self.openelectricity_client.get_carbon_intensity(region)
            
            data["australia_data"] = {
                "region": region,
                "network": network_data,
                "carbon_intensity": carbon,
            }
            
            _LOGGER.debug("OpenElectricity (%s): data retrieved", region)
        except Exception as e:
            _LOGGER.debug("Error fetching Australia data: %s", e)
    
    async def _fetch_spain_data(self, data: dict[str, Any]) -> None:
        """Fetch data from REE Esios API (Spain grid data)."""
        try:
            if not self.ree_esios_client:
                return
            
            # Get generation structure and CO2-free percentage
            generation = await self.ree_esios_client.get_generation_structure()
            co2_free = await self.ree_esios_client.get_carbon_free_percentage()
            
            data["spain_data"] = {
                "region": self._spain_region,
                "generation_structure": generation,
                "co2_free_percentage": co2_free,
            }
            
            if co2_free:
                _LOGGER.debug("REE Esios (Spain): %.1f%% CO2-free", co2_free)
        except Exception as e:
            _LOGGER.debug("Error fetching Spain data: %s", e)
    
    async def _fetch_france_data(self, data: dict[str, Any]) -> None:
        """Fetch data from RTE API (France grid data)."""
        try:
            if not self.rte_client:
                return
            
            # Get actual generation and consumption
            generation = await self.rte_client.get_actual_generation()
            consumption = await self.rte_client.get_consumption()
            
            data["france_data"] = {
                "generation": generation,
                "consumption": consumption,
            }
            
            _LOGGER.debug("RTE (France): generation and consumption data retrieved")
        except Exception as e:
            _LOGGER.debug("Error fetching France data: %s", e)
    
    # === Additional Open API Fetch Methods ===
    
    async def _fetch_finland_data(self, data: dict[str, Any]) -> None:
        """Fetch data from Fingrid API (Finland grid data)."""
        try:
            if not self.fingrid_client:
                return
            
            power_breakdown = await self.fingrid_client.get_power_breakdown()
            frequency = await self.fingrid_client.get_frequency()
            
            data["finland_data"] = {
                "power_breakdown": power_breakdown,
                "frequency": frequency,
            }
            
            if power_breakdown:
                _LOGGER.debug(
                    "Fingrid (Finland): %.0f MW production, %.0f MW consumption",
                    power_breakdown.power_production_mw or 0,
                    power_breakdown.power_consumption_mw or 0,
                )
        except Exception as e:
            _LOGGER.debug("Error fetching Finland data: %s", e)
    
    async def _fetch_denmark_data(self, data: dict[str, Any]) -> None:
        """Fetch data from Energinet API (Denmark grid data)."""
        try:
            if not self.energinet_client:
                return
            
            co2 = await self.energinet_client.get_co2_emission()
            power_breakdown = await self.energinet_client.get_production_consumption()
            prices = await self.energinet_client.get_day_ahead_prices()
            
            data["denmark_data"] = {
                "co2_emission": co2,
                "power_breakdown": power_breakdown,
                "day_ahead_price": prices,
            }
            
            if co2:
                _LOGGER.debug("Energinet (Denmark): %d gCO2/kWh", co2.carbon_intensity)
        except Exception as e:
            _LOGGER.debug("Error fetching Denmark data: %s", e)
    
    async def _fetch_belgium_data(self, data: dict[str, Any]) -> None:
        """Fetch data from Elia API (Belgium grid data)."""
        try:
            if not self.elia_client:
                return
            
            power_breakdown = await self.elia_client.get_power_breakdown()
            imbalance = await self.elia_client.get_current_imbalance()
            load = await self.elia_client.get_total_load()
            
            data["belgium_data"] = {
                "power_breakdown": power_breakdown,
                "imbalance": imbalance,
                "total_load": load,
            }
            
            if load:
                _LOGGER.debug("Elia (Belgium): %.0f MW load", load)
        except Exception as e:
            _LOGGER.debug("Error fetching Belgium data: %s", e)
    
    async def _fetch_germany_data(self, data: dict[str, Any]) -> None:
        """Fetch data from SMARD API (Germany grid data)."""
        try:
            if not self.smard_client:
                return
            
            generation_mix = await self.smard_client.get_generation_mix()
            consumption = await self.smard_client.get_consumption()
            price = await self.smard_client.get_day_ahead_price()
            
            data["germany_data"] = {
                "generation_mix": generation_mix,
                "consumption": consumption,
                "day_ahead_price": price,
            }
            
            if generation_mix:
                # Calculate renewable percentage from generation_by_source
                renewables = ["wind", "solar", "hydro", "biomass", "wind_onshore", "wind_offshore"]
                total = sum(generation_mix.generation_by_source.values())
                renewable_mw = sum(
                    mw for fuel, mw in generation_mix.generation_by_source.items()
                    if any(r in fuel.lower() for r in renewables)
                )
                renewable_pct = (renewable_mw / total * 100) if total > 0 else 0
                _LOGGER.debug(
                    "SMARD (Germany): %.0f MW production, %.1f%% renewable",
                    generation_mix.power_production_mw or 0,
                    renewable_pct,
                )
        except Exception as e:
            _LOGGER.debug("Error fetching Germany data: %s", e)
    
    async def _fetch_poland_data(self, data: dict[str, Any]) -> None:
        """Fetch data from PSE API (Poland grid data)."""
        try:
            if not self.pse_client:
                return
            
            generation = await self.pse_client.get_generation()
            frequency = await self.pse_client.get_frequency()
            cross_border = await self.pse_client.get_cross_border_flows()
            
            data["poland_data"] = {
                "generation": generation,
                "frequency": frequency,
                "cross_border_flows": cross_border,
            }
            
            if generation:
                _LOGGER.debug(
                    "PSE (Poland): %.0f MW production",
                    generation.power_production_mw or 0,
                )
        except Exception as e:
            _LOGGER.debug("Error fetching Poland data: %s", e)
    
    async def _fetch_italy_data(self, data: dict[str, Any]) -> None:
        """Fetch data from Terna API (Italy grid data)."""
        try:
            if not self.terna_client:
                return
            
            generation = await self.terna_client.get_generation_by_source()
            demand = await self.terna_client.get_real_time_demand()
            
            data["italy_data"] = {
                "generation": generation,
                "demand": demand,
            }
            
            if demand:
                _LOGGER.debug("Terna (Italy): %.0f MW demand", demand)
        except Exception as e:
            _LOGGER.debug("Error fetching Italy data: %s", e)
    
    async def _fetch_ontario_data(self, data: dict[str, Any]) -> None:
        """Fetch data from IESO API (Ontario, Canada grid data)."""
        try:
            if not self.ieso_client:
                return
            
            generation = await self.ieso_client.get_generation_output()
            demand = await self.ieso_client.get_demand()
            
            data["ontario_data"] = {
                "generation": generation,
                "demand": demand,
            }
            
            if generation:
                # Calculate renewable percentage from generation_by_source
                renewables = ["wind", "solar", "hydro", "biomass"]
                total = sum(generation.generation_by_source.values())
                renewable_mw = sum(
                    mw for fuel, mw in generation.generation_by_source.items()
                    if any(r in fuel.lower() for r in renewables)
                )
                renewable_pct = (renewable_mw / total * 100) if total > 0 else 0
                _LOGGER.debug(
                    "IESO (Ontario): %.0f MW production, %.1f%% renewable",
                    generation.power_production_mw or 0,
                    renewable_pct,
                )
        except Exception as e:
            _LOGGER.debug("Error fetching Ontario data: %s", e)
    
    async def _fetch_alberta_data(self, data: dict[str, Any]) -> None:
        """Fetch data from AESO API (Alberta, Canada grid data)."""
        try:
            if not self.aeso_client:
                return
            
            generation = await self.aeso_client.get_generation()
            price = await self.aeso_client.get_pool_price()
            
            data["alberta_data"] = {
                "generation": generation,
                "pool_price": price,
            }
            
            if price:
                _LOGGER.debug("AESO (Alberta): $%.2f CAD/MWh", price.price)
        except Exception as e:
            _LOGGER.debug("Error fetching Alberta data: %s", e)
    
    async def _fetch_new_zealand_data(self, data: dict[str, Any]) -> None:
        """Fetch data from Transpower API (New Zealand grid data)."""
        try:
            if not self.transpower_client:
                return
            
            power_data = await self.transpower_client.get_power_data()
            hvdc = await self.transpower_client.get_hvdc_transfer()
            
            data["new_zealand_data"] = {
                "power_data": power_data,
                "hvdc_transfer": hvdc,
            }
            
            if power_data:
                # Calculate renewable percentage from generation_by_source
                renewables = ["wind", "solar", "hydro", "geothermal"]
                total = sum(power_data.generation_by_source.values())
                renewable_mw = sum(
                    mw for fuel, mw in power_data.generation_by_source.items()
                    if any(r in fuel.lower() for r in renewables)
                )
                renewable_pct = (renewable_mw / total * 100) if total > 0 else 0
                _LOGGER.debug(
                    "Transpower (NZ): %.1f%% renewable",
                    renewable_pct,
                )
        except Exception as e:
            _LOGGER.debug("Error fetching New Zealand data: %s", e)
    
    async def _fetch_watttime_data(self, data: dict[str, Any]) -> None:
        """Fetch data from WattTime API (global marginal emissions)."""
        try:
            if not self.watttime_client:
                return
            
            # Use Electricity Maps zone or default to GB
            zone = self._electricity_maps_zone or "GB"
            
            # Try to get region from configured zone
            carbon = await self.watttime_client.get_index(zone)
            marginal = await self.watttime_client.get_marginal_emissions(zone)
            
            data["watttime_data"] = {
                "carbon_index": carbon,
                "marginal_emissions": marginal,
            }
            
            if carbon:
                _LOGGER.debug("WattTime (%s): index %d", zone, carbon.carbon_intensity)
        except Exception as e:
            _LOGGER.debug("Error fetching WattTime data: %s", e)
    
    async def _update_infrastructure(self) -> None:
        """Update cached infrastructure data."""
        if self.ukpn_client is None:
            _LOGGER.warning("UKPN client not initialized")
            return
            
        try:
            # Fetch infrastructure data in parallel
            results = await asyncio.gather(
                self.ukpn_client.get_grid_primary_substations(limit=200),
                self.ukpn_client.get_secondary_substations(limit=500),
                self.ukpn_client.get_overhead_lines_33kv(limit=200),
                self.ukpn_client.get_overhead_lines_hv(limit=200),
                self.ukpn_client.get_embedded_generation(limit=200),
                return_exceptions=True,
            )
            
            # Process results with type checking
            if isinstance(results[0], list):
                self._cached_substations = results[0]
            if isinstance(results[1], list):
                self._cached_substations.extend(results[1])
            if isinstance(results[2], list):
                self._cached_lines = results[2]
            if isinstance(results[3], list):
                self._cached_lines.extend(results[3])
            if isinstance(results[4], list):
                self._cached_generation = results[4]
            
            _LOGGER.debug(
                "Infrastructure updated: %d substations, %d lines, %d generation sites",
                len(self._cached_substations),
                len(self._cached_lines),
                len(self._cached_generation),
            )
            
            # Fetch OSM data if enabled and we have location
            if self.include_osm_data and self.overpass_client:
                await self._update_osm_data()
                
        except Exception as e:
            _LOGGER.error("Error updating infrastructure: %s", e)
    
    async def _update_osm_data(self) -> None:
        """Update OSM power infrastructure data."""
        if not self.overpass_client:
            return
        
        # Get location from first substation or use approximate UK center
        lat, lon = 51.5074, -0.1278  # Default to London
        if self._cached_substations:
            first_sub = self._cached_substations[0]
            if first_sub.latitude and first_sub.longitude:
                lat, lon = first_sub.latitude, first_sub.longitude
        
        try:
            osm_features = await self.overpass_client.get_power_infrastructure(
                lat=lat,
                lon=lon,
                radius_km=self.osm_radius_km,
            )
            self._cached_osm_features = osm_features
            _LOGGER.debug(
                "OSM data updated: %d power features within %d km",
                len(osm_features),
                self.osm_radius_km,
            )
        except Exception as e:
            _LOGGER.debug("Error fetching OSM data: %s", e)
    
    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._session:
            await self._session.close()
            self._session = None
    
    @property
    def carbon_intensity(self) -> int | None:
        """Get current carbon intensity."""
        if self.data and self.data.get("regional_data"):
            return self.data["regional_data"].intensity.forecast
        return None
    
    @property
    def carbon_index(self) -> str | None:
        """Get current carbon intensity index."""
        if self.data and self.data.get("regional_data"):
            return self.data["regional_data"].intensity.index
        return None
    
    @property
    def generation_mix(self) -> list[dict] | None:
        """Get current generation mix."""
        if self.data and self.data.get("regional_data"):
            return [
                {"fuel": g.fuel, "percentage": g.percentage}
                for g in self.data["regional_data"].generation_mix
            ]
        return None
    
    @property
    def region_name(self) -> str | None:
        """Get region name."""
        if self.data and self.data.get("regional_data"):
            return self.data["regional_data"].short_name
        return None
    
    @property
    def dno_name(self) -> str | None:
        """Get DNO name."""
        if self.data and self.data.get("regional_data"):
            return self.data["regional_data"].dno_region
        return None
    
    @property
    def live_fault_count(self) -> int:
        """Get count of live faults."""
        if self.data:
            return len(self.data.get("live_faults", []))
        return 0
    
    @property
    def system_frequency(self) -> float | None:
        """Get current system frequency in Hz."""
        if self.data and self.data.get("system_frequency"):
            return self.data["system_frequency"].frequency_hz
        return None
    
    @property
    def national_demand(self) -> float | None:
        """Get current national demand in MW."""
        if self.data and self.data.get("demand"):
            return self.data["demand"].demand_mw
        return None
    
    @property
    def total_generation(self) -> float | None:
        """Get total generation in MW."""
        if self.data and self.data.get("grid_summary"):
            return self.data["grid_summary"].get("total_generation_mw")
        return None
    
    @property
    def net_imports(self) -> float | None:
        """Get net imports in MW (positive = importing, negative = exporting)."""
        if self.data and self.data.get("grid_summary"):
            return self.data["grid_summary"].get("net_import_mw")
        return None
    
    @property
    def circuit_flow_count(self) -> int:
        """Get count of metered circuit flows."""
        if self.data:
            return len(self.data.get("circuit_flows", []))
        return 0
    
    # === Global Data Properties ===
    
    @property
    def global_carbon_intensity(self) -> int | None:
        """Get global carbon intensity from Electricity Maps."""
        if self.data and self.data.get("global_carbon"):
            return self.data["global_carbon"].carbon_intensity
        return None
    
    @property
    def global_carbon_zone(self) -> str | None:
        """Get the configured Electricity Maps zone."""
        return self._electricity_maps_zone if self._electricity_maps_api_key else None
    
    @property
    def global_fossil_fuel_percentage(self) -> float | None:
        """Get fossil fuel percentage from Electricity Maps."""
        if self.data and self.data.get("global_carbon"):
            return self.data["global_carbon"].fossil_fuel_percentage
        return None
    
    @property
    def global_renewable_percentage(self) -> float | None:
        """Get renewable percentage from power breakdown."""
        if self.data and self.data.get("global_power_breakdown"):
            breakdown = self.data["global_power_breakdown"]
            return breakdown.renewable_percentage
        return None
    
    @property
    def eia_demand(self) -> float | None:
        """Get USA demand from EIA."""
        if self.data and self.data.get("eia_data"):
            demand_data = self.data["eia_data"].get("demand")
            if demand_data and isinstance(demand_data, dict):
                return demand_data.get("value")
        return None
    
    @property
    def eia_region(self) -> str | None:
        """Get configured EIA region."""
        return self._eia_region if self._eia_api_key else None
    
    @property
    def entsoe_area(self) -> str | None:
        """Get configured ENTSO-E area."""
        return self._entsoe_area if self._entsoe_api_key else None
    
    @property
    def spain_co2_free_percentage(self) -> float | None:
        """Get Spain CO2-free percentage."""
        if self.data and self.data.get("spain_data"):
            return self.data["spain_data"].get("co2_free_percentage")
        return None
    
    @property
    def active_global_sources(self) -> list[str]:
        """Get list of active global data sources."""
        sources = []
        if self.electricity_maps_client:
            sources.append(f"Electricity Maps ({self._electricity_maps_zone})")
        if self.eia_client:
            sources.append(f"EIA ({self._eia_region})")
        if self.entsoe_client:
            sources.append(f"ENTSO-E ({self._entsoe_area})")
        if self.openelectricity_client:
            sources.append(f"OpenElectricity ({self._australia_region})")
        if self.ree_esios_client:
            sources.append("REE Esios (Spain)")
        if self.rte_client:
            sources.append("RTE (France)")
        return sources
    
    @property
    def map_data(self) -> dict[str, Any]:
        """Get data formatted for the map card."""
        if not self.data:
            return {}
        
        return {
            "regions": [
                {
                    "id": r.region_id,
                    "name": r.short_name,
                    "dno": r.dno_region,
                    "intensity": r.intensity.forecast,
                    "index": r.intensity.index,
                    "generation_mix": [
                        {"fuel": g.fuel, "percentage": g.percentage}
                        for g in r.generation_mix
                    ],
                }
                for r in self.data.get("all_regions", [])
            ],
            "faults": [
                {
                    "id": f.id,
                    "type": f.incident_type,
                    "status": f.status,
                    "postcode": f.postcode_area,
                    "customers": f.estimated_customers,
                    "lat": f.latitude,
                    "lon": f.longitude,
                }
                for f in self.data.get("live_faults", [])
                if f.latitude and f.longitude
            ],
            "substations": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.substation_type,
                    "lat": s.latitude,
                    "lon": s.longitude,
                    "capacity": s.capacity_mva,
                }
                for s in self.data.get("substations", [])
            ],
            "lines": [
                {
                    "id": l.id,
                    "type": l.line_type,
                    "voltage": l.voltage,
                    "coordinates": l.coordinates,
                }
                for l in self.data.get("power_lines", [])
            ],
            "generation": [
                {
                    "id": g.id,
                    "name": g.name,
                    "technology": g.technology,
                    "capacity_mw": g.capacity_mw,
                    "lat": g.latitude,
                    "lon": g.longitude,
                }
                for g in self.data.get("embedded_generation", [])
            ],
            "forecast": [
                {
                    "from": f.from_time.isoformat(),
                    "to": f.to_time.isoformat(),
                    "intensity": f.forecast,
                    "index": f.index,
                }
                for f in self.data.get("forecast", [])
            ],
            "osm_features": [
                {
                    "id": o.osm_id,
                    "type": o.power_type,
                    "name": o.name,
                    "operator": o.operator,
                    "voltage": o.voltage,
                    "lat": o.lat,
                    "lon": o.lon,
                    "tags": o.tags,
                }
                for o in self.data.get("osm_features", [])
            ],
            # Granular metered circuit flow data
            "circuit_flows": [
                {
                    "id": c.circuit_id,
                    "type": c.circuit_type,
                    "name": c.name,
                    "flow_mw": c.flow_mw,
                    "capacity_mw": c.capacity_mw,
                    "direction": c.direction,
                    "fuel_type": c.fuel_type,
                    "timestamp": c.timestamp.isoformat(),
                }
                for c in self.data.get("circuit_flows", [])
            ],
            "interconnectors": [
                {
                    "id": ic.interconnector_id,
                    "name": ic.name,
                    "country": ic.country,
                    "flow_mw": ic.flow_mw,
                    "capacity_mw": ic.capacity_mw,
                    "utilization_pct": ic.utilization_pct,
                    "direction": "import" if ic.flow_mw >= 0 else "export",
                }
                for ic in self.data.get("interconnector_flows", [])
            ],
            "generation_by_fuel": [
                {
                    "fuel": g.fuel_type,
                    "output_mw": g.output_mw,
                    "percentage": g.percentage,
                }
                for g in self.data.get("generation_by_fuel", [])
            ],
            "system": {
                "frequency_hz": self.data.get("system_frequency").frequency_hz 
                    if self.data.get("system_frequency") else None,
                "demand_mw": self.data.get("demand").demand_mw 
                    if self.data.get("demand") else None,
                "total_generation_mw": self.data.get("grid_summary", {}).get("total_generation_mw"),
                "net_import_mw": self.data.get("grid_summary", {}).get("net_import_mw"),
            },
            # Global API data
            "global": {
                "electricity_maps": {
                    "zone": self._electricity_maps_zone if self.electricity_maps_client else None,
                    "carbon_intensity": self.data.get("global_carbon").carbon_intensity 
                        if self.data.get("global_carbon") else None,
                    "fossil_fuel_pct": self.data.get("global_carbon").fossil_fuel_percentage 
                        if self.data.get("global_carbon") else None,
                    "power_breakdown": {
                        "renewable_pct": self.data.get("global_power_breakdown").renewable_percentage
                            if self.data.get("global_power_breakdown") else None,
                    } if self.data.get("global_power_breakdown") else None,
                } if self.electricity_maps_client else None,
                "eia": self.data.get("eia_data"),
                "entsoe": self.data.get("entsoe_data"),
                "australia": self.data.get("australia_data"),
                "spain": self.data.get("spain_data"),
                "france": self.data.get("france_data"),
                "active_sources": self.active_global_sources,
            },
        }
