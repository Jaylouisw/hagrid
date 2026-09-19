"""Sensors for HAGrid integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FUEL_COLORS, INTENSITY_COLORS
from .coordinator import HAGridCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HAGrid sensors."""
    coordinator: HAGridCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        HAGridCarbonIntensitySensor(coordinator, entry),
        HAGridCarbonIndexSensor(coordinator, entry),
        HAGridGenerationMixSensor(coordinator, entry),
        HAGridLiveFaultsSensor(coordinator, entry),
        HAGridMapDataSensor(coordinator, entry),
        HAGridForecastSensor(coordinator, entry),
        # New granular metered circuit sensors
        HAGridSystemFrequencySensor(coordinator, entry),
        HAGridNationalDemandSensor(coordinator, entry),
        HAGridTotalGenerationSensor(coordinator, entry),
        HAGridNetImportsSensor(coordinator, entry),
        HAGridCircuitFlowsSensor(coordinator, entry),
        HAGridInterconnectorsSensor(coordinator, entry),
    ]
    
    # Add individual fuel sensors
    if coordinator.generation_mix:
        for fuel in coordinator.generation_mix:
            entities.append(
                HAGridFuelSensor(coordinator, entry, fuel["fuel"])
            )
    
    async_add_entities(entities)


class HAGridBaseSensor(CoordinatorEntity[HAGridCoordinator], SensorEntity):
    """Base sensor for HAGrid."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"HAGrid - {coordinator.region_name or 'UK Grid'}",
            "manufacturer": "HAGrid",
            "model": coordinator.dno_name or "UK Power Grid",
        }


class HAGridCarbonIntensitySensor(HAGridBaseSensor):
    """Carbon intensity sensor."""
    
    _attr_name = "Carbon Intensity"
    _attr_native_unit_of_measurement = "gCO2/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:molecule-co2"
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_carbon_intensity"
    
    @property
    def native_value(self) -> int | None:
        """Return the carbon intensity."""
        return self.coordinator.carbon_intensity
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        attrs = {
            "region": self.coordinator.region_name,
            "dno": self.coordinator.dno_name,
        }
        if self.coordinator.data and self.coordinator.data.get("regional_data"):
            rd = self.coordinator.data["regional_data"]
            attrs["actual"] = rd.intensity.actual
            attrs["index"] = rd.intensity.index
        return attrs


class HAGridCarbonIndexSensor(HAGridBaseSensor):
    """Carbon intensity index sensor."""
    
    _attr_name = "Carbon Index"
    _attr_icon = "mdi:leaf"
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_carbon_index"
    
    @property
    def native_value(self) -> str | None:
        """Return the carbon index."""
        return self.coordinator.carbon_index
    
    @property
    def icon(self) -> str:
        """Return dynamic icon based on index."""
        index = self.coordinator.carbon_index
        if index in ["very low", "low"]:
            return "mdi:leaf"
        elif index == "moderate":
            return "mdi:leaf-off"
        else:
            return "mdi:alert"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        index = self.coordinator.carbon_index
        return {
            "color": INTENSITY_COLORS.get(index, "#95A5A6"),
        }


class HAGridGenerationMixSensor(HAGridBaseSensor):
    """Generation mix sensor."""
    
    _attr_name = "Generation Mix"
    _attr_icon = "mdi:chart-pie"
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_generation_mix"
    
    @property
    def native_value(self) -> str | None:
        """Return the dominant fuel type."""
        mix = self.coordinator.generation_mix
        if mix:
            # Find the dominant fuel
            dominant = max(mix, key=lambda x: x["percentage"])
            return dominant["fuel"]
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the full generation mix."""
        mix = self.coordinator.generation_mix
        if not mix:
            return {}
        
        attrs = {
            "mix": mix,
            "renewable_percentage": sum(
                f["percentage"] for f in mix
                if f["fuel"] in ["wind", "solar", "hydro", "biomass"]
            ),
            "fossil_percentage": sum(
                f["percentage"] for f in mix
                if f["fuel"] in ["gas", "coal", "oil"]
            ),
            "low_carbon_percentage": sum(
                f["percentage"] for f in mix
                if f["fuel"] in ["wind", "solar", "hydro", "nuclear", "biomass"]
            ),
        }
        
        # Add individual fuel percentages
        for fuel in mix:
            attrs[f"{fuel['fuel']}_percentage"] = fuel["percentage"]
        
        return attrs


class HAGridFuelSensor(HAGridBaseSensor):
    """Individual fuel type sensor."""
    
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
        fuel: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._fuel = fuel
        self._attr_name = f"{fuel.title()} Generation"
        self._attr_unique_id = f"{entry.entry_id}_{fuel}_generation"
        self._attr_icon = self._get_fuel_icon()
    
    def _get_fuel_icon(self) -> str:
        """Get icon for fuel type."""
        icons = {
            "gas": "mdi:fire",
            "coal": "mdi:factory",
            "nuclear": "mdi:atom",
            "wind": "mdi:wind-turbine",
            "solar": "mdi:solar-power",
            "hydro": "mdi:hydro-power",
            "biomass": "mdi:leaf",
            "imports": "mdi:transmission-tower-import",
            "storage": "mdi:battery-charging",
            "other": "mdi:power-plug",
        }
        return icons.get(self._fuel, "mdi:power-plug")
    
    @property
    def native_value(self) -> float | None:
        """Return the percentage for this fuel."""
        mix = self.coordinator.generation_mix
        if mix:
            for fuel in mix:
                if fuel["fuel"] == self._fuel:
                    return fuel["percentage"]
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return {
            "color": FUEL_COLORS.get(self._fuel, "#95A5A6"),
        }


class HAGridLiveFaultsSensor(HAGridBaseSensor):
    """Live faults sensor."""
    
    _attr_name = "Live Faults"
    _attr_icon = "mdi:alert-circle"
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_live_faults"
    
    @property
    def native_value(self) -> int:
        """Return the number of live faults."""
        return self.coordinator.live_fault_count
    
    @property
    def icon(self) -> str:
        """Return dynamic icon."""
        if self.coordinator.live_fault_count > 0:
            return "mdi:alert-circle"
        return "mdi:check-circle"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return fault details."""
        if not self.coordinator.data:
            return {}
        
        faults = self.coordinator.data.get("live_faults", [])
        
        # Group by type
        planned = sum(1 for f in faults if f.incident_type == "planned")
        unplanned = sum(1 for f in faults if f.incident_type == "unplanned")
        
        # Total affected customers
        total_customers = sum(f.estimated_customers for f in faults)
        
        return {
            "planned_outages": planned,
            "unplanned_outages": unplanned,
            "affected_customers": total_customers,
            "faults": [
                {
                    "id": f.id,
                    "type": f.incident_type,
                    "postcode": f.postcode_area,
                    "customers": f.estimated_customers,
                }
                for f in faults[:10]  # Limit to first 10
            ],
        }


class HAGridMapDataSensor(HAGridBaseSensor):
    """Map data sensor for Lovelace card."""
    
    _attr_name = "Grid Map"
    _attr_icon = "mdi:map"
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_map_data"
    
    @property
    def native_value(self) -> str:
        """Return a simple state."""
        return self.coordinator.region_name or "UK Grid"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the full map data."""
        return self.coordinator.map_data


class HAGridForecastSensor(HAGridBaseSensor):
    """Carbon intensity forecast sensor."""
    
    _attr_name = "Carbon Forecast"
    _attr_icon = "mdi:chart-line"
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_carbon_forecast"
    
    @property
    def native_value(self) -> str | None:
        """Return the trend direction."""
        if not self.coordinator.data:
            return None
        
        forecast = self.coordinator.data.get("forecast", [])
        if len(forecast) < 2:
            return "stable"
        
        current = forecast[0].forecast if forecast else 0
        future = forecast[-1].forecast if forecast else 0
        
        if future < current * 0.9:
            return "decreasing"
        elif future > current * 1.1:
            return "increasing"
        return "stable"
    
    @property
    def icon(self) -> str:
        """Return dynamic icon based on trend."""
        value = self.native_value
        if value == "decreasing":
            return "mdi:trending-down"
        elif value == "increasing":
            return "mdi:trending-up"
        return "mdi:trending-neutral"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the forecast data."""
        if not self.coordinator.data:
            return {}
        
        forecast = self.coordinator.data.get("forecast", [])
        
        # Find best time to use energy (lowest intensity)
        if forecast:
            best = min(forecast, key=lambda x: x.forecast)
            worst = max(forecast, key=lambda x: x.forecast)
            
            return {
                "forecast": [
                    {
                        "from": f.from_time.isoformat(),
                        "to": f.to_time.isoformat(),
                        "intensity": f.forecast,
                        "index": f.index,
                    }
                    for f in forecast
                ],
                "best_time": best.from_time.isoformat(),
                "best_intensity": best.forecast,
                "worst_time": worst.from_time.isoformat(),
                "worst_intensity": worst.forecast,
            }
        
        return {}


class HAGridSystemFrequencySensor(HAGridBaseSensor):
    """System frequency sensor - real-time grid frequency (target 50Hz)."""
    
    _attr_name = "System Frequency"
    _attr_native_unit_of_measurement = "Hz"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sine-wave"
    _attr_suggested_display_precision = 3
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_system_frequency"
    
    @property
    def native_value(self) -> float | None:
        """Return the current system frequency."""
        return self.coordinator.system_frequency
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        freq = self.coordinator.system_frequency
        if freq:
            # Calculate deviation from 50Hz
            deviation = freq - 50.0
            return {
                "target_hz": 50.0,
                "deviation_hz": round(deviation, 4),
                "status": "normal" if abs(deviation) < 0.2 else "deviation",
            }
        return {}


class HAGridNationalDemandSensor(HAGridBaseSensor):
    """National demand sensor - current electricity demand in MW."""
    
    _attr_name = "National Demand"
    _attr_native_unit_of_measurement = "MW"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_icon = "mdi:transmission-tower"
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_national_demand"
    
    @property
    def native_value(self) -> float | None:
        """Return the current national demand."""
        return self.coordinator.national_demand
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return demand details."""
        if not self.coordinator.data:
            return {}
        
        demand = self.coordinator.data.get("demand")
        if demand:
            return {
                "demand_type": demand.demand_type,
                "settlement_period": demand.settlement_period,
                "timestamp": demand.timestamp.isoformat(),
            }
        return {}


class HAGridTotalGenerationSensor(HAGridBaseSensor):
    """Total generation sensor - all generation sources combined."""
    
    _attr_name = "Total Generation"
    _attr_native_unit_of_measurement = "MW"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_icon = "mdi:lightning-bolt"
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_total_generation"
    
    @property
    def native_value(self) -> float | None:
        """Return total generation."""
        return self.coordinator.total_generation
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return generation breakdown by fuel type."""
        if not self.coordinator.data:
            return {}
        
        summary = self.coordinator.data.get("grid_summary", {})
        generation = summary.get("generation", {})
        
        attrs = {}
        for fuel, data in generation.items():
            key = f"{fuel.lower()}_mw"
            attrs[key] = data.get("output_mw", 0)
            attrs[f"{fuel.lower()}_pct"] = data.get("percentage")
        
        return attrs


class HAGridNetImportsSensor(HAGridBaseSensor):
    """Net imports sensor - balance of interconnector flows."""
    
    _attr_name = "Net Imports"
    _attr_native_unit_of_measurement = "MW"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:swap-horizontal"
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_net_imports"
    
    @property
    def native_value(self) -> float | None:
        """Return net imports (positive = importing, negative = exporting)."""
        return self.coordinator.net_imports
    
    @property
    def icon(self) -> str:
        """Dynamic icon based on flow direction."""
        value = self.native_value
        if value and value > 0:
            return "mdi:import"
        elif value and value < 0:
            return "mdi:export"
        return "mdi:swap-horizontal"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return import/export details."""
        if not self.coordinator.data:
            return {}
        
        summary = self.coordinator.data.get("grid_summary", {})
        return {
            "total_import_mw": summary.get("total_import_mw"),
            "total_export_mw": summary.get("total_export_mw"),
            "direction": "importing" if (summary.get("net_import_mw", 0) or 0) > 0 else "exporting",
        }


class HAGridCircuitFlowsSensor(HAGridBaseSensor):
    """Circuit flows sensor - all metered circuits with power flow data."""
    
    _attr_name = "Circuit Flows"
    _attr_icon = "mdi:chart-sankey"
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_circuit_flows"
    
    @property
    def native_value(self) -> int:
        """Return count of metered circuits."""
        return self.coordinator.circuit_flow_count
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all circuit flow data for visualization."""
        if not self.coordinator.data:
            return {}
        
        flows = self.coordinator.data.get("circuit_flows", [])
        
        # Group by type
        generation_flows = [f for f in flows if f.circuit_type == "generation"]
        interconnector_flows = [f for f in flows if f.circuit_type == "interconnector"]
        demand_flows = [f for f in flows if f.circuit_type == "demand"]
        
        return {
            "circuits": [
                {
                    "id": c.circuit_id,
                    "type": c.circuit_type,
                    "name": c.name,
                    "flow_mw": c.flow_mw,
                    "capacity_mw": c.capacity_mw,
                    "direction": c.direction,
                    "fuel_type": c.fuel_type,
                }
                for c in flows
            ],
            "generation_count": len(generation_flows),
            "interconnector_count": len(interconnector_flows),
            "demand_count": len(demand_flows),
            "total_generation_mw": sum(c.flow_mw for c in generation_flows),
            "total_interconnector_mw": sum(c.flow_mw for c in interconnector_flows),
        }


class HAGridInterconnectorsSensor(HAGridBaseSensor):
    """Interconnectors sensor - power flows to/from other countries."""
    
    _attr_name = "Interconnectors"
    _attr_icon = "mdi:earth"
    
    def __init__(
        self,
        coordinator: HAGridCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_interconnectors"
    
    @property
    def native_value(self) -> int:
        """Return count of active interconnectors."""
        if not self.coordinator.data:
            return 0
        return len(self.coordinator.data.get("interconnector_flows", []))
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all interconnector flow data."""
        if not self.coordinator.data:
            return {}
        
        flows = self.coordinator.data.get("interconnector_flows", [])
        
        interconnectors = {}
        total_import = 0
        total_export = 0
        
        for ic in flows:
            interconnectors[ic.interconnector_id] = {
                "name": ic.name,
                "country": ic.country,
                "flow_mw": ic.flow_mw,
                "capacity_mw": ic.capacity_mw,
                "utilization_pct": ic.utilization_pct,
                "direction": "import" if ic.flow_mw >= 0 else "export",
            }
            if ic.flow_mw >= 0:
                total_import += ic.flow_mw
            else:
                total_export += abs(ic.flow_mw)
        
        return {
            "interconnectors": interconnectors,
            "total_import_mw": total_import,
            "total_export_mw": total_export,
            "net_flow_mw": total_import - total_export,
            "countries": list(set(ic.country for ic in flows)),
        }
