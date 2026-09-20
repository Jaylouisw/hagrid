"""API clients for HAGrid - Grid data from multiple sources."""
from __future__ import annotations

import asyncio
import base64
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar
from xml.etree import ElementTree as ET

import aiohttp

from .const import (
    AUSTRALIA_REGIONS,
    CARBON_INTENSITY_API,
    EIA_API_BASE,
    EIA_REGIONS,
    # Global API endpoints
    ELECTRICITY_MAPS_API_BASE,
    # Zone/region mappings
    ELECTRICITY_MAPS_ZONES,
    ELEXON_API_BASE,
    ENERGY_DASHBOARD_API_BASE,
    ENTSOE_API_BASE,
    ENTSOE_AREAS,
    NATIONAL_GRID_API_BASE,
    NATIONAL_GRID_DATASETS,
    NESO_API_BASE,
    NESO_DATASETS,
    NGED_DATASETS,
    NGED_GSP_DATASETS,
    NGED_LICENCE_AREAS,
    NGED_REGION_IDS,
    OPENELECTRICITY_API_BASE,
    OVERPASS_API,
    POSTCODES_IO_API,
    REE_ESIOS_API_BASE,
    RTE_API_BASE,
    SSEN_NERDA_API_BASE,
    UK_INTERCONNECTORS,
    UKPN_API_BASE,
    UKPN_DATASETS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CarbonIntensityData:
    """Carbon intensity data."""

    forecast: int
    actual: int | None
    index: str  # very low, low, moderate, high, very high
    from_time: datetime
    to_time: datetime


@dataclass
class GenerationMix:
    """Generation mix data."""

    fuel: str
    percentage: float


@dataclass
class RegionalData:
    """Regional grid data."""

    region_id: int
    dno_region: str
    short_name: str
    intensity: CarbonIntensityData
    generation_mix: list[GenerationMix] = field(default_factory=list)


@dataclass
class Substation:
    """Substation data."""

    id: str
    name: str
    substation_type: str  # grid, primary, secondary
    latitude: float
    longitude: float
    voltage: str | None = None
    capacity_mva: float | None = None
    customer_count: int | None = None
    address: str | None = None
    extra_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PowerLine:
    """Power line data."""

    id: str
    line_type: str  # 33kv, hv, lv
    coordinates: list[tuple[float, float]]  # List of (lat, lon) pairs
    voltage: str | None = None
    circuit_id: str | None = None


@dataclass
class LiveFault:
    """Live fault/power cut data."""

    id: str
    incident_type: str  # planned, unplanned
    status: str
    postcode_area: str
    estimated_customers: int
    # Both times are optional because not every DNO publishes them, and a field with no default may
    # not follow one that has a default: that ordering is what stopped 1.0.0 importing at all.
    start_time: datetime | None = None
    estimated_restore_time: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    description: str | None = None
    # NGED publishes a licence area rather than a postcode area, and states whether the cut is planned.
    area: str | None = None
    planned: bool = False


@dataclass
class EmbeddedGeneration:
    """Embedded generation/storage site."""

    id: str
    name: str
    technology: str  # solar, wind, battery, etc
    capacity_mw: float
    export_capacity_mw: float | None
    latitude: float
    longitude: float
    connection_voltage: str | None = None
    status: str | None = None


@dataclass
class OSMPowerFeature:
    """OpenStreetMap power infrastructure feature."""

    osm_id: int
    osm_type: str  # node, way, relation
    power_type: str  # substation, line, tower, generator, etc
    name: str | None
    latitude: float
    longitude: float
    voltage: str | None = None
    operator: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    geometry: list[tuple[float, float]] | None = None  # For ways


@dataclass
class SystemData:
    """Real-time system data from NESO/Energy Dashboard."""

    timestamp: datetime
    demand_mw: float | None = None
    frequency_hz: float | None = None
    transfers_mw: dict[str, float] = field(default_factory=dict)


@dataclass
class BMUnit:
    """Balancing Mechanism Unit - Individual generation/demand unit."""

    bm_unit_id: str
    name: str | None
    fuel_type: str
    lead_party: str | None
    registered_capacity_mw: float | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass
class GenerationUnit:
    """Real-time generation output for a specific unit."""

    bm_unit_id: str
    fuel_type: str
    output_mw: float
    timestamp: datetime
    settlement_period: int
    name: str | None = None


@dataclass
class FuelTypeGeneration:
    """Generation output aggregated by fuel type."""

    fuel_type: str
    output_mw: float
    timestamp: datetime
    percentage: float | None = None


@dataclass
class InterconnectorFlow:
    """Power flow through an interconnector."""

    interconnector_id: str
    name: str
    country: str
    flow_mw: float  # Positive = import to GB, Negative = export from GB
    capacity_mw: int
    timestamp: datetime
    utilization_pct: float | None = None


@dataclass
class SystemFrequency:
    """Real-time system frequency."""

    frequency_hz: float
    timestamp: datetime


@dataclass
class DemandData:
    """National/transmission demand data."""

    demand_mw: float
    timestamp: datetime
    demand_type: str  # "national", "transmission"
    settlement_period: int | None = None


@dataclass
class CircuitFlow:
    """Power flow in a metered circuit (aggregated view)."""

    circuit_id: str
    circuit_type: str  # "generation", "interconnector", "demand"
    name: str
    flow_mw: float
    capacity_mw: float | None
    direction: str  # "in", "out", "bidirectional"
    timestamp: datetime
    fuel_type: str | None = None


# ========================================
# GLOBAL DATA STRUCTURES
# ========================================

@dataclass
class ZoneCarbonIntensity:
    """Carbon intensity data for any global zone."""

    zone: str
    zone_name: str
    carbon_intensity: float  # gCO2eq/kWh
    carbon_intensity_unit: str
    fossil_free_percentage: float | None
    renewable_percentage: float | None
    timestamp: datetime
    data_source: str


@dataclass
class ZonePowerBreakdown:
    """Power generation breakdown for any global zone."""

    zone: str
    zone_name: str
    power_consumption_mw: float | None
    power_production_mw: float | None
    power_import_mw: float | None
    power_export_mw: float | None
    generation_by_source: dict[str, float]  # fuel_type -> MW
    timestamp: datetime
    data_source: str
    renewable_percentage: float | None = None  # Percentage of generation from renewables


@dataclass
class CrossBorderFlow:
    """Power flow between two zones/countries."""

    from_zone: str
    to_zone: str
    flow_mw: float
    timestamp: datetime
    data_source: str


@dataclass
class PriceData:
    """Electricity price data."""

    zone: str
    price: float
    currency: str
    price_unit: str  # e.g., "EUR/MWh"
    timestamp: datetime
    market_type: str  # "day_ahead", "real_time", "spot"
    data_source: str


class GridAPIClient(ABC):
    """Abstract base class for grid API clients."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self.session = session

    @abstractmethod
    async def get_carbon_intensity(
        self,
        postcode: str | None = None,
        region_id: int | None = None,
    ) -> CarbonIntensityData | None:
        """Get current carbon intensity."""

    @abstractmethod
    async def get_generation_mix(
        self,
        postcode: str | None = None,
        region_id: int | None = None,
    ) -> list[GenerationMix]:
        """Get current generation mix."""


class GeocoderUnavailable(Exception):
    """The reverse geocode lookup could not be completed."""


class RegisteredKeyRequired(Exception):
    """The dataset is restricted to registered users, so the user's own key is needed."""


@dataclass
class ResolvedLocation:
    """A coordinate expressed the way the grid APIs want it."""

    outcode: str
    latitude: float
    longitude: float
    country: str


class PostcodesIoClient:
    """Reverse geocoding for Great Britain, from postcodes.io.

    Home Assistant knows its latitude and longitude. The Carbon Intensity API's regional endpoints
    want a postcode. One lookup bridges the two, and outside Great Britain the service answers with a
    null result rather than an error, which makes it usable as the "is this address in GB" check too.
    Free, keyless and Open Government Licence, like every other source on the GB path.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self.session = session
        self.base_url = POSTCODES_IO_API

    async def reverse_geocode(
        self, latitude: float, longitude: float
    ) -> ResolvedLocation | None:
        """Nearest postcode to a coordinate, or None when the coordinate is not in Great Britain.

        Raises GeocoderUnavailable when the lookup could not be made at all: "this address is not in
        Great Britain" and "I could not reach the lookup service" need different words in front of a
        user, and both measured cases are real (the default Home Assistant location is outside GB,
        and a service can be down).
        """
        params = {"lon": longitude, "lat": latitude, "limit": 1}
        try:
            async with self.session.get(
                f"{self.base_url}/postcodes", params=params
            ) as response:
                if response.status != 200:
                    raise GeocoderUnavailable(
                        f"postcodes.io returned HTTP {response.status}"
                    )
                payload = await response.json()
        except GeocoderUnavailable:
            raise
        except Exception as err:
            raise GeocoderUnavailable(f"postcodes.io request failed: {err}") from err

        results = payload.get("result") or []
        if not results:
            _LOGGER.info(
                "No GB postcode within range of %.4f, %.4f; the grid APIs are GB-only",
                latitude,
                longitude,
            )
            return None

        nearest = results[0]
        outcode = nearest.get("outcode")
        if not outcode:
            return None

        return ResolvedLocation(
            outcode=outcode,
            latitude=nearest.get("latitude", latitude),
            longitude=nearest.get("longitude", longitude),
            country=nearest.get("country", ""),
        )


class CarbonIntensityClient(GridAPIClient):
    """Client for UK Carbon Intensity API (NESO)."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        super().__init__(session)
        self.base_url = CARBON_INTENSITY_API

    async def _request(self, endpoint: str) -> dict | None:
        """Make a request to the API."""
        url = f"{self.base_url}{endpoint}"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                _LOGGER.error("Carbon Intensity API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("Carbon Intensity API request failed: %s", e)
            return None

    async def get_carbon_intensity(
        self,
        postcode: str | None = None,
        region_id: int | None = None,
    ) -> CarbonIntensityData | None:
        """Get current carbon intensity for region or postcode."""
        if postcode:
            endpoint = f"/regional/postcode/{postcode}"
        elif region_id:
            endpoint = f"/regional/regionid/{region_id}"
        else:
            endpoint = "/intensity"

        data = await self._request(endpoint)
        if not data or "data" not in data:
            return None

        try:
            # Handle different response formats
            if "regions" in data["data"][0]:
                # Regional response
                region = data["data"][0]["regions"][0]
                intensity_data = region.get("intensity", {})
            elif "data" in data["data"][0]:
                # Postcode response
                intensity_data = data["data"][0]["data"][0].get("intensity", {})
            else:
                # National response
                intensity_data = data["data"][0].get("intensity", {})

            return CarbonIntensityData(
                forecast=intensity_data.get("forecast", 0),
                actual=intensity_data.get("actual"),
                index=intensity_data.get("index", "moderate"),
                from_time=datetime.fromisoformat(
                    data["data"][0].get("from", "").replace("Z", "+00:00")
                ),
                to_time=datetime.fromisoformat(
                    data["data"][0].get("to", "").replace("Z", "+00:00")
                ),
            )
        except (KeyError, IndexError, ValueError) as e:
            _LOGGER.error("Error parsing carbon intensity data: %s", e)
            return None

    async def get_generation_mix(
        self,
        postcode: str | None = None,
        region_id: int | None = None,
    ) -> list[GenerationMix]:
        """Get current generation mix."""
        if postcode:
            endpoint = f"/regional/postcode/{postcode}"
        elif region_id:
            endpoint = f"/regional/regionid/{region_id}"
        else:
            endpoint = "/generation"

        data = await self._request(endpoint)
        if not data or "data" not in data:
            return []

        try:
            # Extract generation mix from response
            if "regions" in data["data"][0]:
                mix_data = data["data"][0]["regions"][0].get("generationmix", [])
            elif "data" in data["data"][0]:
                mix_data = data["data"][0]["data"][0].get("generationmix", [])
            else:
                mix_data = data["data"][0].get("generationmix", [])

            return [
                GenerationMix(fuel=item["fuel"], percentage=item["perc"])
                for item in mix_data
            ]
        except (KeyError, IndexError) as e:
            _LOGGER.error("Error parsing generation mix: %s", e)
            return []

    async def get_regional_data(
        self,
        postcode: str | None = None,
        region_id: int | None = None,
    ) -> RegionalData | None:
        """Get full regional data including intensity and generation mix."""
        if postcode:
            endpoint = f"/regional/postcode/{postcode}"
        elif region_id:
            endpoint = f"/regional/regionid/{region_id}"
        else:
            return None

        data = await self._request(endpoint)
        if not data or "data" not in data:
            return None

        try:
            if "regions" in data["data"][0]:
                region = data["data"][0]["regions"][0]
                from_time = data["data"][0].get("from", "")
                to_time = data["data"][0].get("to", "")
            else:
                region = data["data"][0]
                from_time = region.get("data", [{}])[0].get("from", "")
                to_time = region.get("data", [{}])[0].get("to", "")
            intensity_data = region.get("intensity", {})
            if region.get("data"):
                intensity_data = region["data"][0].get("intensity", intensity_data)

            generation_mix = []
            mix_data = region.get("generationmix", [])
            if region.get("data"):
                mix_data = region["data"][0].get("generationmix", mix_data)

            for item in mix_data:
                generation_mix.append(
                    GenerationMix(fuel=item["fuel"], percentage=item["perc"])
                )

            return RegionalData(
                region_id=region.get("regionid", 0),
                dno_region=region.get("dnoregion", "Unknown"),
                short_name=region.get("shortname", "Unknown"),
                intensity=CarbonIntensityData(
                    forecast=intensity_data.get("forecast", 0),
                    actual=intensity_data.get("actual"),
                    index=intensity_data.get("index", "moderate"),
                    from_time=datetime.fromisoformat(from_time.replace("Z", "+00:00")) if from_time else datetime.now(),
                    to_time=datetime.fromisoformat(to_time.replace("Z", "+00:00")) if to_time else datetime.now(),
                ),
                generation_mix=generation_mix,
            )
        except Exception as e:
            _LOGGER.error("Error parsing regional data: %s", e)
            return None

    async def get_all_regions(self) -> list[RegionalData]:
        """Get data for all GB regions."""
        data = await self._request("/regional")
        if not data or "data" not in data:
            return []

        regions = []
        try:
            for region_data in data["data"][0].get("regions", []):
                intensity_data = region_data.get("intensity", {})
                generation_mix = [
                    GenerationMix(fuel=item["fuel"], percentage=item["perc"])
                    for item in region_data.get("generationmix", [])
                ]

                regions.append(RegionalData(
                    region_id=region_data.get("regionid", 0),
                    dno_region=region_data.get("dnoregion", "Unknown"),
                    short_name=region_data.get("shortname", "Unknown"),
                    intensity=CarbonIntensityData(
                        forecast=intensity_data.get("forecast", 0),
                        actual=intensity_data.get("actual"),
                        index=intensity_data.get("index", "moderate"),
                        from_time=datetime.fromisoformat(
                            data["data"][0].get("from", "").replace("Z", "+00:00")
                        ),
                        to_time=datetime.fromisoformat(
                            data["data"][0].get("to", "").replace("Z", "+00:00")
                        ),
                    ),
                    generation_mix=generation_mix,
                ))
        except Exception as e:
            _LOGGER.error("Error parsing all regions: %s", e)

        return regions

    async def get_intensity_forecast(
        self,
        hours: int = 24,
        postcode: str | None = None,
        region_id: int | None = None,
    ) -> list[CarbonIntensityData]:
        """Get carbon intensity forecast."""
        if postcode:
            endpoint = f"/regional/intensity/{{now}}/fw{hours}h/postcode/{postcode}"
        elif region_id:
            endpoint = f"/regional/intensity/{{now}}/fw{hours}h/regionid/{region_id}"
        else:
            endpoint = f"/intensity/{{now}}/fw{hours}h"

        # Replace {now} with actual datetime
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")
        endpoint = endpoint.replace("{now}", now)

        data = await self._request(endpoint)
        if not data or "data" not in data:
            return []

        forecasts = []
        try:
            for item in data["data"]:
                if "intensity" in item:
                    intensity = item["intensity"]
                elif "regions" in item:
                    intensity = item["regions"][0].get("intensity", {})
                else:
                    continue

                forecasts.append(CarbonIntensityData(
                    forecast=intensity.get("forecast", 0),
                    actual=intensity.get("actual"),
                    index=intensity.get("index", "moderate"),
                    from_time=datetime.fromisoformat(item.get("from", "").replace("Z", "+00:00")),
                    to_time=datetime.fromisoformat(item.get("to", "").replace("Z", "+00:00")),
                ))
        except Exception as e:
            _LOGGER.error("Error parsing intensity forecast: %s", e)

        return forecasts


def _parse_datetime(value: str | None) -> datetime | None:
    """A timestamp from one of the portals, or None when it is absent or unparseable.

    None rather than a substitute: a fabricated start time is worse than a missing one, and the
    LiveFault fields are optional precisely so this can say "not published".
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        _LOGGER.debug("Unparseable timestamp from a grid API: %r", value)
        return None


def nged_licence_area(dno: str | None, region_id: int | None) -> str | None:
    """Which NGED licence area an entry falls in, or None when NGED does not cover it.

    The DNO string is what the Carbon Intensity API called it, and the region id is the fallback for
    an entry whose DNO was never resolved. Asking the wrong operator for power cuts is worse than
    asking nobody, so anything unrecognised returns None and the caller stays with UKPN.
    """
    return NGED_LICENCE_AREAS.get(dno or "") or NGED_REGION_IDS.get(region_id or -1)


class UKPNClient(GridAPIClient):
    """Client for UK Power Networks Open Data API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        super().__init__(session)
        self.base_url = UKPN_API_BASE

    async def _request(
        self,
        dataset: str,
        limit: int = 100,
        offset: int = 0,
        where: str | None = None,
        select: str | None = None,
    ) -> dict | None:
        """Make a request to the UKPN API."""
        url = f"{self.base_url}/catalog/datasets/{dataset}/records"
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }
        if where:
            params["where"] = where
        if select:
            params["select"] = select

        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                _LOGGER.error("UKPN API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("UKPN API request failed: %s", e)
            return None

    async def get_carbon_intensity(
        self,
        postcode: str | None = None,
        region_id: int | None = None,
    ) -> CarbonIntensityData | None:
        """Not implemented for UKPN - use CarbonIntensityClient."""
        return None

    async def get_generation_mix(
        self,
        postcode: str | None = None,
        region_id: int | None = None,
    ) -> list[GenerationMix]:
        """Not implemented for UKPN - use CarbonIntensityClient."""
        return []

    async def get_live_faults(self, limit: int = 100) -> list[LiveFault]:
        """Get live power cut/fault data."""
        data = await self._request(UKPN_DATASETS["live_faults"], limit=limit)
        if not data or "results" not in data:
            return []

        faults: list[LiveFault] = []
        for record in data["results"]:
            fields = record.get("record", {}).get("fields", record)
            fault = self._parse_ukpn_fault(fields)
            if fault is not None:
                faults.append(fault)

        return faults

    @staticmethod
    def _parse_ukpn_fault(fields: dict) -> LiveFault | None:
        """One UKPN incident, read under the field names this dataset actually publishes.

        Four of them used to be read under names that do not exist here - geo_point_2d (it is
        geopoint), status, postcodearea and estimatedrestoredcustomers - so every UKPN fault arrived
        with no coordinates, no postcode area, no affected customers and the status "unknown", while
        the numeric incidenttype stood in for the type text. Verified against the live dataset
        2026-09-19.
        """
        reference = fields.get("incidentreference")
        if not reference:
            return None

        geo = fields.get("geopoint") or {}
        incident = str(fields.get("incidenttypename") or fields.get("powercuttype") or "unknown")
        try:
            customers = int(fields.get("nocustomeraffected") or 0)
        except (TypeError, ValueError):
            customers = 0

        return LiveFault(
            id=str(reference),
            incident_type=incident,
            status=incident,
            postcode_area=str(fields.get("postcodesaffected") or "").split(";")[0],
            estimated_customers=customers,
            start_time=_parse_datetime(fields.get("creationdatetime")),
            estimated_restore_time=_parse_datetime(fields.get("estimatedrestorationdate")),
            latitude=geo.get("lat"),
            longitude=geo.get("lon"),
            description=fields.get("incidentcategorycustomerfriendlydescription"),
            planned="planned" in incident.lower() or bool(fields.get("planneddate")),
        )

    async def get_grid_primary_substations(
        self,
        limit: int = 100,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[Substation]:
        """Get grid and primary substation data."""
        where = None
        if bbox:
            # bbox = (min_lat, min_lon, max_lat, max_lon)
            where = f"within_distance(geo_point_2d, geom'POINT({bbox[1]} {bbox[0]})', {bbox[3]-bbox[1]}km)"

        data = await self._request(
            UKPN_DATASETS["grid_primary_sites"],
            limit=limit,
            where=where,
        )
        if not data or "results" not in data:
            return []

        substations = []
        for record in data["results"]:
            fields = record.get("record", {}).get("fields", record)
            try:
                geo = fields.get("geo_point_2d", {})
                if not geo:
                    continue

                substations.append(Substation(
                    id=str(fields.get("gsp_gis_id", record.get("record", {}).get("id", ""))),
                    name=fields.get("substation_name", "Unknown"),
                    substation_type="grid" if fields.get("substation_type", "").lower() == "grid" else "primary",
                    latitude=geo.get("lat", 0),
                    longitude=geo.get("lon", 0),
                    voltage=fields.get("voltage"),
                    capacity_mva=fields.get("installed_capacity_mva"),
                    extra_data={
                        "licence_area": fields.get("licence_area"),
                        "dno_area": fields.get("dno_area"),
                    },
                ))
            except Exception as e:
                _LOGGER.debug("Error parsing substation record: %s", e)
                continue

        return substations

    async def get_secondary_substations(
        self,
        limit: int = 100,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[Substation]:
        """Get secondary substation data."""
        where = None
        if bbox:
            where = f"within_distance(geo_point_2d, geom'POINT({bbox[1]} {bbox[0]})', {bbox[3]-bbox[1]}km)"

        data = await self._request(
            UKPN_DATASETS["secondary_sites"],
            limit=limit,
            where=where,
        )
        if not data or "results" not in data:
            return []

        substations = []
        for record in data["results"]:
            fields = record.get("record", {}).get("fields", record)
            try:
                geo = fields.get("geo_point_2d", {})
                if not geo:
                    continue

                substations.append(Substation(
                    id=str(fields.get("asset_id", record.get("record", {}).get("id", ""))),
                    name=fields.get("substation_name", "Unknown"),
                    substation_type="secondary",
                    latitude=geo.get("lat", 0),
                    longitude=geo.get("lon", 0),
                    capacity_mva=fields.get("onan_rating_kva", 0) / 1000 if fields.get("onan_rating_kva") else None,
                    customer_count=fields.get("customer_count"),
                    address=fields.get("address"),
                    extra_data={
                        "indoor_outdoor": fields.get("indoor_outdoor"),
                        "primary_feeder": fields.get("primary_feeder"),
                    },
                ))
            except Exception as e:
                _LOGGER.debug("Error parsing secondary substation: %s", e)
                continue

        return substations

    async def get_overhead_lines_33kv(
        self,
        limit: int = 100,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[PowerLine]:
        """Get 33kV overhead line data."""
        data = await self._request(
            UKPN_DATASETS["33kv_overhead_lines"],
            limit=limit,
        )
        if not data or "results" not in data:
            return []

        lines = []
        for record in data["results"]:
            fields = record.get("record", {}).get("fields", record)
            try:
                geo_shape = fields.get("geo_shape", {})
                if not geo_shape or "coordinates" not in geo_shape:
                    continue

                # Convert coordinates from [lon, lat] to (lat, lon)
                coords = geo_shape.get("coordinates", [])
                if geo_shape.get("type") == "LineString":
                    coordinates = [(c[1], c[0]) for c in coords]
                elif geo_shape.get("type") == "MultiLineString":
                    coordinates = [(c[1], c[0]) for segment in coords for c in segment]
                else:
                    continue

                lines.append(PowerLine(
                    id=str(record.get("record", {}).get("id", "")),
                    line_type="33kv",
                    coordinates=coordinates,
                    voltage="33kV",
                    circuit_id=fields.get("circuit_id"),
                ))
            except Exception as e:
                _LOGGER.debug("Error parsing 33kV line: %s", e)
                continue

        return lines

    async def get_overhead_lines_hv(
        self,
        limit: int = 100,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[PowerLine]:
        """Get HV overhead line data."""
        data = await self._request(
            UKPN_DATASETS["hv_overhead_lines"],
            limit=limit,
        )
        if not data or "results" not in data:
            return []

        lines = []
        for record in data["results"]:
            fields = record.get("record", {}).get("fields", record)
            try:
                geo_shape = fields.get("geo_shape", {})
                if not geo_shape or "coordinates" not in geo_shape:
                    continue

                coords = geo_shape.get("coordinates", [])
                if geo_shape.get("type") == "LineString":
                    coordinates = [(c[1], c[0]) for c in coords]
                elif geo_shape.get("type") == "MultiLineString":
                    coordinates = [(c[1], c[0]) for segment in coords for c in segment]
                else:
                    continue

                lines.append(PowerLine(
                    id=str(record.get("record", {}).get("id", "")),
                    line_type="hv",
                    coordinates=coordinates,
                    voltage=fields.get("voltage", "HV"),
                    circuit_id=fields.get("circuit_id"),
                ))
            except Exception as e:
                _LOGGER.debug("Error parsing HV line: %s", e)
                continue

        return lines

    async def get_embedded_generation(
        self,
        limit: int = 100,
        technology: str | None = None,
    ) -> list[EmbeddedGeneration]:
        """Get embedded generation/storage sites."""
        where = None
        if technology:
            where = f"technology_type='{technology}'"

        data = await self._request(
            UKPN_DATASETS["embedded_capacity"],
            limit=limit,
            where=where,
        )
        if not data or "results" not in data:
            return []

        sites = []
        for record in data["results"]:
            fields = record.get("record", {}).get("fields", record)
            try:
                geo = fields.get("geo_point_2d", {})
                if not geo:
                    continue

                sites.append(EmbeddedGeneration(
                    id=str(fields.get("ecr_ref", record.get("record", {}).get("id", ""))),
                    name=fields.get("site_name", "Unknown"),
                    technology=fields.get("technology_type", "unknown"),
                    capacity_mw=float(fields.get("installed_capacity_mw", 0)),
                    export_capacity_mw=float(fields.get("export_capacity_mw", 0)) if fields.get("export_capacity_mw") else None,
                    latitude=geo.get("lat", 0),
                    longitude=geo.get("lon", 0),
                    connection_voltage=fields.get("connection_voltage"),
                    status=fields.get("status"),
                ))
            except Exception as e:
                _LOGGER.debug("Error parsing embedded generation: %s", e)
                continue

        return sites


class OverpassClient:
    """Client for OpenStreetMap Overpass API - power infrastructure."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self.session = session
        self.base_url = OVERPASS_API

    async def _query(self, query: str) -> dict | None:
        """Execute an Overpass query."""
        try:
            async with self.session.post(
                self.base_url,
                data={"data": query},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status == 200:
                    return await response.json()
                _LOGGER.error("Overpass API error: %s", response.status)
                return None
        except TimeoutError:
            _LOGGER.error("Overpass API timeout")
            return None
        except Exception as e:
            _LOGGER.error("Overpass API request failed: %s", e)
            return None

    def _build_bbox(
        self,
        lat: float,
        lon: float,
        radius_km: float,
    ) -> tuple[float, float, float, float]:
        """Build bounding box from center point and radius."""
        # Approximate degrees per km
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * math.cos(math.radians(lat)))

        return (
            lat - lat_delta,  # south
            lon - lon_delta,  # west
            lat + lat_delta,  # north
            lon + lon_delta,  # east
        )

    async def get_power_infrastructure(
        self,
        lat: float,
        lon: float,
        radius_km: float = 10,
        include_lines: bool = True,
    ) -> list[OSMPowerFeature]:
        """Get power infrastructure within radius of a point."""
        bbox = self._build_bbox(lat, lon, radius_km)

        # Build Overpass QL query for power infrastructure
        query = f"""
        [out:json][timeout:30];
        (
          node["power"="substation"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
          way["power"="substation"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
          node["power"="plant"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
          way["power"="plant"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
          node["power"="generator"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
          node["power"="tower"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
        """

        if include_lines:
            query += f"""
          way["power"="line"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
          way["power"="minor_line"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
            """

        query += """
        );
        out center;
        """

        data = await self._query(query)
        if not data or "elements" not in data:
            return []

        features: list[OSMPowerFeature] = []
        for element in data["elements"]:
            try:
                osm_type = element.get("type", "node")
                tags = element.get("tags", {})

                # Get coordinates (center for ways)
                if osm_type == "node":
                    lat_val = element.get("lat", 0)
                    lon_val = element.get("lon", 0)
                elif osm_type == "way":
                    center = element.get("center", {})
                    lat_val = center.get("lat", 0)
                    lon_val = center.get("lon", 0)
                else:
                    continue

                features.append(OSMPowerFeature(
                    osm_id=element.get("id", 0),
                    osm_type=osm_type,
                    power_type=tags.get("power", "unknown"),
                    name=tags.get("name"),
                    latitude=lat_val,
                    longitude=lon_val,
                    voltage=tags.get("voltage"),
                    operator=tags.get("operator"),
                    tags=tags,
                ))
            except Exception as e:
                _LOGGER.debug("Error parsing OSM element: %s", e)
                continue

        return features

    async def get_substations(
        self,
        lat: float,
        lon: float,
        radius_km: float = 20,
    ) -> list[OSMPowerFeature]:
        """Get substations within radius."""
        bbox = self._build_bbox(lat, lon, radius_km)

        query = f"""
        [out:json][timeout:30];
        (
          node["power"="substation"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
          way["power"="substation"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
          relation["power"="substation"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
        );
        out center tags;
        """

        data = await self._query(query)
        if not data or "elements" not in data:
            return []

        substations: list[OSMPowerFeature] = []
        for element in data["elements"]:
            try:
                tags = element.get("tags", {})
                osm_type = element.get("type", "node")

                if osm_type == "node":
                    lat_val = element.get("lat", 0)
                    lon_val = element.get("lon", 0)
                else:
                    center = element.get("center", {})
                    lat_val = center.get("lat", 0)
                    lon_val = center.get("lon", 0)

                substations.append(OSMPowerFeature(
                    osm_id=element.get("id", 0),
                    osm_type=osm_type,
                    power_type="substation",
                    name=tags.get("name"),
                    latitude=lat_val,
                    longitude=lon_val,
                    voltage=tags.get("voltage"),
                    operator=tags.get("operator"),
                    tags=tags,
                ))
            except Exception as e:
                _LOGGER.debug("Error parsing OSM substation: %s", e)
                continue

        return substations


class NESOClient:
    """Client for NESO (National Energy System Operator) API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self.session = session
        self.base_url = NESO_API_BASE

    async def _request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make a request to the NESO API."""
        url = f"{self.base_url}/{endpoint}"
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                _LOGGER.error("NESO API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("NESO API request failed: %s", e)
            return None

    async def get_embedded_forecasts(self, limit: int = 48) -> list[dict]:
        """Get embedded wind and solar forecasts."""
        params = {
            "resource_id": NESO_DATASETS["embedded_wind_solar"],
            "limit": limit,
        }
        data = await self._request("datastore_search", params)
        if not data or not data.get("success"):
            return []
        return data.get("result", {}).get("records", [])

    async def get_demand_forecast(self, limit: int = 48) -> list[dict]:
        """Get demand forecast data."""
        params = {
            "resource_id": NESO_DATASETS["demand_forecast"],
            "limit": limit,
        }
        data = await self._request("datastore_search", params)
        if not data or not data.get("success"):
            return []
        return data.get("result", {}).get("records", [])

    async def get_package_list(self) -> list[str]:
        """Get list of available datasets."""
        data = await self._request("package_list")
        if not data or not data.get("success"):
            return []
        return data.get("result", [])


class NGEDLiveDataMixin:
    """The parts of the NGED portal that are open data.

    Icebreaker One sensitivity class IB1-O: full open access, under an open data license, free to use,
    by anyone, for any purpose. Measured 2026-09-19 answering with no credential of any kind. The
    static network layers on the same portal are a different matter: they answer 403 "Resource access
    restricted to registered users", which is the mitigation their Data Sharing Assessment relies on,
    so they stay behind the user's own key.
    """

    async def get_nged_live_faults(self, licence_area: str | None = None) -> list[LiveFault]:
        """Live and planned power cuts across NGED's four licence areas.

        The package carries two resources in different shapes: the detailed one names the licence area
        per record, the summary one calls the same thing Region. Both are normalised here so that
        whichever the portal has populated, the caller sees the same fields. Neither publishes
        coordinates, so these cannot be placed on the map individually.
        """
        records: list[dict] = []
        for wanted in ("detailed", "cuts"):
            try:
                records = await self._datastore_search(
                    NGED_DATASETS["live_power_cuts"], name=wanted, limit=200
                )
            except RegisteredKeyRequired:
                raise
            if records:
                break

        faults = [fault for fault in (self._parse_nged_fault(r) for r in records) if fault]
        if licence_area:
            faults = [f for f in faults if (f.area or "").lower() == licence_area.lower()]
        return faults

    async def get_nged_live_data(self, licence_area: str) -> list[dict]:
        """Aggregate demand and generation for one licence area. Open data, no key."""
        return await self._datastore_search(
            NGED_DATASETS["live_data"], name=licence_area, limit=200
        )

    async def get_nged_gsp_data(self, licence_area: str, limit: int = 200) -> list[dict]:
        """Live per-Grid-Supply-Point flows for one licence area. Open data, no key."""
        package_id = NGED_GSP_DATASETS.get(licence_area)
        if not package_id:
            return []
        return await self._datastore_search(package_id, limit=limit)

    @staticmethod
    def _parse_nged_fault(record: dict) -> LiveFault | None:
        """One NGED power-cut record, in either of the two shapes the portal publishes."""
        # The two resources differ only in case and spacing: fault_id against "Incident ID",
        # licence_area against "Region", confirmed_off against "Confirmed Off". Normalising the keys
        # is what lets one parser read both, and the customers field is the one that gets missed.
        lowered = {
            str(key).strip().lower().replace(" ", "_"): value for key, value in record.items()
        }
        fault_id = lowered.get("fault_id") or lowered.get("incident_id")
        if fault_id is None:
            return None
        try:
            customers = int(float(lowered.get("confirmed_off") or 0))
        except (TypeError, ValueError):
            customers = 0
        planned = str(lowered.get("planned")).strip().lower() == "true"
        return LiveFault(
            id=str(fault_id),
            incident_type=str(lowered.get("category") or "unknown"),
            status=str(lowered.get("status") or "unknown"),
            postcode_area="",  # not published per incident
            estimated_customers=customers,
            description=str(lowered.get("category") or "") or None,
            area=str(lowered.get("licence_area") or lowered.get("region") or "") or None,
            planned=planned,
        )


class NationalGridClient(NGEDLiveDataMixin):
    """Client for the National Grid Electricity Distribution portal (CKAN)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str | None = None,
    ) -> None:
        """Initialize the client."""
        self.session = session
        self.base_url = NATIONAL_GRID_API_BASE
        self.api_key = api_key

    async def _request_raw(
        self, endpoint: str, params: dict | None = None
    ) -> tuple[int | None, dict | None]:
        """Make a request and keep the status code alongside the body.

        The status is the only thing that separates the three outcomes on this portal: 403 means the
        dataset is restricted to registered users, 404 means the resource is not a queryable table,
        and None means the request never completed. Collapsing them into one None is what made the
        old code silently return nothing for all three.
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {}
        if self.api_key:
            headers["Authorization"] = self.api_key

        try:
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    return response.status, await response.json()
                _LOGGER.error("National Grid API error: %s for %s", response.status, endpoint)
                return response.status, None
        except Exception as e:
            _LOGGER.error("National Grid API request failed: %s", e)
            return None, None

    async def _request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make a request to the National Grid API, discarding the status."""
        _, data = await self._request_raw(endpoint, params)
        return data

    async def _datastore_search(
        self,
        package_id: str,
        *,
        name: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query a package's datastore, choosing which resource to ask.

        Selection cannot use the datastore_active flag. Measured 2026-09-19: thirteen of the fourteen
        East Midlands GSP resources are flagged false and answer queries anyway, while the genuinely
        non-tabular entries answer 404. So candidates come from the format, are ordered by how well
        their name matches, and a 404 moves on to the next one rather than failing the whole call.
        """
        pkg = await self.get_package_info(package_id)
        if not pkg:
            return []

        candidates = [
            resource
            for resource in pkg.get("resources", [])
            if (resource.get("format") or "").upper() == "CSV"
        ]
        if name:
            wanted = name.lower()
            candidates.sort(key=lambda r: wanted not in (r.get("name") or "").lower())
        if not candidates:
            _LOGGER.debug("No CSV resources in %s", package_id)
            return []

        for resource in candidates:
            status, data = await self._request_raw(
                "datastore_search", {"resource_id": resource["id"], "limit": limit}
            )
            if status == 403:
                raise RegisteredKeyRequired(f"{package_id} is restricted to registered users")
            if status == 200 and data and data.get("success"):
                return data.get("result", {}).get("records", [])

        _LOGGER.debug("No datastore resource answered for %s", package_id)
        return []

    async def get_package_info(self, package_id: str) -> dict | None:
        """Get information about a dataset package."""
        data = await self._request("package_show", {"id": package_id})
        if not data or not data.get("success"):
            return None
        return data.get("result")

    async def get_embedded_capacity_register(self, limit: int = 100) -> list[dict]:
        """Get embedded capacity register data. Open data, no key needed."""
        return await self._datastore_search(
            NATIONAL_GRID_DATASETS["embedded_capacity_register"], name="ECR", limit=limit
        )

    async def get_primary_substations(self, limit: int = 100) -> list[Substation]:
        """Get primary substation locations.

        Restricted to registered users, so this raises RegisteredKeyRequired rather than returning an
        empty list and leaving the caller to guess why there are no substations.
        """
        records = await self._datastore_search(
            NATIONAL_GRID_DATASETS["primary_substations"], limit=limit
        )

        substations: list[Substation] = []
        for record in records:
            try:
                easting = float(record.get("Easting", 0))
                northing = float(record.get("Northing", 0))

                # Not the OSGB36 to WGS84 conversion the comment here used to claim. Scaling eastings
                # and northings linearly puts these on the map kilometres out, which is worse than no
                # marker at all. Tracked separately; do not build on it.
                lat = 49.0 + (northing / 111000)
                lon = -8.0 + (easting / 80000)

                substations.append(Substation(
                    id=str(record.get("_id", "")),
                    name=record.get("Name", "Unknown"),
                    substation_type="primary",
                    latitude=lat,
                    longitude=lon,
                ))
            except Exception as e:
                _LOGGER.debug("Error parsing NG substation: %s", e)
                continue

        return substations


class SSENNerdaClient:
    """Client for SSEN NERDA API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str | None = None,
    ) -> None:
        """Initialize the client."""
        self.session = session
        self.base_url = SSEN_NERDA_API_BASE
        self.api_key = api_key

    async def _request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make a request to the SSEN NERDA API."""
        url = f"{self.base_url}/{endpoint}"
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                _LOGGER.error("SSEN NERDA API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("SSEN NERDA API request failed: %s", e)
            return None

    async def get_network_data(self) -> dict | None:
        """Get network data from NERDA."""
        return await self._request("network")

    async def get_assets(self, asset_type: str | None = None) -> list[dict]:
        """Get asset data."""
        params = {}
        if asset_type:
            params["type"] = asset_type
        data = await self._request("assets", params)
        return data if isinstance(data, list) else []


class EnergyDashboardClient:
    """Client for energydashboard.co.uk API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str | None = None,
    ) -> None:
        """Initialize the client."""
        self.session = session
        self.base_url = ENERGY_DASHBOARD_API_BASE
        self.api_key = api_key

    async def _request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make a request to the Energy Dashboard API."""
        url = f"{self.base_url}/{endpoint}"
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                _LOGGER.error("Energy Dashboard API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("Energy Dashboard API request failed: %s", e)
            return None

    async def get_generation_latest(self) -> dict | None:
        """Get latest generation data."""
        return await self._request("generation/latest")

    async def get_carbon_intensity_latest(self) -> dict | None:
        """Get latest carbon intensity."""
        return await self._request("carbon-intensity/latest")

    async def get_demand_latest(self) -> dict | None:
        """Get latest demand data."""
        return await self._request("demand/latest")


class ElexonBMRSClient:
    """Client for Elexon BMRS API - Granular metered circuit data.
    
    Free public API, no authentication required.
    Provides real-time metered data for:
    - Individual generation units (power stations)
    - Interconnector flows (France, Belgium, etc.)
    - System frequency
    - National demand
    - Balancing mechanism data
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self.session = session
        self.base_url = ELEXON_API_BASE

    async def _request(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> dict | list | None:
        """Make a request to the Elexon BMRS API."""
        url = f"{self.base_url}{endpoint}"

        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                _LOGGER.warning("Elexon API error %s: %s", response.status, url)
                return None
        except Exception as e:
            _LOGGER.error("Elexon API request failed: %s", e)
            return None

    async def get_all_bm_units(self) -> list[BMUnit]:
        """Get all Balancing Mechanism Units (power stations, interconnectors, etc.)."""
        data = await self._request("/reference/bmunits/all")
        if not data or not isinstance(data, list):
            return []

        units = []
        for item in data:
            units.append(BMUnit(
                bm_unit_id=item.get("bmUnitId", ""),
                name=item.get("bmUnitName"),
                fuel_type=item.get("fuelType", "UNKNOWN"),
                lead_party=item.get("leadPartyName"),
                registered_capacity_mw=item.get("registeredCapacity"),
            ))
        return units

    async def get_generation_by_unit(
        self,
        settlement_date: str | None = None,
        settlement_period: int | None = None,
    ) -> list[GenerationUnit]:
        """Get actual generation output per generation unit (B1610).
        
        This is THE most granular data - individual power station output!
        """
        params = {}
        if settlement_date:
            params["settlementDate"] = settlement_date
        if settlement_period:
            params["settlementPeriod"] = settlement_period

        # Use the streaming endpoint for latest data
        data = await self._request("/datasets/B1610", params)
        if not data or "data" not in data:
            return []

        units = []
        for item in data.get("data", []):
            try:
                units.append(GenerationUnit(
                    bm_unit_id=item.get("ngcBmUnitId", item.get("bmUnitId", "")),
                    fuel_type=item.get("fuelType", "UNKNOWN"),
                    output_mw=float(item.get("quantity", 0)),
                    timestamp=datetime.fromisoformat(
                        item.get("settlementDate", datetime.now().isoformat())
                    ),
                    settlement_period=item.get("settlementPeriod", 0),
                    name=item.get("registeredResourceName"),
                ))
            except (ValueError, TypeError) as e:
                _LOGGER.debug("Error parsing generation unit: %s", e)

        return units

    async def get_generation_by_fuel_type(self) -> list[FuelTypeGeneration]:
        """Get instantaneous generation outturn by fuel type (FUELINST).
        
        Real-time generation breakdown: gas, coal, nuclear, wind, solar, etc.
        """
        data = await self._request("/generation/outturn/current")
        if not data:
            return []

        generation = []
        now = datetime.now()

        # Handle the response structure
        gen_data = data if isinstance(data, list) else data.get("data", [])

        for item in gen_data:
            try:
                fuel = item.get("fuelType", item.get("fuel", "UNKNOWN"))
                output = float(item.get("currentMW", item.get("generation", 0)))
                pct = item.get("currentPercentage", item.get("percentage"))

                generation.append(FuelTypeGeneration(
                    fuel_type=fuel,
                    output_mw=output,
                    timestamp=now,
                    percentage=float(pct) if pct else None,
                ))
            except (ValueError, TypeError) as e:
                _LOGGER.debug("Error parsing fuel generation: %s", e)

        return generation

    async def get_interconnector_flows(self) -> list[InterconnectorFlow]:
        """Get real-time interconnector power flows.
        
        Shows import/export with France, Belgium, Netherlands, Norway, etc.
        Positive = importing to GB, Negative = exporting from GB
        """
        data = await self._request("/generation/outturn/interconnectors")
        if not data or "data" not in data:
            return []

        flows = []
        now = datetime.now()

        for item in data.get("data", []):
            try:
                ic_id = item.get("interconnectorId", item.get("fuelType", ""))
                ic_info = UK_INTERCONNECTORS.get(ic_id, {})

                flow_mw = float(item.get("generation", item.get("flow", 0)))
                capacity = ic_info.get("capacity_mw", 1000)

                flows.append(InterconnectorFlow(
                    interconnector_id=ic_id,
                    name=ic_info.get("name", ic_id),
                    country=ic_info.get("country", ""),
                    flow_mw=flow_mw,
                    capacity_mw=capacity,
                    timestamp=now,
                    utilization_pct=abs(flow_mw) / capacity * 100 if capacity else None,
                ))
            except (ValueError, TypeError) as e:
                _LOGGER.debug("Error parsing interconnector flow: %s", e)

        return flows

    async def get_system_frequency(self) -> SystemFrequency | None:
        """Get real-time system frequency (target 50Hz)."""
        data = await self._request("/system/frequency")
        if not data or "data" not in data:
            return None

        items = data.get("data", [])
        if not items:
            return None

        latest = items[0]  # Most recent
        try:
            return SystemFrequency(
                frequency_hz=float(latest.get("frequency", 50.0)),
                timestamp=datetime.fromisoformat(
                    latest.get("measurementTime", datetime.now().isoformat())
                ),
            )
        except (ValueError, TypeError):
            return None

    async def get_demand_outturn(self) -> DemandData | None:
        """Get Initial National Demand Outturn (INDO)."""
        data = await self._request("/demand/outturn")
        if not data or "data" not in data:
            return None

        items = data.get("data", [])
        if not items:
            return None

        latest = items[0]
        try:
            return DemandData(
                demand_mw=float(latest.get("initialDemandOutturn", 0)),
                timestamp=datetime.fromisoformat(
                    latest.get("startTime", datetime.now().isoformat())
                ),
                demand_type="national",
                settlement_period=latest.get("settlementPeriod"),
            )
        except (ValueError, TypeError):
            return None

    async def get_demand_summary(self) -> dict:
        """Get demand summary including current demand and peak."""
        data = await self._request("/demand/outturn/summary")
        if not data:
            return {}
        return data

    async def get_all_fuel_types(self) -> list[dict]:
        """Get reference data for all fuel types."""
        data = await self._request("/reference/fueltypes/all")
        return data if isinstance(data, list) else []

    async def get_all_interconnectors(self) -> list[dict]:
        """Get reference data for all interconnectors."""
        data = await self._request("/reference/interconnectors/all")
        return data if isinstance(data, list) else []

    async def get_physical_notifications(
        self,
        bm_unit_id: str | None = None,
    ) -> list[dict]:
        """Get Physical Notifications - planned output per BMU.
        
        Shows what each power station plans to generate.
        """
        params = {}
        if bm_unit_id:
            params["bmUnit"] = bm_unit_id

        data = await self._request("/balancing/physical/all", params)
        if not data or "data" not in data:
            return []
        return data.get("data", [])

    async def get_circuit_flows(self) -> list[CircuitFlow]:
        """Get aggregated view of all metered circuits.
        
        Combines generation units, interconnectors, and demand into
        a unified view of power flows across the grid.
        """
        # Fetch all data in parallel
        results = await asyncio.gather(
            self.get_generation_by_fuel_type(),
            self.get_interconnector_flows(),
            self.get_demand_outturn(),
            return_exceptions=True,
        )

        flows = []
        now = datetime.now()

        # Add generation by fuel type
        if isinstance(results[0], list):
            for gen in results[0]:
                flows.append(CircuitFlow(
                    circuit_id=f"gen_{gen.fuel_type.lower()}",
                    circuit_type="generation",
                    name=f"{gen.fuel_type} Generation",
                    flow_mw=gen.output_mw,
                    capacity_mw=None,  # Could be calculated from reference data
                    direction="in",
                    fuel_type=gen.fuel_type,
                    timestamp=now,
                ))

        # Add interconnector flows
        if isinstance(results[1], list):
            for ic in results[1]:
                direction = "in" if ic.flow_mw >= 0 else "out"
                flows.append(CircuitFlow(
                    circuit_id=f"ic_{ic.interconnector_id.lower()}",
                    circuit_type="interconnector",
                    name=ic.name,
                    flow_mw=abs(ic.flow_mw),
                    capacity_mw=float(ic.capacity_mw),
                    direction=direction,
                    fuel_type="interconnector",
                    timestamp=now,
                ))

        # Add demand
        if isinstance(results[2], DemandData):
            flows.append(CircuitFlow(
                circuit_id="demand_national",
                circuit_type="demand",
                name="National Demand",
                flow_mw=results[2].demand_mw,
                capacity_mw=None,
                direction="out",
                fuel_type=None,
                timestamp=now,
            ))

        return flows

    async def get_grid_summary(self) -> dict[str, Any]:
        """Get comprehensive grid summary with all metered data.
        
        Returns a complete picture of the grid including:
        - Total generation by fuel type
        - All interconnector flows
        - Current demand
        - System frequency
        - Net import/export position
        """
        results = await asyncio.gather(
            self.get_generation_by_fuel_type(),
            self.get_interconnector_flows(),
            self.get_demand_outturn(),
            self.get_system_frequency(),
            return_exceptions=True,
        )

        summary = {
            "timestamp": datetime.now().isoformat(),
            "generation": {},
            "interconnectors": {},
            "demand_mw": None,
            "frequency_hz": None,
            "total_generation_mw": 0,
            "total_import_mw": 0,
            "total_export_mw": 0,
            "net_import_mw": 0,
        }

        # Process generation
        if isinstance(results[0], list):
            for gen in results[0]:
                summary["generation"][gen.fuel_type] = {
                    "output_mw": gen.output_mw,
                    "percentage": gen.percentage,
                }
                summary["total_generation_mw"] += gen.output_mw

        # Process interconnectors
        if isinstance(results[1], list):
            for ic in results[1]:
                summary["interconnectors"][ic.interconnector_id] = {
                    "name": ic.name,
                    "country": ic.country,
                    "flow_mw": ic.flow_mw,
                    "capacity_mw": ic.capacity_mw,
                    "utilization_pct": ic.utilization_pct,
                    "direction": "import" if ic.flow_mw >= 0 else "export",
                }
                if ic.flow_mw >= 0:
                    summary["total_import_mw"] += ic.flow_mw
                else:
                    summary["total_export_mw"] += abs(ic.flow_mw)

        summary["net_import_mw"] = summary["total_import_mw"] - summary["total_export_mw"]

        # Process demand
        if isinstance(results[2], DemandData):
            summary["demand_mw"] = results[2].demand_mw

        # Process frequency
        if isinstance(results[3], SystemFrequency):
            summary["frequency_hz"] = results[3].frequency_hz

        return summary


# ========================================
# GLOBAL ENERGY API CLIENTS
# ========================================

class ElectricityMapsClient:
    """Client for Electricity Maps API - Global carbon intensity and power data.
    
    API Documentation: https://portal.electricitymaps.com/docs/
    Free tier: 30 requests/hour
    Provides: Carbon intensity, power breakdown, zone data for 200+ zones
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
    ) -> None:
        """Initialize the Electricity Maps client.
        
        Args:
            session: aiohttp session
            api_key: Electricity Maps API key (required)
        """
        self.session = session
        self.api_key = api_key
        self.base_url = ELECTRICITY_MAPS_API_BASE

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict | None:
        """Make an authenticated request to the API."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "auth-token": self.api_key,
        }

        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    _LOGGER.error("Electricity Maps API: Invalid API key")
                elif response.status == 429:
                    _LOGGER.warning("Electricity Maps API: Rate limit exceeded")
                else:
                    _LOGGER.error("Electricity Maps API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("Electricity Maps API request failed: %s", e)
            return None

    async def get_carbon_intensity(self, zone: str) -> ZoneCarbonIntensity | None:
        """Get current carbon intensity for a zone.
        
        Args:
            zone: Zone code (e.g., "GB", "DE", "US-CAL-CISO")
        
        Returns:
            ZoneCarbonIntensity with current carbon data
        """
        data = await self._request("/carbon-intensity/latest", {"zone": zone})
        if not data:
            return None

        try:
            zone_info = ELECTRICITY_MAPS_ZONES.get(zone, {"name": zone, "country": ""})

            return ZoneCarbonIntensity(
                zone=zone,
                zone_name=zone_info.get("name", zone),
                carbon_intensity=data.get("carbonIntensity", 0),
                carbon_intensity_unit="gCO2eq/kWh",
                fossil_free_percentage=data.get("fossilFreePercentage"),
                renewable_percentage=data.get("renewablePercentage"),
                timestamp=datetime.fromisoformat(
                    data.get("datetime", "").replace("Z", "+00:00")
                ),
                data_source="Electricity Maps",
            )
        except Exception as e:
            _LOGGER.error("Error parsing Electricity Maps carbon data: %s", e)
            return None

    async def get_power_breakdown(self, zone: str) -> ZonePowerBreakdown | None:
        """Get current power breakdown for a zone.
        
        Args:
            zone: Zone code (e.g., "GB", "DE", "US-CAL-CISO")
        
        Returns:
            ZonePowerBreakdown with generation by source
        """
        data = await self._request("/power-breakdown/latest", {"zone": zone})
        if not data:
            return None

        try:
            zone_info = ELECTRICITY_MAPS_ZONES.get(zone, {"name": zone, "country": ""})

            # Extract power production by source
            production = data.get("powerProductionBreakdown", {})
            generation_by_source = {}
            for fuel, value in production.items():
                if value is not None and value > 0:
                    generation_by_source[fuel] = value

            return ZonePowerBreakdown(
                zone=zone,
                zone_name=zone_info.get("name", zone),
                power_consumption_mw=data.get("powerConsumptionTotal"),
                power_production_mw=data.get("powerProductionTotal"),
                power_import_mw=data.get("powerImportTotal"),
                power_export_mw=data.get("powerExportTotal"),
                generation_by_source=generation_by_source,
                timestamp=datetime.fromisoformat(
                    data.get("datetime", "").replace("Z", "+00:00")
                ),
                data_source="Electricity Maps",
            )
        except Exception as e:
            _LOGGER.error("Error parsing Electricity Maps power data: %s", e)
            return None

    async def get_zone_history(
        self,
        zone: str,
        hours: int = 24,
    ) -> list[ZoneCarbonIntensity]:
        """Get historical carbon intensity for a zone.
        
        Args:
            zone: Zone code
            hours: Number of hours of history (default 24)
        
        Returns:
            List of ZoneCarbonIntensity objects
        """
        data = await self._request("/carbon-intensity/history", {"zone": zone})
        if not data or "history" not in data:
            return []

        results = []
        zone_info = ELECTRICITY_MAPS_ZONES.get(zone, {"name": zone, "country": ""})

        for entry in data.get("history", [])[:hours]:
            try:
                results.append(ZoneCarbonIntensity(
                    zone=zone,
                    zone_name=zone_info.get("name", zone),
                    carbon_intensity=entry.get("carbonIntensity", 0),
                    carbon_intensity_unit="gCO2eq/kWh",
                    fossil_free_percentage=entry.get("fossilFreePercentage"),
                    renewable_percentage=entry.get("renewablePercentage"),
                    timestamp=datetime.fromisoformat(
                        entry.get("datetime", "").replace("Z", "+00:00")
                    ),
                    data_source="Electricity Maps",
                ))
            except Exception:
                continue

        return results

    async def get_zones(self) -> list[str]:
        """Get list of available zones.
        
        Returns:
            List of zone codes
        """
        data = await self._request("/zones")
        if not data:
            return list(ELECTRICITY_MAPS_ZONES.keys())

        return list(data.keys())


class EIAClient:
    """Client for US Energy Information Administration (EIA) API v2.
    
    API Documentation: https://www.eia.gov/opendata/documentation.php
    Free API with key, no rate limits mentioned
    Provides: US electricity generation, consumption, prices, fuel mix
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
    ) -> None:
        """Initialize the EIA client.
        
        Args:
            session: aiohttp session
            api_key: EIA API key (required, free registration)
        """
        self.session = session
        self.api_key = api_key
        self.base_url = EIA_API_BASE

    async def _request(
        self,
        route: str,
        params: dict[str, Any] | None = None,
    ) -> dict | None:
        """Make a request to the EIA API."""
        url = f"{self.base_url}/{route}"
        request_params = {"api_key": self.api_key}
        if params:
            request_params.update(params)

        try:
            async with self.session.get(url, params=request_params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    _LOGGER.error("EIA API: Invalid API key")
                else:
                    _LOGGER.error("EIA API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("EIA API request failed: %s", e)
            return None

    async def get_hourly_grid_monitor(
        self,
        region: str = "US48",
    ) -> ZonePowerBreakdown | None:
        """Get hourly grid monitor data for a region.
        
        Args:
            region: EIA region code (e.g., "CISO", "ERCO", "US48")
        
        Returns:
            ZonePowerBreakdown with generation data
        """
        # Use the electricity/rto route for real-time data
        params = {
            "frequency": "hourly",
            "data[]": "value",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "24",
        }

        if region != "US48":
            params["facets[respondent][]"] = region

        data = await self._request("electricity/rto/fuel-type-data/data", params)
        if not data or "response" not in data:
            return None

        try:
            rows = data.get("response", {}).get("data", [])
            if not rows:
                return None

            # Aggregate by fuel type (latest hour)
            generation_by_source = {}
            latest_period = rows[0].get("period") if rows else None
            total_gen = 0

            for row in rows:
                if row.get("period") != latest_period:
                    break
                fuel = row.get("fueltype", "unknown")
                value = float(row.get("value", 0))
                generation_by_source[fuel] = value
                total_gen += value

            region_info = EIA_REGIONS.get(region, {"name": region, "type": "region"})

            return ZonePowerBreakdown(
                zone=region,
                zone_name=region_info.get("name", region),
                power_consumption_mw=None,  # Separate endpoint
                power_production_mw=total_gen,
                power_import_mw=None,
                power_export_mw=None,
                generation_by_source=generation_by_source,
                timestamp=datetime.fromisoformat(latest_period) if latest_period else datetime.now(),
                data_source="EIA",
            )
        except Exception as e:
            _LOGGER.error("Error parsing EIA data: %s", e)
            return None

    async def get_demand(self, region: str = "US48") -> float | None:
        """Get current demand for a region.
        
        Args:
            region: EIA region code
        
        Returns:
            Demand in MW
        """
        params = {
            "frequency": "hourly",
            "data[]": "value",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "1",
        }

        if region != "US48":
            params["facets[respondent][]"] = region

        data = await self._request("electricity/rto/demand/data", params)
        if not data or "response" not in data:
            return None

        try:
            rows = data.get("response", {}).get("data", [])
            if rows:
                return float(rows[0].get("value", 0))
            return None
        except Exception as e:
            _LOGGER.error("Error parsing EIA demand: %s", e)
            return None


class ENTSOEClient:
    """Client for ENTSO-E Transparency Platform API.
    
    API Documentation: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
    Free registration required for security token
    Provides: European grid data - generation, load, cross-border flows
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        security_token: str,
    ) -> None:
        """Initialize the ENTSO-E client.
        
        Args:
            session: aiohttp session
            security_token: ENTSO-E security token (required)
        """
        self.session = session
        self.security_token = security_token
        self.base_url = ENTSOE_API_BASE

    async def _request(self, params: dict[str, Any]) -> str | None:
        """Make a request to the ENTSO-E API (returns XML)."""
        params["securityToken"] = self.security_token

        try:
            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 401:
                    _LOGGER.error("ENTSO-E API: Invalid security token")
                else:
                    _LOGGER.error("ENTSO-E API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("ENTSO-E API request failed: %s", e)
            return None

    def _parse_xml_timeseries(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse ENTSO-E XML response for time series data."""
        results = []
        try:
            ns = {"ns": "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0"}
            root = ET.fromstring(xml_text)

            for ts in root.findall(".//ns:TimeSeries", ns):
                mrid = ts.find("ns:mRID", ns)
                psr_type = ts.find(".//ns:psrType", ns)

                for period in ts.findall(".//ns:Period", ns):
                    for point in period.findall(".//ns:Point", ns):
                        position = point.find("ns:position", ns)
                        quantity = point.find("ns:quantity", ns)

                        if quantity is not None:
                            results.append({
                                "mrid": mrid.text if mrid is not None else None,
                                "psr_type": psr_type.text if psr_type is not None else None,
                                "position": int(position.text) if position is not None else 0,
                                "quantity": float(quantity.text),
                            })
        except Exception as e:
            _LOGGER.error("Error parsing ENTSO-E XML: %s", e)

        return results

    async def get_generation_per_type(
        self,
        area_code: str,
        hours_back: int = 1,
    ) -> ZonePowerBreakdown | None:
        """Get actual generation per type for an area.
        
        Args:
            area_code: ENTSO-E EIC area code (e.g., "10YGB----------A" for GB)
            hours_back: Hours of data to fetch
        
        Returns:
            ZonePowerBreakdown with generation by source
        """
        now = datetime.utcnow()
        start = (now - timedelta(hours=hours_back)).strftime("%Y%m%d%H00")
        end = now.strftime("%Y%m%d%H00")

        params = {
            "documentType": "A75",  # Actual generation per type
            "processType": "A16",  # Realised
            "in_Domain": area_code,
            "periodStart": start,
            "periodEnd": end,
        }

        xml_data = await self._request(params)
        if not xml_data:
            return None

        try:
            results = self._parse_xml_timeseries(xml_data)

            # Map ENTSO-E PSR types to fuel names
            psr_type_map = {
                "B01": "biomass", "B02": "brown_coal", "B03": "coal_gas",
                "B04": "gas", "B05": "coal", "B06": "oil",
                "B09": "geothermal", "B10": "hydro_pumped", "B11": "hydro",
                "B12": "hydro_reservoir", "B13": "marine", "B14": "nuclear",
                "B15": "other_renewable", "B16": "solar", "B17": "waste",
                "B18": "wind_offshore", "B19": "wind_onshore", "B20": "other",
            }

            generation_by_source = {}
            total = 0
            for entry in results:
                psr = entry.get("psr_type", "")
                fuel = psr_type_map.get(psr, psr)
                val = entry.get("quantity", 0)
                if fuel in generation_by_source:
                    generation_by_source[fuel] += val
                else:
                    generation_by_source[fuel] = val
                total += val

            area_info = ENTSOE_AREAS.get(area_code, {"name": area_code, "country": ""})

            return ZonePowerBreakdown(
                zone=area_code,
                zone_name=area_info.get("name", area_code),
                power_consumption_mw=None,
                power_production_mw=total,
                power_import_mw=None,
                power_export_mw=None,
                generation_by_source=generation_by_source,
                timestamp=datetime.utcnow(),
                data_source="ENTSO-E",
            )
        except Exception as e:
            _LOGGER.error("Error parsing ENTSO-E generation: %s", e)
            return None

    async def get_total_load(
        self,
        area_code: str,
        hours_back: int = 1,
    ) -> float | None:
        """Get actual total load for an area.
        
        Args:
            area_code: ENTSO-E EIC area code
            hours_back: Hours of data to fetch
        
        Returns:
            Total load in MW
        """
        now = datetime.utcnow()
        start = (now - timedelta(hours=hours_back)).strftime("%Y%m%d%H00")
        end = now.strftime("%Y%m%d%H00")

        params = {
            "documentType": "A65",  # System total load
            "processType": "A16",  # Realised
            "outBiddingZone_Domain": area_code,
            "periodStart": start,
            "periodEnd": end,
        }

        xml_data = await self._request(params)
        if not xml_data:
            return None

        try:
            results = self._parse_xml_timeseries(xml_data)
            if results:
                # Return the latest value
                return results[-1].get("quantity")
            return None
        except Exception as e:
            _LOGGER.error("Error parsing ENTSO-E load: %s", e)
            return None


class OpenElectricityClient:
    """Client for OpenElectricity (formerly OpenNEM) - Australia NEM/WEM.
    
    API Documentation: https://docs.openelectricity.org.au/
    Free API, no key required
    Provides: Australia NEM/WEM generation, demand, emissions
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the OpenElectricity client."""
        self.session = session
        self.base_url = OPENELECTRICITY_API_BASE

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict | None:
        """Make a request to the OpenElectricity API."""
        url = f"{self.base_url}{endpoint}"

        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    _LOGGER.error("OpenElectricity API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("OpenElectricity API request failed: %s", e)
            return None

    async def get_network_data(
        self,
        network: str = "NEM",
        region: str | None = None,
    ) -> ZonePowerBreakdown | None:
        """Get current network data.
        
        Args:
            network: Network code ("NEM" or "WEM")
            region: Optional region code (e.g., "NSW1", "VIC1")
        
        Returns:
            ZonePowerBreakdown with generation data
        """
        endpoint = f"/stats/{network.lower()}"
        if region:
            endpoint += f"/{region}"

        data = await self._request(endpoint)
        if not data:
            return None

        try:
            generation_by_source = {}
            for fuel_data in data.get("fueltech", []):
                fuel = fuel_data.get("fuel_tech", "unknown")
                output = fuel_data.get("generation", 0) or 0
                if output > 0:
                    generation_by_source[fuel] = output

            zone_name = region if region else network
            region_info = AUSTRALIA_REGIONS.get(zone_name, {"name": zone_name, "network": network})

            return ZonePowerBreakdown(
                zone=zone_name,
                zone_name=region_info.get("name", zone_name),
                power_consumption_mw=data.get("demand"),
                power_production_mw=data.get("generation"),
                power_import_mw=data.get("imports"),
                power_export_mw=data.get("exports"),
                generation_by_source=generation_by_source,
                timestamp=datetime.fromisoformat(
                    data.get("data_updated", "").replace("Z", "+00:00")
                ) if data.get("data_updated") else datetime.now(),
                data_source="OpenElectricity",
            )
        except Exception as e:
            _LOGGER.error("Error parsing OpenElectricity data: %s", e)
            return None

    async def get_carbon_intensity(
        self,
        network: str = "NEM",
    ) -> ZoneCarbonIntensity | None:
        """Get carbon intensity for a network.
        
        Args:
            network: Network code ("NEM" or "WEM")
        
        Returns:
            ZoneCarbonIntensity with emissions data
        """
        data = await self._request(f"/stats/{network.lower()}/emissions")
        if not data:
            return None

        try:
            return ZoneCarbonIntensity(
                zone=network,
                zone_name=f"Australia {network}",
                carbon_intensity=data.get("emissions_intensity", 0),
                carbon_intensity_unit="kgCO2e/MWh",
                fossil_free_percentage=None,
                renewable_percentage=data.get("renewables_proportion", 0) * 100,
                timestamp=datetime.fromisoformat(
                    data.get("data_updated", "").replace("Z", "+00:00")
                ) if data.get("data_updated") else datetime.now(),
                data_source="OpenElectricity",
            )
        except Exception as e:
            _LOGGER.error("Error parsing OpenElectricity emissions: %s", e)
            return None


class REEEsiosClient:
    """Client for REE Esios API - Spain electricity data.
    
    API: https://api.esios.ree.es
    Free API, no authentication required for basic data
    Provides: Spain generation, demand, prices, emissions
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the REE Esios client."""
        self.session = session
        self.base_url = REE_ESIOS_API_BASE

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict | None:
        """Make a request to the REE Esios API."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Accept": "application/json; application/vnd.esios-api-v1+json",
        }

        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    _LOGGER.error("REE Esios API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("REE Esios API request failed: %s", e)
            return None

    async def get_generation_structure(self) -> ZonePowerBreakdown | None:
        """Get current generation structure for Spain.
        
        Returns:
            ZonePowerBreakdown with generation by source
        """
        # Indicator 1293 = Real demand
        # Indicator 10195 = Generation structure
        data = await self._request("/indicators/1293")
        if not data or "indicator" not in data:
            return None

        try:
            indicator = data.get("indicator", {})
            values = indicator.get("values", [])

            if not values:
                return None

            latest = values[0]

            return ZonePowerBreakdown(
                zone="ES",
                zone_name="Spain - Peninsular",
                power_consumption_mw=latest.get("value"),
                power_production_mw=None,  # Separate indicator
                power_import_mw=None,
                power_export_mw=None,
                generation_by_source={},  # Need to query indicator 10195
                timestamp=datetime.fromisoformat(
                    latest.get("datetime", "").replace("Z", "+00:00")
                ) if latest.get("datetime") else datetime.now(),
                data_source="REE Esios",
            )
        except Exception as e:
            _LOGGER.error("Error parsing REE Esios data: %s", e)
            return None

    async def get_carbon_free_percentage(self) -> float | None:
        """Get current CO2-free generation percentage.
        
        Returns:
            Percentage of CO2-free generation
        """
        # Indicator 541 = % carbon-free generation
        data = await self._request("/indicators/541")
        if not data or "indicator" not in data:
            return None

        try:
            values = data.get("indicator", {}).get("values", [])
            if values:
                return values[0].get("value")
            return None
        except Exception as e:
            _LOGGER.error("Error parsing REE Esios CO2 data: %s", e)
            return None


class RTEClient:
    """Client for RTE Data API - France electricity data.
    
    API: https://data.rte-france.com/
    OAuth2 authentication required (free registration)
    Provides: France generation, consumption, cross-border flows
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize the RTE client.
        
        Args:
            session: aiohttp session
            client_id: RTE OAuth client ID
            client_secret: RTE OAuth client secret
        """
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = RTE_API_BASE
        self._access_token: str | None = None
        self._token_expires: datetime | None = None

    async def _get_token(self) -> str | None:
        """Get or refresh OAuth2 access token."""
        if self._access_token and self._token_expires and datetime.now() < self._token_expires:
            return self._access_token

        auth_url = f"{self.base_url}/token/oauth/"
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            async with self.session.post(auth_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    self._access_token = data.get("access_token")
                    expires_in = data.get("expires_in", 3600)
                    self._token_expires = datetime.now() + timedelta(seconds=expires_in - 60)
                    return self._access_token
                else:
                    _LOGGER.error("RTE OAuth error: %s", response.status)
                    return None
        except Exception as e:
            _LOGGER.error("RTE OAuth request failed: %s", e)
            return None

    async def _request(
        self,
        api_name: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict | None:
        """Make an authenticated request to the RTE API."""
        token = await self._get_token()
        if not token:
            return None

        url = f"{self.base_url}/open_api/{api_name}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
        }

        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    _LOGGER.error("RTE API error: %s", response.status)
                return None
        except Exception as e:
            _LOGGER.error("RTE API request failed: %s", e)
            return None

    async def get_actual_generation(self) -> ZonePowerBreakdown | None:
        """Get actual generation by fuel type for France.
        
        Returns:
            ZonePowerBreakdown with generation data
        """
        data = await self._request("actual_generation", "v1/actual_generations_per_production_type")
        if not data:
            return None

        try:
            generation_by_source = {}
            total = 0

            for entry in data.get("actual_generations_per_production_type", []):
                fuel = entry.get("production_type", "unknown")
                values = entry.get("values", [])
                if values:
                    latest = values[-1].get("value", 0)
                    generation_by_source[fuel] = latest
                    total += latest

            return ZonePowerBreakdown(
                zone="FR",
                zone_name="France",
                power_consumption_mw=None,
                power_production_mw=total,
                power_import_mw=None,
                power_export_mw=None,
                generation_by_source=generation_by_source,
                timestamp=datetime.now(),
                data_source="RTE",
            )
        except Exception as e:
            _LOGGER.error("Error parsing RTE generation: %s", e)
            return None

    async def get_consumption(self) -> float | None:
        """Get current consumption for France.
        
        Returns:
            Consumption in MW
        """
        data = await self._request("consumption", "v1/short_term")
        if not data:
            return None

        try:
            values = data.get("short_term", [{}])[0].get("values", [])
            if values:
                return values[-1].get("value")
            return None
        except Exception as e:
            _LOGGER.error("Error parsing RTE consumption: %s", e)
            return None


# ============================================================================
# ADDITIONAL OPEN API CLIENTS
# ============================================================================


@dataclass
class GridFrequency:
    """Grid frequency data."""

    frequency_hz: float
    timestamp: datetime
    target_hz: float = 50.0  # Most grids target 50Hz (60Hz in Americas)
    deviation_hz: float = 0.0
    status: str = "normal"
    data_source: str = ""


@dataclass
class DayAheadPrice:
    """Day-ahead electricity price data."""

    price: float
    currency: str
    price_area: str
    timestamp: datetime
    unit: str = "EUR/MWh"
    data_source: str = ""


@dataclass
class ImbalanceData:
    """Grid imbalance data."""

    system_imbalance_mw: float
    imbalance_price: float
    currency: str
    timestamp: datetime
    direction: str = ""  # "long" or "short"
    data_source: str = ""


# ============================================================================
# NORDIC REGION
# ============================================================================


class FingridClient:
    """Client for Fingrid Open Data API (Finland).
    
    API Documentation: https://data.fingrid.fi/
    Free API key required (registration).
    
    Provides: Production, consumption, wind/solar, frequency, cross-border flows.
    """

    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        """Initialize the client.
        
        Args:
            session: aiohttp client session
            api_key: Fingrid API key (free registration)
        """
        self._session = session
        self._api_key = api_key
        self._base_url = "https://api.fingrid.fi/v1"

    async def _request(self, dataset_id: int, start_time: str | None = None) -> list[dict] | None:
        """Make API request to Fingrid.
        
        Args:
            dataset_id: Fingrid dataset ID
            start_time: Optional start time (ISO format)
        """
        url = f"{self._base_url}/variable/{dataset_id}/events/json"
        headers = {"x-api-key": self._api_key}
        params = {}
        if start_time:
            params["start_time"] = start_time

        try:
            async with self._session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                _LOGGER.warning("Fingrid API returned %d for dataset %d", resp.status, dataset_id)
                return None
        except Exception as e:
            _LOGGER.error("Fingrid API error: %s", e)
            return None

    async def get_electricity_production(self) -> float | None:
        """Get total electricity production in Finland (MW)."""
        data = await self._request(74)  # Dataset ID for electricity production
        if data and len(data) > 0:
            return data[-1].get("value")
        return None

    async def get_electricity_consumption(self) -> float | None:
        """Get total electricity consumption in Finland (MW)."""
        data = await self._request(124)
        if data and len(data) > 0:
            return data[-1].get("value")
        return None

    async def get_wind_power(self) -> float | None:
        """Get wind power production in Finland (MW)."""
        data = await self._request(75)
        if data and len(data) > 0:
            return data[-1].get("value")
        return None

    async def get_solar_power(self) -> float | None:
        """Get solar power production in Finland (MW)."""
        data = await self._request(248)
        if data and len(data) > 0:
            return data[-1].get("value")
        return None

    async def get_nuclear_power(self) -> float | None:
        """Get nuclear power production in Finland (MW)."""
        data = await self._request(188)
        if data and len(data) > 0:
            return data[-1].get("value")
        return None

    async def get_frequency(self) -> GridFrequency | None:
        """Get current grid frequency in Finland."""
        data = await self._request(177)
        if data and len(data) > 0:
            latest = data[-1]
            freq = latest.get("value", 50.0)
            deviation = freq - 50.0
            status = "normal" if abs(deviation) < 0.1 else ("high" if deviation > 0 else "low")
            return GridFrequency(
                frequency_hz=freq,
                timestamp=datetime.fromisoformat(latest.get("start_time", "").replace("Z", "+00:00")),
                target_hz=50.0,
                deviation_hz=deviation,
                status=status,
                data_source="Fingrid",
            )
        return None

    async def get_power_breakdown(self) -> ZonePowerBreakdown | None:
        """Get comprehensive power breakdown for Finland."""
        # Fetch all data in parallel
        results = await asyncio.gather(
            self.get_electricity_production(),
            self.get_electricity_consumption(),
            self.get_wind_power(),
            self.get_solar_power(),
            self.get_nuclear_power(),
            self._request(191),  # Hydro
            return_exceptions=True,
        )

        production = results[0] if not isinstance(results[0], Exception) else None
        consumption = results[1] if not isinstance(results[1], Exception) else None
        wind = results[2] if not isinstance(results[2], Exception) else None
        solar = results[3] if not isinstance(results[3], Exception) else None
        nuclear = results[4] if not isinstance(results[4], Exception) else None
        hydro_data = results[5] if not isinstance(results[5], Exception) else None
        hydro = hydro_data[-1].get("value") if hydro_data and len(hydro_data) > 0 else None

        generation_by_source = {}
        if wind:
            generation_by_source["wind"] = wind
        if solar:
            generation_by_source["solar"] = solar
        if nuclear:
            generation_by_source["nuclear"] = nuclear
        if hydro:
            generation_by_source["hydro"] = hydro

        # Calculate renewable percentage
        renewable_mw = (wind or 0) + (solar or 0) + (hydro or 0)
        renewable_pct = (renewable_mw / production * 100) if production and production > 0 else None

        return ZonePowerBreakdown(
            zone="FI",
            zone_name="Finland",
            power_consumption_mw=consumption,
            power_production_mw=production,
            power_import_mw=None,
            power_export_mw=None,
            generation_by_source=generation_by_source,
            renewable_percentage=renewable_pct,
            timestamp=datetime.now(UTC),
            data_source="Fingrid",
        )


class EnerginetClient:
    """Client for Energi Data Service API (Denmark).
    
    API Documentation: https://www.energidataservice.dk/
    Free, no authentication required.
    
    Provides: CO2 emissions, day-ahead prices, generation, consumption.
    """

    def __init__(self, session: aiohttp.ClientSession):
        """Initialize the client."""
        self._session = session
        self._base_url = "https://api.energidataservice.dk"

    async def _request(self, dataset: str, limit: int = 1, sort: str = "HourUTC DESC") -> dict | None:
        """Make API request to Energinet."""
        url = f"{self._base_url}/dataset/{dataset}"
        params = {
            "limit": limit,
            "sort": sort,
        }

        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                _LOGGER.warning("Energinet API returned %d for %s", resp.status, dataset)
                return None
        except Exception as e:
            _LOGGER.error("Energinet API error: %s", e)
            return None

    async def get_co2_emission(self) -> ZoneCarbonIntensity | None:
        """Get current CO2 emission intensity for Denmark."""
        data = await self._request("CO2Emis", limit=2)
        if not data or not data.get("records"):
            return None

        records = data["records"]
        if not records:
            return None

        # Get DK1 and DK2 (West and East Denmark)
        dk1 = next((r for r in records if r.get("PriceArea") == "DK1"), None)
        dk2 = next((r for r in records if r.get("PriceArea") == "DK2"), None)

        # Use average or available
        co2_dk1 = dk1.get("CO2Emission", 0) if dk1 else 0
        co2_dk2 = dk2.get("CO2Emission", 0) if dk2 else 0
        co2_avg = (co2_dk1 + co2_dk2) / 2 if co2_dk1 and co2_dk2 else (co2_dk1 or co2_dk2)

        return ZoneCarbonIntensity(
            zone="DK",
            zone_name="Denmark",
            carbon_intensity=int(co2_avg),
            fossil_fuel_percentage=None,
            timestamp=datetime.now(UTC),
            data_source="Energinet",
        )

    async def get_day_ahead_prices(self, price_area: str = "DK1") -> DayAheadPrice | None:
        """Get day-ahead electricity prices for Denmark.
        
        Args:
            price_area: "DK1" (West) or "DK2" (East)
        """
        data = await self._request("Elspotprices", limit=24)
        if not data or not data.get("records"):
            return None

        # Find latest for specified area
        for record in data["records"]:
            if record.get("PriceArea") == price_area:
                return DayAheadPrice(
                    price=record.get("SpotPriceEUR", 0),
                    currency="EUR",
                    price_area=price_area,
                    timestamp=datetime.fromisoformat(record.get("HourUTC", "").replace("Z", "+00:00")),
                    unit="EUR/MWh",
                    data_source="Energinet",
                )
        return None

    async def get_production_consumption(self) -> ZonePowerBreakdown | None:
        """Get production and consumption data for Denmark."""
        data = await self._request("ProductionConsumptionSettlement", limit=10)
        if not data or not data.get("records"):
            return None

        records = data["records"]
        # Sum up latest records for all areas
        latest_hour = records[0].get("HourUTC") if records else None

        total_production = 0
        total_consumption = 0
        generation_by_source = {}

        for record in records:
            if record.get("HourUTC") == latest_hour:
                # Add generation by source
                for key in ["OnshoreWindPower", "OffshoreWindPower", "SolarPower",
                           "ThermalPower", "HydroPower"]:
                    val = record.get(key, 0) or 0
                    fuel = key.replace("Power", "").lower()
                    if fuel in generation_by_source:
                        generation_by_source[fuel] += val
                    else:
                        generation_by_source[fuel] = val
                    total_production += val

                total_consumption += record.get("GrossConsumption", 0) or 0

        # Combine wind types
        if "onshorewind" in generation_by_source or "offshorewind" in generation_by_source:
            generation_by_source["wind"] = (
                generation_by_source.pop("onshorewind", 0) +
                generation_by_source.pop("offshorewind", 0)
            )

        renewable_mw = (
            generation_by_source.get("wind", 0) +
            generation_by_source.get("solar", 0) +
            generation_by_source.get("hydro", 0)
        )
        renewable_pct = (renewable_mw / total_production * 100) if total_production > 0 else None

        return ZonePowerBreakdown(
            zone="DK",
            zone_name="Denmark",
            power_consumption_mw=total_consumption,
            power_production_mw=total_production,
            power_import_mw=None,
            power_export_mw=None,
            generation_by_source=generation_by_source,
            renewable_percentage=renewable_pct,
            timestamp=datetime.now(UTC),
            data_source="Energinet",
        )


# ============================================================================
# WESTERN EUROPE
# ============================================================================


class EliaClient:
    """Client for Elia Open Data API (Belgium).
    
    API Documentation: https://opendata.elia.be/
    Free, no authentication required.
    
    Dataset IDs (updated after MARI go-live 22/05/2024):
    - ods169: Current system imbalance (near real-time)
    - ods161: Imbalance prices per minute
    - ods162: Imbalance prices per quarter-hour
    - ods002: Measured and forecasted total load
    - ods086: Wind power production
    - ods087: Photovoltaic power production
    
    Provides: Imbalance prices, system imbalance, wind/solar forecasts, load.
    """

    def __init__(self, session: aiohttp.ClientSession):
        """Initialize the client."""
        self._session = session
        self._base_url = "https://opendata.elia.be/api/explore/v2.1"

    async def _request(self, dataset: str, limit: int = 1, order_by: str = "datetime DESC") -> dict | None:
        """Make API request to Elia."""
        url = f"{self._base_url}/catalog/datasets/{dataset}/records"
        params = {
            "limit": limit,
            "order_by": order_by,
        }

        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                _LOGGER.warning("Elia API returned %d for %s", resp.status, dataset)
                return None
        except Exception as e:
            _LOGGER.error("Elia API error: %s", e)
            return None

    async def get_current_imbalance(self) -> ImbalanceData | None:
        """Get current system imbalance for Belgium.
        
        Uses ods169 - Current system imbalance (near real-time).
        """
        data = await self._request("ods169")
        if not data or not data.get("results"):
            return None

        record = data["results"][0]
        # ods169 fields: datetime, systemimbalance, acevalue, etc.
        imbalance = record.get("systemimbalance", record.get("system_imbalance", 0))
        direction = "long" if imbalance > 0 else "short"

        # Get timestamp - handle different field names
        timestamp_str = record.get("datetime", record.get("timestamp", ""))
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.now(UTC)

        return ImbalanceData(
            system_imbalance_mw=imbalance,
            imbalance_price=record.get("alpha", 0),
            currency="EUR",
            timestamp=timestamp,
            direction=direction,
            data_source="Elia",
        )

    async def get_imbalance_prices(self) -> dict | None:
        """Get current imbalance prices for Belgium.
        
        Uses ods162 - Imbalance prices per quarter-hour.
        """
        data = await self._request("ods162")
        if not data or not data.get("results"):
            return None

        record = data["results"][0]
        return {
            "positive_imbalance_price": record.get("positiveimbalanceprice", record.get("pos_imb_price")),
            "negative_imbalance_price": record.get("negativeimbalanceprice", record.get("neg_imb_price")),
            "alpha": record.get("alpha"),
            "timestamp": record.get("datetime", record.get("timestamp")),
            "currency": "EUR",
            "unit": "EUR/MWh",
        }

    async def get_total_load(self) -> float | None:
        """Get total load for Belgium (MW).
        
        Uses ods002 - Measured and forecasted total load.
        Fields: datetime, resolutioncode, measured, mostrecentforecast, etc.
        """
        data = await self._request("ods002")
        if not data or not data.get("results"):
            return None

        record = data["results"][0]
        # ods002 uses 'measured' for actual load value
        return record.get("measured", record.get("mostrecentforecast", record.get("totalload")))

    async def get_solar_power(self) -> dict | None:
        """Get solar/PV power data for Belgium.
        
        Uses ods087 - Photovoltaic power production.
        Fields: datetime, resolutioncode, region, realtime, mostrecentforecast, etc.
        """
        data = await self._request("ods087", limit=48)
        if not data or not data.get("results"):
            return None

        forecasts = []
        for record in data["results"]:
            forecasts.append({
                "datetime": record.get("datetime"),
                "realtime_mw": record.get("realtime"),
                "forecast_mw": record.get("mostrecentforecast"),
                "dayahead_forecast_mw": record.get("dayahead11hforecast"),
                "region": record.get("region"),
            })
        return forecasts

    async def get_wind_power(self) -> dict | None:
        """Get wind power data for Belgium.
        
        Uses ods086 - Wind power production.
        Fields: datetime, resolutioncode, offshoreonshore, region, gridconnectiontype, 
                realtime, mostrecentforecast, mostrecentconfidence10, etc.
        """
        data = await self._request("ods086")
        if not data or not data.get("results"):
            return None

        record = data["results"][0]
        return {
            "realtime_mw": record.get("realtime"),
            "forecast_mw": record.get("mostrecentforecast"),
            "offshore_onshore": record.get("offshoreonshore"),
            "region": record.get("region"),
            "datetime": record.get("datetime"),
        }

    async def get_power_breakdown(self) -> ZonePowerBreakdown | None:
        """Get power breakdown for Belgium."""
        results = await asyncio.gather(
            self.get_total_load(),
            self.get_wind_power(),
            self._request("ods087"),  # Solar/PV
            return_exceptions=True,
        )

        load = results[0] if not isinstance(results[0], Exception) else None
        wind_data = results[1] if not isinstance(results[1], Exception) else None
        solar_data = results[2] if not isinstance(results[2], Exception) else None

        generation_by_source = {}

        if wind_data and isinstance(wind_data, dict):
            wind_val = wind_data.get("realtime_mw") or wind_data.get("forecast_mw")
            if wind_val:
                generation_by_source["wind"] = wind_val

        if solar_data and solar_data.get("results"):
            record = solar_data["results"][0]
            solar_val = record.get("realtime") or record.get("mostrecentforecast")
            if solar_val:
                generation_by_source["solar"] = solar_val

        return ZonePowerBreakdown(
            zone="BE",
            zone_name="Belgium",
            power_consumption_mw=load,
            power_production_mw=None,
            power_import_mw=None,
            power_export_mw=None,
            generation_by_source=generation_by_source,
            timestamp=datetime.now(UTC),
            data_source="Elia",
        )


class SMARDClient:
    """Client for SMARD API (Germany - Bundesnetzagentur).
    
    Documentation: https://www.smard.de/
    Free, no authentication required.
    
    Provides: Generation by source, consumption, prices, cross-border flows.
    """

    def __init__(self, session: aiohttp.ClientSession):
        """Initialize the client."""
        self._session = session
        self._base_url = "https://www.smard.de/app/chart_data"

    # SMARD filter IDs for different data types
    FILTERS: ClassVar[dict[str, Any]] = {
        "generation_total": 1223,
        "generation_biomass": 4066,
        "generation_hydro": 1226,
        "generation_wind_offshore": 1225,
        "generation_wind_onshore": 4067,
        "generation_solar": 4068,
        "generation_nuclear": 1224,
        "generation_lignite": 1227,
        "generation_hard_coal": 1228,
        "generation_gas": 4071,
        "generation_pumped_storage": 4070,
        "generation_other_conventional": 1223,
        "consumption": 410,
        "price_day_ahead": 4169,
        "cross_border_de_at": 252,
        "cross_border_de_ch": 253,
        "cross_border_de_fr": 254,
    }

    async def _request(self, filter_id: int, region: str = "DE") -> dict | None:
        """Make API request to SMARD."""
        # Get index to find latest timestamp
        index_url = f"{self._base_url}/{filter_id}/{region}/index_quarterhour.json"

        try:
            async with self._session.get(index_url) as resp:
                if resp.status != 200:
                    _LOGGER.warning("SMARD index returned %d", resp.status)
                    return None
                index_data = await resp.json()

            timestamps = index_data.get("timestamps", [])
            if not timestamps:
                return None

            # Get latest timestamp data
            latest_ts = timestamps[-1]
            data_url = f"{self._base_url}/{filter_id}/{region}/{filter_id}_{region}_quarterhour_{latest_ts}.json"

            async with self._session.get(data_url) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            _LOGGER.error("SMARD API error: %s", e)
            return None

    async def get_generation_mix(self) -> ZonePowerBreakdown | None:
        """Get current generation mix for Germany."""
        # Fetch all generation types in parallel
        filter_ids = {
            "solar": 4068,
            "wind_onshore": 4067,
            "wind_offshore": 1225,
            "hydro": 1226,
            "biomass": 4066,
            "nuclear": 1224,
            "lignite": 1227,
            "hard_coal": 1228,
            "gas": 4071,
            "pumped_storage": 4070,
        }

        tasks = {fuel: self._request(fid) for fuel, fid in filter_ids.items()}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        generation_by_source = {}
        total_production = 0
        renewable_mw = 0

        for fuel, result in zip(tasks.keys(), results, strict=True):
            if isinstance(result, Exception) or not result:
                continue

            series = result.get("series", [])
            if series:
                # Get latest non-null value
                for entry in reversed(series):
                    if entry[1] is not None:
                        val = entry[1]
                        generation_by_source[fuel] = val
                        total_production += val

                        # Track renewables
                        if fuel in ["solar", "wind_onshore", "wind_offshore", "hydro", "biomass"]:
                            renewable_mw += val
                        break

        # Combine wind types
        if "wind_onshore" in generation_by_source or "wind_offshore" in generation_by_source:
            generation_by_source["wind"] = (
                generation_by_source.pop("wind_onshore", 0) +
                generation_by_source.pop("wind_offshore", 0)
            )

        renewable_pct = (renewable_mw / total_production * 100) if total_production > 0 else None

        return ZonePowerBreakdown(
            zone="DE",
            zone_name="Germany",
            power_consumption_mw=None,
            power_production_mw=total_production,
            power_import_mw=None,
            power_export_mw=None,
            generation_by_source=generation_by_source,
            renewable_percentage=renewable_pct,
            timestamp=datetime.now(UTC),
            data_source="SMARD",
        )

    async def get_consumption(self) -> float | None:
        """Get total consumption for Germany (MW)."""
        data = await self._request(410)
        if not data:
            return None

        series = data.get("series", [])
        if series:
            for entry in reversed(series):
                if entry[1] is not None:
                    return entry[1]
        return None

    async def get_day_ahead_price(self) -> DayAheadPrice | None:
        """Get day-ahead price for Germany."""
        data = await self._request(4169)
        if not data:
            return None

        series = data.get("series", [])
        if series:
            for entry in reversed(series):
                if entry[1] is not None:
                    return DayAheadPrice(
                        price=entry[1],
                        currency="EUR",
                        price_area="DE",
                        timestamp=datetime.fromtimestamp(entry[0] / 1000, tz=UTC),
                        unit="EUR/MWh",
                        data_source="SMARD",
                    )
        return None


# ============================================================================
# EASTERN EUROPE
# ============================================================================


class PSEClient:
    """Client for PSE Raporty API (Poland).
    
    API Documentation: https://raporty.pse.pl/
    Free, no authentication required.
    
    Provides: Load, generation, cross-border flows, frequency, prices.
    """

    def __init__(self, session: aiohttp.ClientSession):
        """Initialize the client."""
        self._session = session
        self._base_url = "https://api.raporty.pse.pl/api"

    async def _request(self, endpoint: str) -> dict | None:
        """Make API request to PSE."""
        url = f"{self._base_url}/{endpoint}"

        try:
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                _LOGGER.warning("PSE API returned %d for %s", resp.status, endpoint)
                return None
        except Exception as e:
            _LOGGER.error("PSE API error: %s", e)
            return None

    async def get_current_data(self) -> dict | None:
        """Get current system data for Poland."""
        data = await self._request("dane-systemowe")
        if not data:
            return None

        # Return latest entry
        if isinstance(data, list) and len(data) > 0:
            return data[-1]
        return data

    async def get_generation(self) -> ZonePowerBreakdown | None:
        """Get current generation breakdown for Poland."""
        data = await self.get_current_data()
        if not data:
            return None

        generation_by_source = {
            "thermal": data.get("generation_thermal", 0),
            "hydro": data.get("generation_hydro", 0),
            "wind": data.get("generation_wind", 0),
            "solar": data.get("generation_pv", 0),
        }

        total = sum(v for v in generation_by_source.values() if v)
        renewable_mw = (
            generation_by_source.get("hydro", 0) +
            generation_by_source.get("wind", 0) +
            generation_by_source.get("solar", 0)
        )
        renewable_pct = (renewable_mw / total * 100) if total > 0 else None

        return ZonePowerBreakdown(
            zone="PL",
            zone_name="Poland",
            power_consumption_mw=data.get("demand"),
            power_production_mw=total,
            power_import_mw=data.get("import"),
            power_export_mw=data.get("export"),
            generation_by_source=generation_by_source,
            renewable_percentage=renewable_pct,
            timestamp=datetime.now(UTC),
            data_source="PSE",
        )

    async def get_frequency(self) -> GridFrequency | None:
        """Get current grid frequency for Poland."""
        data = await self.get_current_data()
        if not data:
            return None

        freq = data.get("frequency", 50.0)
        deviation = freq - 50.0
        status = "normal" if abs(deviation) < 0.1 else ("high" if deviation > 0 else "low")

        return GridFrequency(
            frequency_hz=freq,
            timestamp=datetime.now(UTC),
            target_hz=50.0,
            deviation_hz=deviation,
            status=status,
            data_source="PSE",
        )

    async def get_cross_border_flows(self) -> dict | None:
        """Get cross-border flows for Poland."""
        data = await self.get_current_data()
        if not data:
            return None

        return {
            "germany": data.get("flow_de", 0),
            "czech_republic": data.get("flow_cz", 0),
            "slovakia": data.get("flow_sk", 0),
            "lithuania": data.get("flow_lt", 0),
            "ukraine": data.get("flow_ua", 0),
            "sweden": data.get("flow_se", 0),
            "net_import": data.get("import", 0) - data.get("export", 0),
        }


# ============================================================================
# SOUTHERN EUROPE
# ============================================================================


class TernaClient:
    """Client for Terna API (Italy).
    
    Documentation: https://dati.terna.it/
    Free, limited authentication.
    
    Provides: Demand, generation by source, RES percentage.
    """

    def __init__(self, session: aiohttp.ClientSession):
        """Initialize the client."""
        self._session = session
        self._base_url = "https://api.terna.it/pti-api/v1"

    async def _request(self, endpoint: str) -> dict | None:
        """Make API request to Terna."""
        url = f"{self._base_url}/{endpoint}"

        try:
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                _LOGGER.warning("Terna API returned %d for %s", resp.status, endpoint)
                return None
        except Exception as e:
            _LOGGER.error("Terna API error: %s", e)
            return None

    async def get_real_time_demand(self) -> float | None:
        """Get real-time electricity demand for Italy (MW)."""
        data = await self._request("real-time-demand")
        if data and isinstance(data, list) and len(data) > 0:
            return data[-1].get("value")
        return None

    async def get_generation_by_source(self) -> ZonePowerBreakdown | None:
        """Get generation by source for Italy."""
        data = await self._request("generation-by-source")
        if not data:
            return None

        generation_by_source = {}
        total = 0
        renewable_mw = 0

        if isinstance(data, list):
            for entry in data:
                source = entry.get("source", "unknown").lower()
                value = entry.get("value", 0)
                generation_by_source[source] = value
                total += value

                if source in ["hydro", "solar", "wind", "geothermal", "biomass"]:
                    renewable_mw += value

        renewable_pct = (renewable_mw / total * 100) if total > 0 else None

        return ZonePowerBreakdown(
            zone="IT",
            zone_name="Italy",
            power_consumption_mw=await self.get_real_time_demand(),
            power_production_mw=total,
            power_import_mw=None,
            power_export_mw=None,
            generation_by_source=generation_by_source,
            renewable_percentage=renewable_pct,
            timestamp=datetime.now(UTC),
            data_source="Terna",
        )


# ============================================================================
# AMERICAS
# ============================================================================


class IESOClient:
    """Client for IESO API (Ontario, Canada).
    
    Documentation: https://www.ieso.ca/en/Power-Data
    Free, no authentication required.
    
    Provides: Demand, generation by fuel type, prices.
    """

    def __init__(self, session: aiohttp.ClientSession):
        """Initialize the client."""
        self._session = session
        self._base_url = "https://www.ieso.ca"

    async def _request(self, report_name: str) -> str | None:
        """Make API request to IESO (returns XML)."""
        url = f"{self._base_url}/publicreports/{report_name}"

        try:
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
                _LOGGER.warning("IESO API returned %d for %s", resp.status, report_name)
                return None
        except Exception as e:
            _LOGGER.error("IESO API error: %s", e)
            return None

    async def get_generation_output(self) -> ZonePowerBreakdown | None:
        """Get current generation output by fuel type for Ontario."""
        xml_data = await self._request("GenOutputCapability.xml")
        if not xml_data:
            return None

        try:
            # Parse XML
            root = ET.fromstring(xml_data)
            ns = {"ns": "http://www.ieso.ca/schema/IMO/PDP/Report/GenOutputCapability"}

            generation_by_source = {}
            total = 0
            renewable_mw = 0

            fuel_types = root.findall(".//ns:FuelType", ns)
            for fuel_type in fuel_types:
                fuel = fuel_type.find("ns:Fuel", ns)
                output = fuel_type.find("ns:Output", ns)

                if fuel is not None and output is not None:
                    fuel_name = fuel.text.lower() if fuel.text else "unknown"
                    output_mw = float(output.text) if output.text else 0

                    generation_by_source[fuel_name] = output_mw
                    total += output_mw

                    if fuel_name in ["hydro", "solar", "wind", "biofuel"]:
                        renewable_mw += output_mw

            renewable_pct = (renewable_mw / total * 100) if total > 0 else None

            return ZonePowerBreakdown(
                zone="CA-ON",
                zone_name="Ontario, Canada",
                power_consumption_mw=None,
                power_production_mw=total,
                power_import_mw=None,
                power_export_mw=None,
                generation_by_source=generation_by_source,
                renewable_percentage=renewable_pct,
                timestamp=datetime.now(UTC),
                data_source="IESO",
            )
        except Exception as e:
            _LOGGER.error("Error parsing IESO data: %s", e)
            return None

    async def get_demand(self) -> float | None:
        """Get current Ontario demand (MW)."""
        xml_data = await self._request("Demand.xml")
        if not xml_data:
            return None

        try:
            root = ET.fromstring(xml_data)
            # Find latest demand value
            demand_elem = root.find(".//Demand")
            if demand_elem is not None and demand_elem.text:
                return float(demand_elem.text)
            return None
        except Exception as e:
            _LOGGER.error("Error parsing IESO demand: %s", e)
            return None


class AESOClient:
    """Client for AESO API (Alberta, Canada).
    
    Documentation: https://www.aeso.ca/
    Free API key required.
    
    Provides: Pool price, supply/demand, wind/solar forecasts.
    """

    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        """Initialize the client.
        
        Args:
            session: aiohttp client session
            api_key: AESO API key (free registration)
        """
        self._session = session
        self._api_key = api_key
        self._base_url = "https://api.aeso.ca"

    async def _request(self, endpoint: str) -> dict | None:
        """Make API request to AESO."""
        url = f"{self._base_url}/{endpoint}"
        headers = {"API-Key": self._api_key}

        try:
            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                _LOGGER.warning("AESO API returned %d for %s", resp.status, endpoint)
                return None
        except Exception as e:
            _LOGGER.error("AESO API error: %s", e)
            return None

    async def get_pool_price(self) -> DayAheadPrice | None:
        """Get current Alberta pool price."""
        data = await self._request("report/v1/poolPrice/current")
        if not data or not data.get("return"):
            return None

        pool_data = data["return"]
        if isinstance(pool_data, list) and len(pool_data) > 0:
            pool_data = pool_data[0]

        return DayAheadPrice(
            price=pool_data.get("pool_price", 0),
            currency="CAD",
            price_area="AB",
            timestamp=datetime.now(UTC),
            unit="CAD/MWh",
            data_source="AESO",
        )

    async def get_current_supply_demand(self) -> dict | None:
        """Get current supply and demand for Alberta."""
        data = await self._request("report/v1/csd/summary/current")
        if not data or not data.get("return"):
            return None

        return data["return"]

    async def get_generation(self) -> ZonePowerBreakdown | None:
        """Get generation breakdown for Alberta."""
        data = await self.get_current_supply_demand()
        if not data:
            return None

        generation_by_source = {}
        total = 0
        renewable_mw = 0

        # Parse fuel types from summary
        if isinstance(data, dict):
            for key, value in data.items():
                if key.endswith("_mw") and value:
                    fuel = key.replace("_mw", "")
                    generation_by_source[fuel] = value
                    total += value

                    if fuel in ["wind", "solar", "hydro"]:
                        renewable_mw += value

        renewable_pct = (renewable_mw / total * 100) if total > 0 else None

        return ZonePowerBreakdown(
            zone="CA-AB",
            zone_name="Alberta, Canada",
            power_consumption_mw=data.get("alberta_internal_load"),
            power_production_mw=total,
            power_import_mw=data.get("net_import"),
            power_export_mw=None,
            generation_by_source=generation_by_source,
            renewable_percentage=renewable_pct,
            timestamp=datetime.now(UTC),
            data_source="AESO",
        )


# ============================================================================
# ASIA-PACIFIC
# ============================================================================


class TranspowerClient:
    """Client for New Zealand Electricity Market Information (EMI).
    
    Documentation: https://www.emi.ea.govt.nz/ and https://forum.emi.ea.govt.nz/
    Free, no authentication required.
    
    Data Sources:
    - EMI Azure Blob Storage: https://emidatasets.blob.core.windows.net/publicdata
    - Generation, demand, prices, and more available via CSV files
    
    Note: Real-time data shown at https://www.transpower.co.nz/power-system-live-data
    is sourced from EM6 (https://app.em6.co.nz) which requires account access.
    This client uses EMI public datasets which update daily/periodically.
    
    Provides: Generation by fuel type, demand, prices.
    """

    def __init__(self, session: aiohttp.ClientSession):
        """Initialize the client."""
        self._session = session
        self._blob_url = "https://emidatasets.blob.core.windows.net/publicdata"
        self._cache: dict = {}
        self._cache_time: datetime | None = None
        self._cache_ttl = timedelta(hours=1)  # Cache for 1 hour as data is not real-time

    async def _get_latest_generation_file(self) -> str | None:
        """Get URL of the latest generation file."""
        # EMI publishes monthly generation files
        today = datetime.now()
        year = today.year
        month = today.month

        # Try current month first, then previous month
        for m in [month, month - 1 if month > 1 else 12]:
            y = year if m <= month else year - 1
            filename = f"{y}{m:02d}_Generation_MD.csv"
            url = f"{self._blob_url}/Datasets/Wholesale/Generation/Generation_MD/{y}/{filename}"

            try:
                async with self._session.head(url) as resp:
                    if resp.status == 200:
                        return url
            except Exception:
                continue

        return None

    async def _parse_generation_csv(self, url: str) -> dict | None:
        """Parse generation CSV file and return latest data."""
        try:
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    return None

                content = await resp.text()
                lines = content.strip().split("\n")
                if len(lines) < 2:
                    return None

                # Parse header
                headers = lines[0].split(",")

                # Get the last few rows (most recent data)
                generation_by_fuel = {}
                total_gen = 0
                renewable_gen = 0

                # Process last row
                last_row = lines[-1].split(",")

                # Try to find fuel type and generation columns
                fuel_idx = None
                for i, h in enumerate(headers):
                    h_lower = h.lower().strip('"')
                    if "fuel" in h_lower or "type" in h_lower:
                        fuel_idx = i

                # If we can't find the structure, aggregate by fuel type
                if fuel_idx is None:
                    # Alternative: scan the file structure for fuel-specific columns
                    for i, h in enumerate(headers):
                        h_lower = h.lower().strip('"')
                        if h_lower in ["hydro", "wind", "solar", "geothermal", "gas", "coal", "diesel", "battery"]:
                            try:
                                val = float(last_row[i].strip('"'))
                                generation_by_fuel[h_lower] = val
                                total_gen += val
                                if h_lower in ["hydro", "wind", "solar", "geothermal"]:
                                    renewable_gen += val
                            except (ValueError, IndexError):
                                pass

                return {
                    "generation_by_fuel": generation_by_fuel,
                    "total_generation_mw": total_gen,
                    "renewable_generation_mw": renewable_gen,
                    "renewable_percentage": (renewable_gen / total_gen * 100) if total_gen > 0 else None,
                }
        except Exception as e:
            _LOGGER.error("Error parsing NZ generation CSV: %s", e)
            return None

    async def get_power_data(self) -> ZonePowerBreakdown | None:
        """Get current power data for New Zealand.
        
        Note: EMI data is not real-time. For real-time data, EM6 subscription is required.
        This provides the most recent available data from EMI public datasets.
        """
        # Check cache
        if self._cache and self._cache_time and datetime.now() - self._cache_time < self._cache_ttl:
            return self._cache.get("power_data")

        gen_url = await self._get_latest_generation_file()
        if not gen_url:
            _LOGGER.warning("Could not find NZ generation file")
            return None

        gen_data = await self._parse_generation_csv(gen_url)
        if not gen_data:
            return None

        result = ZonePowerBreakdown(
            zone="NZ",
            zone_name="New Zealand",
            power_consumption_mw=None,  # Demand in separate dataset
            power_production_mw=gen_data.get("total_generation_mw"),
            power_import_mw=None,
            power_export_mw=None,
            generation_by_source=gen_data.get("generation_by_fuel", {}),
            renewable_percentage=gen_data.get("renewable_percentage"),
            timestamp=datetime.now(UTC),
            data_source="EMI New Zealand",
        )

        # Cache result
        self._cache["power_data"] = result
        self._cache_time = datetime.now()

        return result

    async def get_generation_summary(self) -> dict | None:
        """Get generation summary for New Zealand."""
        power_data = await self.get_power_data()
        if not power_data:
            return None

        return {
            "total_mw": power_data.power_production_mw,
            "generation_by_source": power_data.generation_by_source,
            "renewable_percentage": power_data.renewable_percentage,
            "data_source": power_data.data_source,
            "note": "Data from EMI public datasets (not real-time). For real-time data, see app.em6.co.nz",
        }

    async def get_hvdc_transfer(self) -> dict | None:
        """Get HVDC link transfer between North and South Island.
        
        Note: Real-time HVDC data requires EM6 access.
        """
        return {
            "hvdc_transfer_mw": None,
            "direction": None,
            "note": "Real-time HVDC data requires EM6 subscription. See app.em6.co.nz",
        }


# ============================================================================
# GLOBAL / MULTI-REGION
# ============================================================================


class WattTimeClient:
    """Client for WattTime API (Global marginal emissions).
    
    Documentation: https://docs.watttime.org/
    Free tier available with registration.
    
    Provides: Marginal emissions, average emissions, health damage signals.
    """

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        """Initialize the client.
        
        Args:
            session: aiohttp client session
            username: WattTime username
            password: WattTime password
        """
        self._session = session
        self._username = username
        self._password = password
        self._base_url = "https://api.watttime.org/v3"
        self._token: str | None = None
        self._token_expiry: datetime | None = None

    async def _get_token(self) -> str | None:
        """Get authentication token."""
        if self._token and self._token_expiry and datetime.now(UTC) < self._token_expiry:
            return self._token

        url = f"{self._base_url}/login"
        auth = aiohttp.BasicAuth(self._username, self._password)

        try:
            async with self._session.get(url, auth=auth) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._token = data.get("token")
                    # Token typically valid for 30 minutes
                    self._token_expiry = datetime.now(UTC) + timedelta(minutes=25)
                    return self._token
                _LOGGER.warning("WattTime login returned %d", resp.status)
                return None
        except Exception as e:
            _LOGGER.error("WattTime login error: %s", e)
            return None

    async def _request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make authenticated API request to WattTime."""
        token = await self._get_token()
        if not token:
            return None

        url = f"{self._base_url}/{endpoint}"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with self._session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                _LOGGER.warning("WattTime API returned %d for %s", resp.status, endpoint)
                return None
        except Exception as e:
            _LOGGER.error("WattTime API error: %s", e)
            return None

    async def get_region_from_location(self, latitude: float, longitude: float) -> str | None:
        """Get WattTime region/ba from coordinates."""
        data = await self._request("region-from-loc", {"latitude": latitude, "longitude": longitude})
        if data:
            return data.get("region")
        return None

    async def get_index(self, region: str) -> ZoneCarbonIntensity | None:
        """Get real-time emissions index for a region.
        
        Args:
            region: WattTime region/balancing authority code
        """
        data = await self._request("signal-index", {"region": region})
        if not data:
            return None

        return ZoneCarbonIntensity(
            zone=region,
            zone_name=data.get("region_full_name", region),
            carbon_intensity=int(data.get("value", 0)),  # WattTime uses 0-100 index
            fossil_fuel_percentage=None,
            timestamp=datetime.fromisoformat(data.get("point_time", "").replace("Z", "+00:00")),
            data_source="WattTime",
        )

    async def get_marginal_emissions(self, region: str) -> dict | None:
        """Get marginal emissions data.
        
        Args:
            region: WattTime region code
        """
        data = await self._request("signal-index", {"region": region, "signal_type": "co2_moer"})
        if not data:
            return None

        return {
            "region": region,
            "moer": data.get("value"),  # Marginal Operating Emissions Rate
            "units": "lbs CO2/MWh",
            "timestamp": data.get("point_time"),
        }

    async def get_health_damage(self, region: str) -> dict | None:
        """Get health damage signal for a region.
        
        Args:
            region: WattTime region code
        """
        data = await self._request("signal-index", {"region": region, "signal_type": "health_damage"})
        if not data:
            return None

        return {
            "region": region,
            "health_damage_index": data.get("value"),
            "timestamp": data.get("point_time"),
        }
