"""Constants for HAGrid integration."""

DOMAIN = "hagrid"
PLATFORMS = ["sensor"]

# Config - User settings
CONF_POSTCODE = "postcode"
CONF_REGION_ID = "region_id"
CONF_DNO = "dno"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_SHOW_INFRASTRUCTURE = "show_infrastructure"
CONF_SHOW_LIVE_FAULTS = "show_live_faults"
CONF_INCLUDE_OSM_DATA = "include_osm_data"
CONF_OSM_RADIUS_KM = "osm_radius_km"

# Config - API Keys (stored securely in config entry)
CONF_NATIONAL_GRID_API_KEY = "national_grid_api_key"
CONF_SSEN_NERDA_API_KEY = "ssen_nerda_api_key"
CONF_ENERGY_DASHBOARD_API_KEY = "energy_dashboard_api_key"

# Global API Keys
CONF_ELECTRICITY_MAPS_API_KEY = "electricity_maps_api_key"
CONF_EIA_API_KEY = "eia_api_key"
CONF_ENTSOE_API_KEY = "entsoe_api_key"
CONF_RTE_CLIENT_ID = "rte_client_id"
CONF_RTE_CLIENT_SECRET = "rte_client_secret"
CONF_FINGRID_API_KEY = "fingrid_api_key"
CONF_AESO_API_KEY = "aeso_api_key"
CONF_WATTTIME_USERNAME = "watttime_username"
CONF_WATTTIME_PASSWORD = "watttime_password"

# Zone/Region Configuration
CONF_ZONE = "zone"
CONF_ENABLED_REGIONS = "enabled_regions"
CONF_ELECTRICITY_MAPS_ZONE = "electricity_maps_zone"
CONF_EIA_REGION = "eia_region"
CONF_ENTSOE_AREA = "entsoe_area"
CONF_AUSTRALIA_REGION = "australia_region"
CONF_SPAIN_REGION = "spain_region"
CONF_FRANCE_REGION = "france_region"
CONF_FINLAND_ENABLED = "finland_enabled"
CONF_DENMARK_ENABLED = "denmark_enabled"
CONF_BELGIUM_ENABLED = "belgium_enabled"
CONF_GERMANY_ENABLED = "germany_enabled"
CONF_POLAND_ENABLED = "poland_enabled"
CONF_ITALY_ENABLED = "italy_enabled"
CONF_NEW_ZEALAND_ENABLED = "new_zealand_enabled"
CONF_ONTARIO_ENABLED = "ontario_enabled"
CONF_ALBERTA_ENABLED = "alberta_enabled"
CONF_WATTTIME_ENABLED = "watttime_enabled"
CONF_CANADA_REGION = "canada_region"
CONF_US_ISO = "us_iso"

# Defaults
DEFAULT_UPDATE_INTERVAL = 300  # 5 minutes
DEFAULT_SHOW_INFRASTRUCTURE = True
DEFAULT_SHOW_LIVE_FAULTS = True
DEFAULT_INCLUDE_OSM_DATA = True
DEFAULT_OSM_RADIUS_KM = 10  # km radius for OSM queries

# API Endpoints
CARBON_INTENSITY_API = "https://api.carbonintensity.org.uk"
UKPN_API_BASE = "https://ukpowernetworks.opendatasoft.com/api/explore/v2.1"
NESO_API_BASE = "https://api.neso.energy/api/3/action"
NATIONAL_GRID_API_BASE = "https://connecteddata.nationalgrid.co.uk/api/3/action"
SSEN_NERDA_API_BASE = "https://api.nerda.ssen.co.uk/api/v1"
ENERGY_DASHBOARD_API_BASE = "https://api.energydashboard.co.uk"
OVERPASS_API = "https://overpass-api.de/api/interpreter"

# Elexon BMRS API (Free, no API key required) - Granular metered data
ELEXON_API_BASE = "https://data.elexon.co.uk/bmrs/api/v1"

# ========================================
# GLOBAL ENERGY DATA APIs
# ========================================

# Electricity Maps - Global carbon intensity & power breakdown
# Free tier: 30 requests/hour, zones available globally
# API Key required for authenticated access
ELECTRICITY_MAPS_API_BASE = "https://api.electricitymap.org/v3"

# EIA (US Energy Information Administration) - USA electricity data
# Free API, requires registration for API key
# Covers all US states, RTO regions, and facilities
EIA_API_BASE = "https://api.eia.gov/v2"

# ENTSO-E Transparency Platform - European grid data
# Free registration required for security token
# Covers 35 European countries, generation, load, cross-border flows
ENTSOE_API_BASE = "https://web-api.tp.entsoe.eu/api"

# OpenElectricity (formerly OpenNEM) - Australia NEM/WEM
# Free API, no key required
# Covers NEM (East coast) + WEM (Western Australia)
OPENELECTRICITY_API_BASE = "https://api.openelectricity.org.au/v4"

# REE/Esios - Spain (Red Eléctrica de España)
# Free API, no key required for basic data
# Real-time generation, demand, prices, CO2
REE_ESIOS_API_BASE = "https://api.esios.ree.es"

# RTE Data - France
# Free registration, OAuth2 authentication required
# Generation, consumption, cross-border flows, forecasts
RTE_API_BASE = "https://digital.iservices.rte-france.com"

# IESO - Ontario, Canada
# Free public reports, no authentication
# Real-time demand, generation, prices
IESO_API_BASE = "https://www.ieso.ca"

# CAISO - California ISO
# Free OASIS API
# Real-time generation, demand, prices
CAISO_API_BASE = "https://oasis.caiso.com/oasisapi"

# ========================================
# ADDITIONAL OPEN ENERGY APIs
# ========================================

# NORDIC REGION
# -------------

# Fingrid Open Data - Finland
# Free API key required (registration)
# Production, consumption, wind power, frequency, cross-border flows
FINGRID_API_BASE = "https://api.fingrid.fi/v1"

# Energi Data Service - Denmark (Energinet)
# Free, no authentication required
# CO2 emissions, day-ahead prices, generation, consumption
ENERGINET_API_BASE = "https://api.energidataservice.dk"

# Svenska Kraftnät - Sweden (limited API, mostly via ENTSO-E)
# Grid frequency, consumption by bidding area
SVK_API_BASE = "https://www.svk.se/api"

# Statnett - Norway (limited API, mostly via ENTSO-E)
STATNETT_API_BASE = "https://www.statnett.no/api"

# Nord Pool - Nordic electricity market
# Day-ahead prices, intraday, power system data
NORDPOOL_API_BASE = "https://data.nordpoolgroup.com/api"

# WESTERN EUROPE
# --------------

# Elia Open Data - Belgium
# Free, no authentication required
# Imbalance prices, system imbalance, wind/solar forecasts, load
ELIA_API_BASE = "https://opendata.elia.be/api/explore/v2.1"

# SMARD - Germany (Bundesnetzagentur)
# Free, no authentication required
# Renewable/conventional generation, consumption, prices
SMARD_API_BASE = "https://www.smard.de/app/chart_data"

# TenneT - Netherlands/Germany TSO
# Grid data, congestion, balancing
TENNET_API_BASE = "https://www.tennet.org/api"

# EASTERN EUROPE
# --------------

# PSE Raporty - Poland
# Free, no authentication required
# Load, generation, cross-border flows, frequency, prices
PSE_API_BASE = "https://api.raporty.pse.pl"

# CEPS - Czech Republic
# System data, generation, cross-border flows
CEPS_API_BASE = "https://www.ceps.cz/api"

# MAVIR - Hungary
# System data, generation, cross-border
MAVIR_API_BASE = "https://www.mavir.hu/api"

# SOUTHERN EUROPE
# ---------------

# Terna - Italy
# Demand, generation by source, RES percentage
TERNA_API_BASE = "https://api.terna.it/pti-api/v1"

# OMIE - Iberian electricity market (Spain/Portugal)
# Day-ahead/intraday prices
OMIE_API_BASE = "https://www.omie.es/api"

# AMERICAS
# --------

# AESO - Alberta, Canada
# Free API key required
# Pool price, supply/demand, wind/solar forecasts
AESO_API_BASE = "https://api.aeso.ca"

# Hydro-Québec - Quebec, Canada
# Generation, demand, exports
HYDROQUEBEC_API_BASE = "https://www.hydroquebec.com/data"

# PJM Interconnection - Eastern USA (13 states)
# Generation, load, prices, LMP
PJM_API_BASE = "https://api.pjm.com/api/v1"

# ERCOT - Texas
# Grid conditions, generation, prices
ERCOT_API_BASE = "https://www.ercot.com/api"

# NYISO - New York
# Generation, load, prices
NYISO_API_BASE = "https://www.nyiso.com/public/webservices"

# MISO - Midcontinent USA
# Generation, load, prices, LMP
MISO_API_BASE = "https://api.misoenergy.org/MISORTWD"

# ISO-NE - New England
# Generation, load, prices
ISONE_API_BASE = "https://www.iso-ne.com/isoexpress"

# SPP - Southwest Power Pool
# Generation, load, prices
SPP_API_BASE = "https://marketplace.spp.org/pages/rtbm-lmp-by-location"

# ASIA-PACIFIC
# ------------

# Transpower - New Zealand
# Total demand, renewables %, generation by fuel, HVDC transfer
TRANSPOWER_API_BASE = "https://www.transpower.co.nz/power-system-live-data"

# AEMO - Australia (Official)
# NEM generation, demand, emissions, prices
AEMO_API_BASE = "https://aemo.com.au/aemo/api/v1"

# Singapore EMA
# Electricity market data
EMA_SINGAPORE_API_BASE = "https://www.ema.gov.sg/api"

# Korea Power Exchange - KEPCO
# Generation, demand, prices (limited English)
KPX_API_BASE = "https://www.kpx.or.kr/api"

# TEPCO - Japan (Tokyo region)
# Demand forecast, supply
TEPCO_API_BASE = "https://www.tepco.co.jp/forecast"

# Taiwan Power Company
# Generation, demand
TAIPOWER_API_BASE = "https://www.taipower.com.tw/api"

# SOUTH AMERICA
# -------------

# ONS - Brazil Operator
# Generation, demand, reservoir levels
ONS_BRAZIL_API_BASE = "https://ons.org.br/api"

# Coordinador Eléctrico Nacional - Chile
# System operation, generation, prices
CEN_CHILE_API_BASE = "https://www.coordinador.cl/api"

# CAMMESA - Argentina
# Generation, demand, prices
CAMMESA_API_BASE = "https://cammesaweb.cammesa.com/api"

# GLOBAL / MULTI-REGION
# ---------------------

# WattTime - Global marginal emissions
# Free tier available with registration
# Marginal emissions, average emissions, health damage
WATTTIME_API_BASE = "https://api.watttime.org/v3"

# Open-Meteo - Weather (useful for renewable forecasting)
# Free, no API key
OPEN_METEO_API_BASE = "https://api.open-meteo.com/v1"

# ========================================
# REGION/ZONE CONFIGURATIONS
# ========================================

# Fingrid dataset IDs
FINGRID_DATASETS = {
    "electricity_production": 74,
    "electricity_consumption": 124,
    "wind_power_production": 75,
    "solar_power_production": 248,
    "nuclear_power_production": 188,
    "hydro_power_production": 191,
    "frequency": 177,
    "total_imports": 89,
    "total_exports": 92,
    "temperature_helsinki": 178,
}

# Energinet (Denmark) dataset names
ENERGINET_DATASETS = {
    "co2_emission": "CO2Emis",
    "co2_emission_prognosis": "CO2EmisProg",
    "day_ahead_prices": "Elspotprices",
    "production_consumption": "ProductionConsumptionSettlement",
    "declaration": "DeclarationProduction",
}

# Elia (Belgium) dataset names  
ELIA_DATASETS = {
    "imbalance_prices_1min": "ods001",
    "imbalance_prices_15min": "ods002",
    "current_system_imbalance": "ods003",
    "solar_power_estimated": "ods032",
    "wind_power_monitored": "ods033",
    "total_load": "ods007",
}

# PSE (Poland) report types
PSE_REPORTS = {
    "current_data": "biezace_dane_systemowe",
    "daily_pse": "dobowe_pse",
    "cross_border": "wymiana_transgr",
    "generation": "moc_wytworcza",
}

# New Zealand regions for Transpower
NZ_REGIONS = {
    "NI": {"name": "North Island", "includes": ["Auckland", "Wellington", "Hamilton"]},
    "SI": {"name": "South Island", "includes": ["Christchurch", "Dunedin"]},
}

# Canadian regions
CANADA_REGIONS = {
    "IESO": {"name": "Ontario", "api": IESO_API_BASE},
    "AESO": {"name": "Alberta", "api": AESO_API_BASE},
    "BCTC": {"name": "British Columbia", "api": None},
    "HQ": {"name": "Quebec", "api": HYDROQUEBEC_API_BASE},
    "NBSO": {"name": "New Brunswick", "api": None},
    "NSPI": {"name": "Nova Scotia", "api": None},
}

# US ISO/RTO regions
US_ISOS = {
    "CAISO": {"name": "California ISO", "api": CAISO_API_BASE, "states": ["CA"]},
    "ERCOT": {"name": "Electric Reliability Council of Texas", "api": ERCOT_API_BASE, "states": ["TX"]},
    "PJM": {"name": "PJM Interconnection", "api": PJM_API_BASE, "states": ["PA", "NJ", "DE", "MD", "VA", "WV", "OH", "DC", "NC", "KY", "IN", "IL", "MI"]},
    "MISO": {"name": "Midcontinent ISO", "api": MISO_API_BASE, "states": ["AR", "IL", "IN", "IA", "KY", "LA", "MI", "MN", "MS", "MO", "MT", "ND", "SD", "TX", "WI"]},
    "NYISO": {"name": "New York ISO", "api": NYISO_API_BASE, "states": ["NY"]},
    "ISONE": {"name": "ISO New England", "api": ISONE_API_BASE, "states": ["CT", "MA", "ME", "NH", "RI", "VT"]},
    "SPP": {"name": "Southwest Power Pool", "api": SPP_API_BASE, "states": ["AR", "KS", "LA", "MO", "NE", "NM", "OK", "TX"]},
}

# UK DNOs (Distribution Network Operators)
UK_DNOS = {
    "ukpn_epn": {
        "name": "UK Power Networks - Eastern",
        "short": "UKPN EPN",
        "regions": ["East England", "East Midlands"],
        "api_base": UKPN_API_BASE,
    },
    "ukpn_lpn": {
        "name": "UK Power Networks - London",
        "short": "UKPN LPN", 
        "regions": ["London"],
        "api_base": UKPN_API_BASE,
    },
    "ukpn_spn": {
        "name": "UK Power Networks - South Eastern",
        "short": "UKPN SPN",
        "regions": ["South East England", "South England"],
        "api_base": UKPN_API_BASE,
    },
    "ssen_sepd": {
        "name": "Scottish & Southern - Southern",
        "short": "SSEN SEPD",
        "regions": ["South West England", "South England"],
        "api_base": None,  # TODO: Add SSEN API
    },
    "ssen_shepd": {
        "name": "Scottish & Southern - Scottish",
        "short": "SSEN SHEPD",
        "regions": ["North Scotland", "South Scotland"],
        "api_base": None,
    },
    "enwl": {
        "name": "Electricity North West",
        "short": "ENWL",
        "regions": ["North West England"],
        "api_base": None,  # TODO: Add ENWL API
    },
    "npg_north": {
        "name": "Northern Powergrid - Northeast",
        "short": "NPG North",
        "regions": ["North East England"],
        "api_base": None,
    },
    "npg_yorkshire": {
        "name": "Northern Powergrid - Yorkshire",
        "short": "NPG Yorkshire",
        "regions": ["Yorkshire"],
        "api_base": None,
    },
    "spen_sp": {
        "name": "SP Energy Networks - SP Distribution",
        "short": "SPEN SP",
        "regions": ["South Scotland"],
        "api_base": None,
    },
    "spen_manweb": {
        "name": "SP Energy Networks - Manweb",
        "short": "SPEN Manweb",
        "regions": ["North Wales", "North West England"],
        "api_base": None,
    },
    "wpd_south_wales": {
        "name": "National Grid - South Wales",
        "short": "NGED SWales",
        "regions": ["South Wales"],
        "api_base": None,
    },
    "wpd_south_west": {
        "name": "National Grid - South West",
        "short": "NGED SWest",
        "regions": ["South West England"],
        "api_base": None,
    },
    "wpd_east_midlands": {
        "name": "National Grid - East Midlands",
        "short": "NGED EMid",
        "regions": ["East Midlands"],
        "api_base": None,
    },
    "wpd_west_midlands": {
        "name": "National Grid - West Midlands",
        "short": "NGED WMid",
        "regions": ["West Midlands"],
        "api_base": None,
    },
}

# Carbon Intensity Region IDs (from NESO API)
CARBON_REGIONS = {
    1: "North Scotland",
    2: "South Scotland",
    3: "North West England",
    4: "North East England",
    5: "Yorkshire",
    6: "North Wales",
    7: "South Wales",
    8: "West Midlands",
    9: "East Midlands",
    10: "East England",
    11: "South West England",
    12: "South England",
    13: "London",
    14: "South East England",
    15: "England",
    16: "Scotland",
    17: "Wales",
}

# Fuel type colors for visualization
FUEL_COLORS = {
    "gas": "#FF6B35",
    "coal": "#4A4A4A",
    "nuclear": "#9B59B6",
    "wind": "#3498DB",
    "solar": "#F1C40F",
    "hydro": "#1ABC9C",
    "biomass": "#27AE60",
    "imports": "#E74C3C",
    "storage": "#9B59B6",
    "other": "#95A5A6",
}

# Carbon intensity index colors
INTENSITY_COLORS = {
    "very low": "#2ECC71",
    "low": "#82E0AA",
    "moderate": "#F4D03F",
    "high": "#E67E22",
    "very high": "#E74C3C",
}

# UKPN Dataset IDs
UKPN_DATASETS = {
    "live_faults": "ukpn-live-faults",
    "grid_primary_sites": "grid-and-primary-sites",
    "secondary_sites": "ukpn-secondary-sites",
    "hv_overhead_lines": "ukpn-hv-overhead-lines-shapefile",
    "33kv_overhead_lines": "ukpn-33kv-overhead-lines",
    "embedded_capacity": "ukpn-embedded-capacity-register",
    "primary_areas": "ukpn_primary_postcode_area",
    "local_authorities": "ukpn-local-authorities",
}

# NESO Dataset Resource IDs
NESO_DATASETS = {
    "embedded_wind_solar": "db6c038f-98af-4570-ab60-24d71ebd0ae5",
    "demand_forecast": "b98095a8-310a-4fee-8d51-e20531c49465",
    "system_frequency": "f93d1c52-d053-4b11-a7b5-4d7c039e5e28",
    "generation_by_fuel": "f93d1c52-d053-4b11-a7b5-4d7c039e5e28",
}

# National Grid Dataset IDs
NATIONAL_GRID_DATASETS = {
    "embedded_capacity_register": "embedded-capacity-register",
    "primary_substations": "primary-substation-location-easting-northings",
    "distribution_substations": "distribution-substation-location-easting-northings",
    "ev_capacity_map": "electric-vehicle-capacity-map",
    "generation_capacity_register": "generation-capacity-register",
    "live_data": "live-data",
}

# OpenStreetMap Power Infrastructure Tags
OSM_POWER_TAGS = {
    "substation": "power=substation",
    "plant": "power=plant",
    "generator": "power=generator",
    "line": "power=line",
    "minor_line": "power=minor_line",
    "tower": "power=tower",
    "pole": "power=pole",
    "transformer": "power=transformer",
    "cable": "power=cable",
}

# Elexon BMRS Datasets - Granular metered circuit data
ELEXON_DATASETS = {
    # Real-time generation per unit (most granular!)
    "generation_per_unit": "/datasets/B1610",  # Actual Generation Output Per Generation Unit
    "generation_by_fuel": "/datasets/FUELINST",  # Instantaneous generation by fuel type
    "generation_half_hourly": "/datasets/FUELHH",  # Half-hourly generation outturn
    
    # Physical notifications (planned output)
    "physical_notifications": "/datasets/PN",  # Physical Notifications per BMU
    
    # Interconnector flows
    "interconnector_flows": "/generation/outturn/interconnectors",  # All interconnector flows
    
    # Demand data
    "demand_outturn": "/datasets/INDO",  # Initial National Demand Outturn
    "transmission_demand": "/datasets/ITSDO",  # Transmission System Demand Outturn
    "demand_total": "/demand/actual/total",  # Total load (ATL/B0610)
    
    # System data
    "system_frequency": "/datasets/FREQ",  # Real-time system frequency
    "system_warnings": "/datasets/SYSWARN",  # System warnings
    
    # Balancing data
    "bid_offer_acceptances": "/datasets/BOALF",  # Bid-Offer Acceptance Levels
    "balancing_volumes": "/datasets/QAS",  # Balancing Services Volume
    
    # Reference data
    "bm_units": "/reference/bmunits/all",  # All Balancing Mechanism Units
    "interconnectors": "/reference/interconnectors/all",  # All interconnectors
    "fuel_types": "/reference/fueltypes/all",  # All fuel types
}

# UK Interconnectors (for flow visualization)
UK_INTERCONNECTORS = {
    "IFA": {"name": "IFA (France)", "capacity_mw": 2000, "country": "FR"},
    "IFA2": {"name": "IFA2 (France)", "capacity_mw": 1000, "country": "FR"},
    "BritNed": {"name": "BritNed (Netherlands)", "capacity_mw": 1000, "country": "NL"},
    "NEMO": {"name": "Nemo Link (Belgium)", "capacity_mw": 1000, "country": "BE"},
    "NSL": {"name": "North Sea Link (Norway)", "capacity_mw": 1400, "country": "NO"},
    "Viking": {"name": "Viking Link (Denmark)", "capacity_mw": 1400, "country": "DK"},
    "ElecLink": {"name": "ElecLink (France)", "capacity_mw": 1000, "country": "FR"},
    "Moyle": {"name": "Moyle (N.Ireland)", "capacity_mw": 500, "country": "NI"},
    "EWIC": {"name": "East-West (Ireland)", "capacity_mw": 500, "country": "IE"},
    "Greenlink": {"name": "Greenlink (Ireland)", "capacity_mw": 500, "country": "IE"},
}

# ========================================
# ELECTRICITY MAPS ZONES
# ========================================
# Full list at: https://app.electricitymaps.com/zone
ELECTRICITY_MAPS_ZONES = {
    # UK & Ireland
    "GB": {"name": "Great Britain", "country": "UK"},
    "GB-NIR": {"name": "Northern Ireland", "country": "UK"},
    "IE": {"name": "Ireland", "country": "IE"},
    
    # Europe
    "DE": {"name": "Germany", "country": "DE"},
    "FR": {"name": "France", "country": "FR"},
    "ES": {"name": "Spain", "country": "ES"},
    "IT-NORD": {"name": "Italy - North", "country": "IT"},
    "IT-CNOR": {"name": "Italy - Central North", "country": "IT"},
    "IT-CSUD": {"name": "Italy - Central South", "country": "IT"},
    "IT-SUD": {"name": "Italy - South", "country": "IT"},
    "IT-SICI": {"name": "Italy - Sicily", "country": "IT"},
    "IT-SARD": {"name": "Italy - Sardinia", "country": "IT"},
    "NL": {"name": "Netherlands", "country": "NL"},
    "BE": {"name": "Belgium", "country": "BE"},
    "AT": {"name": "Austria", "country": "AT"},
    "CH": {"name": "Switzerland", "country": "CH"},
    "PL": {"name": "Poland", "country": "PL"},
    "CZ": {"name": "Czech Republic", "country": "CZ"},
    "DK-DK1": {"name": "Denmark - West", "country": "DK"},
    "DK-DK2": {"name": "Denmark - East", "country": "DK"},
    "NO-NO1": {"name": "Norway - Southeast", "country": "NO"},
    "NO-NO2": {"name": "Norway - Southwest", "country": "NO"},
    "NO-NO3": {"name": "Norway - Mid", "country": "NO"},
    "NO-NO4": {"name": "Norway - North", "country": "NO"},
    "NO-NO5": {"name": "Norway - West", "country": "NO"},
    "SE-SE1": {"name": "Sweden - North", "country": "SE"},
    "SE-SE2": {"name": "Sweden - North-Central", "country": "SE"},
    "SE-SE3": {"name": "Sweden - South-Central", "country": "SE"},
    "SE-SE4": {"name": "Sweden - South", "country": "SE"},
    "FI": {"name": "Finland", "country": "FI"},
    "PT": {"name": "Portugal", "country": "PT"},
    "GR": {"name": "Greece", "country": "GR"},
    "RO": {"name": "Romania", "country": "RO"},
    "BG": {"name": "Bulgaria", "country": "BG"},
    "HU": {"name": "Hungary", "country": "HU"},
    "SK": {"name": "Slovakia", "country": "SK"},
    "SI": {"name": "Slovenia", "country": "SI"},
    "HR": {"name": "Croatia", "country": "HR"},
    "RS": {"name": "Serbia", "country": "RS"},
    "BA": {"name": "Bosnia Herzegovina", "country": "BA"},
    "EE": {"name": "Estonia", "country": "EE"},
    "LV": {"name": "Latvia", "country": "LV"},
    "LT": {"name": "Lithuania", "country": "LT"},
    
    # North America
    "US-CAL-CISO": {"name": "California ISO", "country": "US"},
    "US-TEX-ERCO": {"name": "Texas ERCOT", "country": "US"},
    "US-NY-NYIS": {"name": "New York ISO", "country": "US"},
    "US-NE-ISNE": {"name": "New England ISO", "country": "US"},
    "US-MIDW-MISO": {"name": "MISO (Midwest)", "country": "US"},
    "US-MIDA-PJM": {"name": "PJM (Mid-Atlantic)", "country": "US"},
    "US-SW-SRP": {"name": "Salt River Project", "country": "US"},
    "US-NW-BPAT": {"name": "Bonneville Power", "country": "US"},
    "US-FLA-FPC": {"name": "Duke Florida", "country": "US"},
    "CA-ON": {"name": "Ontario", "country": "CA"},
    "CA-QC": {"name": "Quebec", "country": "CA"},
    "CA-AB": {"name": "Alberta", "country": "CA"},
    "CA-BC": {"name": "British Columbia", "country": "CA"},
    
    # Australia & NZ
    "AU-NSW": {"name": "New South Wales", "country": "AU"},
    "AU-VIC": {"name": "Victoria", "country": "AU"},
    "AU-QLD": {"name": "Queensland", "country": "AU"},
    "AU-SA": {"name": "South Australia", "country": "AU"},
    "AU-TAS": {"name": "Tasmania", "country": "AU"},
    "AU-WA": {"name": "Western Australia", "country": "AU"},
    "NZ": {"name": "New Zealand", "country": "NZ"},
    
    # Asia
    "JP-TK": {"name": "Japan - Tokyo", "country": "JP"},
    "JP-CB": {"name": "Japan - Chubu", "country": "JP"},
    "JP-KN": {"name": "Japan - Kansai", "country": "JP"},
    "JP-HR": {"name": "Japan - Hokuriku", "country": "JP"},
    "KR": {"name": "South Korea", "country": "KR"},
    "TW": {"name": "Taiwan", "country": "TW"},
    "IN-DL": {"name": "India - Delhi", "country": "IN"},
    "IN-MH": {"name": "India - Maharashtra", "country": "IN"},
    "IN-KA": {"name": "India - Karnataka", "country": "IN"},
    "IN-TN": {"name": "India - Tamil Nadu", "country": "IN"},
    "SG": {"name": "Singapore", "country": "SG"},
    
    # South America
    "BR-CS": {"name": "Brazil - Central-South", "country": "BR"},
    "BR-N": {"name": "Brazil - North", "country": "BR"},
    "BR-NE": {"name": "Brazil - Northeast", "country": "BR"},
    "BR-S": {"name": "Brazil - South", "country": "BR"},
    "CL-SEN": {"name": "Chile - Central", "country": "CL"},
    "AR": {"name": "Argentina", "country": "AR"},
    "UY": {"name": "Uruguay", "country": "UY"},
    
    # Africa & Middle East
    "ZA": {"name": "South Africa", "country": "ZA"},
    "IL": {"name": "Israel", "country": "IL"},
    "AE": {"name": "UAE", "country": "AE"},
    "SA": {"name": "Saudi Arabia", "country": "SA"},
}

# EIA (USA) Regions and Balancing Authorities
EIA_REGIONS = {
    # Major RTOs/ISOs
    "CISO": {"name": "California ISO", "type": "iso"},
    "ERCO": {"name": "ERCOT (Texas)", "type": "iso"},
    "ISNE": {"name": "ISO New England", "type": "iso"},
    "MISO": {"name": "Midcontinent ISO", "type": "iso"},
    "NYIS": {"name": "New York ISO", "type": "iso"},
    "PJM": {"name": "PJM Interconnection", "type": "iso"},
    "SWPP": {"name": "Southwest Power Pool", "type": "iso"},
    
    # Major interconnections
    "US48": {"name": "Lower 48 States", "type": "region"},
    "TEN": {"name": "Eastern Interconnection", "type": "region"},
    "TW": {"name": "Western Interconnection", "type": "region"},
    "TEX": {"name": "Texas Interconnection", "type": "region"},
}

# ENTSO-E Country Codes (EIC codes)
ENTSOE_AREAS = {
    # Major European countries
    "10YAT-APG------L": {"name": "Austria", "country": "AT"},
    "10YBE----------2": {"name": "Belgium", "country": "BE"},
    "10Y1001A1001A82H": {"name": "Germany-Luxembourg", "country": "DE"},
    "10YDK-1--------W": {"name": "Denmark - West", "country": "DK"},
    "10YDK-2--------M": {"name": "Denmark - East", "country": "DK"},
    "10YES-REE------0": {"name": "Spain", "country": "ES"},
    "10YFR-RTE------C": {"name": "France", "country": "FR"},
    "10YGB----------A": {"name": "Great Britain", "country": "GB"},
    "10YGR-HTSO-----Y": {"name": "Greece", "country": "GR"},
    "10YIT-GRTN-----B": {"name": "Italy", "country": "IT"},
    "10YNL----------L": {"name": "Netherlands", "country": "NL"},
    "10YNO-0--------C": {"name": "Norway - All", "country": "NO"},
    "10YNO-1--------2": {"name": "Norway - Southeast", "country": "NO"},
    "10YNO-2--------T": {"name": "Norway - Southwest", "country": "NO"},
    "10YNO-3--------J": {"name": "Norway - Mid", "country": "NO"},
    "10YNO-4--------9": {"name": "Norway - North", "country": "NO"},
    "10YPL-AREA-----S": {"name": "Poland", "country": "PL"},
    "10YPT-REN------W": {"name": "Portugal", "country": "PT"},
    "10YCH-SWISSGRIDZ": {"name": "Switzerland", "country": "CH"},
    "10YSE-1--------K": {"name": "Sweden - All", "country": "SE"},
    "10Y1001A1001A44P": {"name": "Finland", "country": "FI"},
    "10YCZ-CEPS-----N": {"name": "Czech Republic", "country": "CZ"},
    "10YHU-MAVIR----U": {"name": "Hungary", "country": "HU"},
    "10YRO-TEL------P": {"name": "Romania", "country": "RO"},
    "10YBG-ESO------2": {"name": "Bulgaria", "country": "BG"},
    "10YSK-SEPS-----K": {"name": "Slovakia", "country": "SK"},
    "10YSI-ELES-----O": {"name": "Slovenia", "country": "SI"},
    "10YHR-HEP------M": {"name": "Croatia", "country": "HR"},
}

# Australia NEM/WEM Regions (OpenElectricity)
AUSTRALIA_REGIONS = {
    # National Electricity Market (NEM)
    "NSW1": {"name": "New South Wales", "network": "NEM"},
    "VIC1": {"name": "Victoria", "network": "NEM"},
    "QLD1": {"name": "Queensland", "network": "NEM"},
    "SA1": {"name": "South Australia", "network": "NEM"},
    "TAS1": {"name": "Tasmania", "network": "NEM"},
    
    # Wholesale Electricity Market (WEM)
    "WEM": {"name": "Western Australia", "network": "WEM"},
}

# REE Spain Regions (Peninsular + Non-peninsular)
REE_SPAIN_REGIONS = {
    "peninsular": {"name": "Peninsular Spain", "type": "main"},
    "canarias": {"name": "Canary Islands", "type": "nonpeninsular"},
    "baleares": {"name": "Balearic Islands", "type": "nonpeninsular"},
    "ceuta": {"name": "Ceuta", "type": "nonpeninsular"},
    "melilla": {"name": "Melilla", "type": "nonpeninsular"},
}

# RTE France Regions
RTE_FRANCE_REGIONS = {
    "FR": {"name": "France - National"},
    "FR-BRE": {"name": "Bretagne"},
    "FR-COR": {"name": "Corse"},
    "FR-GUY": {"name": "Guyane"},
    "FR-MTQ": {"name": "Martinique"},
    "FR-GUA": {"name": "Guadeloupe"},
    "FR-REU": {"name": "Réunion"},
}

# Infrastructure types
INFRASTRUCTURE_TYPES = {
    "grid_substation": {"icon": "mdi:transmission-tower", "color": "#E74C3C"},
    "primary_substation": {"icon": "mdi:flash", "color": "#F39C12"},
    "secondary_substation": {"icon": "mdi:flash-outline", "color": "#3498DB"},
    "overhead_line_33kv": {"icon": "mdi:transmission-tower", "color": "#9B59B6"},
    "overhead_line_hv": {"icon": "mdi:power-plug", "color": "#1ABC9C"},
    "generation": {"icon": "mdi:wind-turbine", "color": "#27AE60"},
    "storage": {"icon": "mdi:battery-charging", "color": "#8E44AD"},
}
