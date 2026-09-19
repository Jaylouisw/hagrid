/**
 * HAGrid Map Card
 * Lovelace card for visualizing UK electrical grid data
 * 
 * Shows:
 * - Regional carbon intensity (color-coded map)
 * - Generation mix (pie chart)
 * - Substations and power lines
 * - Live faults
 */

const VERSION = "1.0.0";

// UK regions GeoJSON (simplified)
const UK_REGIONS = {
  1: { name: "North Scotland", center: [57.5, -4.5] },
  2: { name: "South Scotland", center: [55.9, -3.2] },
  3: { name: "North West England", center: [53.8, -2.4] },
  4: { name: "North East England", center: [54.9, -1.6] },
  5: { name: "Yorkshire", center: [53.8, -1.3] },
  6: { name: "North Wales & Merseyside", center: [53.2, -3.1] },
  7: { name: "South Wales", center: [51.7, -3.4] },
  8: { name: "West Midlands", center: [52.5, -2.0] },
  9: { name: "East Midlands", center: [52.8, -0.8] },
  10: { name: "East England", center: [52.2, 0.9] },
  11: { name: "South West England", center: [50.7, -3.5] },
  12: { name: "South England", center: [51.0, -1.0] },
  13: { name: "London", center: [51.5, -0.1] },
  14: { name: "South East England", center: [51.3, 0.5] },
  15: { name: "England", center: [52.5, -1.5] },
  16: { name: "Scotland", center: [56.5, -4.0] },
  17: { name: "Wales", center: [52.0, -3.5] },
};

// Carbon intensity color scale
const INTENSITY_COLORS = {
  "very low": "#2ECC71",
  "low": "#82E0AA",
  "moderate": "#F4D03F",
  "high": "#E67E22",
  "very high": "#E74C3C",
};

// Fuel type colors
const FUEL_COLORS = {
  gas: "#E67E22",
  coal: "#2C3E50",
  nuclear: "#9B59B6",
  wind: "#3498DB",
  solar: "#F1C40F",
  hydro: "#1ABC9C",
  biomass: "#27AE60",
  imports: "#95A5A6",
  storage: "#E91E63",
  other: "#BDC3C7",
};

class HAGridMapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._map = null;
    this._markers = [];
    this._lines = [];
    this._initialized = false;
  }

  static get properties() {
    return {
      hass: {},
      config: {},
    };
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("You need to define an entity (sensor.hagrid_grid_map)");
    }
    this.config = {
      entity: config.entity,
      title: config.title || "UK Grid Map",
      height: config.height || "400px",
      show_generation_mix: config.show_generation_mix !== false,
      show_infrastructure: config.show_infrastructure !== false,
      show_faults: config.show_faults !== false,
      show_intensity_legend: config.show_intensity_legend !== false,
      center: config.center || [54.5, -2.5],
      zoom: config.zoom || 5,
      ...config,
    };
  }

  set hass(hass) {
    this._hass = hass;
    
    if (!this._initialized) {
      this._initialize();
    } else {
      this._updateData();
    }
  }

  async _initialize() {
    // Load Leaflet if not already loaded
    if (!window.L) {
      await this._loadLeaflet();
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        .card {
          background: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,0.15));
          padding: 16px;
          font-family: var(--primary-font-family);
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .title {
          font-size: 1.2em;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        .intensity-badge {
          padding: 4px 12px;
          border-radius: 16px;
          font-size: 0.85em;
          font-weight: 500;
          color: white;
          text-transform: uppercase;
        }
        #map {
          height: ${this.config.height};
          border-radius: 8px;
          z-index: 0;
        }
        .stats-container {
          display: flex;
          gap: 16px;
          margin-top: 12px;
          flex-wrap: wrap;
        }
        .stat-card {
          flex: 1;
          min-width: 120px;
          background: var(--secondary-background-color);
          border-radius: 8px;
          padding: 12px;
        }
        .stat-label {
          font-size: 0.75em;
          color: var(--secondary-text-color);
          text-transform: uppercase;
        }
        .stat-value {
          font-size: 1.5em;
          font-weight: 600;
          color: var(--primary-text-color);
        }
        .stat-unit {
          font-size: 0.75em;
          color: var(--secondary-text-color);
        }
        .generation-mix {
          margin-top: 16px;
        }
        .mix-title {
          font-size: 0.9em;
          font-weight: 500;
          margin-bottom: 8px;
          color: var(--primary-text-color);
        }
        .mix-bar {
          display: flex;
          height: 24px;
          border-radius: 12px;
          overflow: hidden;
        }
        .mix-segment {
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-size: 0.7em;
          font-weight: 500;
          transition: flex 0.3s ease;
        }
        .mix-legend {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 8px;
        }
        .legend-item {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 0.75em;
          color: var(--secondary-text-color);
        }
        .legend-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
        }
        .intensity-legend {
          display: flex;
          gap: 8px;
          margin-top: 12px;
          justify-content: center;
        }
        .intensity-item {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 0.7em;
        }
        .intensity-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
        }
        .faults-banner {
          background: #E74C3C;
          color: white;
          padding: 8px 12px;
          border-radius: 8px;
          margin-bottom: 12px;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .faults-banner.no-faults {
          background: #2ECC71;
        }
        .forecast-container {
          margin-top: 16px;
        }
        .forecast-title {
          font-size: 0.9em;
          font-weight: 500;
          margin-bottom: 8px;
        }
        .forecast-chart {
          display: flex;
          height: 60px;
          align-items: flex-end;
          gap: 2px;
        }
        .forecast-bar {
          flex: 1;
          border-radius: 2px 2px 0 0;
          min-width: 4px;
          transition: height 0.3s ease;
        }
        .best-time {
          margin-top: 8px;
          padding: 8px;
          background: #2ECC71;
          color: white;
          border-radius: 6px;
          font-size: 0.85em;
        }

        /* Leaflet overrides */
        .leaflet-container {
          font-family: inherit;
        }
        .custom-marker {
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .substation-marker {
          width: 12px;
          height: 12px;
          background: #9B59B6;
          border: 2px solid white;
          border-radius: 50%;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .fault-marker {
          width: 20px;
          height: 20px;
          background: #E74C3C;
          border: 2px solid white;
          border-radius: 50%;
          animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
          0% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.2); opacity: 0.8; }
          100% { transform: scale(1); opacity: 1; }
        }
      </style>
      
      <div class="card">
        <div class="header">
          <span class="title">${this.config.title}</span>
          <span class="intensity-badge" id="intensity-badge">Loading...</span>
        </div>
        
        <div id="faults-banner" class="faults-banner no-faults" style="display: none;">
          <span>⚡</span>
          <span id="faults-text"></span>
        </div>
        
        <div id="map"></div>
        
        <div class="stats-container">
          <div class="stat-card">
            <div class="stat-label">Carbon Intensity</div>
            <div class="stat-value" id="carbon-value">--</div>
            <div class="stat-unit">gCO2/kWh</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Renewable</div>
            <div class="stat-value" id="renewable-value">--</div>
            <div class="stat-unit">%</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Low Carbon</div>
            <div class="stat-value" id="lowcarbon-value">--</div>
            <div class="stat-unit">%</div>
          </div>
        </div>
        
        ${this.config.show_generation_mix ? `
          <div class="generation-mix">
            <div class="mix-title">Generation Mix</div>
            <div class="mix-bar" id="mix-bar"></div>
            <div class="mix-legend" id="mix-legend"></div>
          </div>
        ` : ''}
        
        ${this.config.show_intensity_legend ? `
          <div class="intensity-legend">
            <div class="intensity-item"><span class="intensity-dot" style="background: ${INTENSITY_COLORS['very low']}"></span>Very Low</div>
            <div class="intensity-item"><span class="intensity-dot" style="background: ${INTENSITY_COLORS['low']}"></span>Low</div>
            <div class="intensity-item"><span class="intensity-dot" style="background: ${INTENSITY_COLORS['moderate']}"></span>Moderate</div>
            <div class="intensity-item"><span class="intensity-dot" style="background: ${INTENSITY_COLORS['high']}"></span>High</div>
            <div class="intensity-item"><span class="intensity-dot" style="background: ${INTENSITY_COLORS['very high']}"></span>Very High</div>
          </div>
        ` : ''}
        
        <div class="forecast-container" id="forecast-container" style="display: none;">
          <div class="forecast-title">48hr Carbon Forecast</div>
          <div class="forecast-chart" id="forecast-chart"></div>
          <div class="best-time" id="best-time"></div>
        </div>
      </div>
    `;

    // Initialize map after DOM is ready
    await this._initMap();
    this._initialized = true;
    this._updateData();
  }

  async _loadLeaflet() {
    // Load Leaflet CSS
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);

    // Load Leaflet JS
    return new Promise((resolve, reject) => {
      if (window.L) {
        resolve();
        return;
      }
      const script = document.createElement("script");
      script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  async _initMap() {
    await new Promise(resolve => setTimeout(resolve, 100)); // Wait for DOM
    
    const mapEl = this.shadowRoot.getElementById("map");
    if (!mapEl || !window.L) return;

    this._map = L.map(mapEl, {
      center: this.config.center,
      zoom: this.config.zoom,
      zoomControl: true,
      attributionControl: true,
    });

    // Add tile layer
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(this._map);

    // Force resize
    setTimeout(() => this._map.invalidateSize(), 200);
  }

  _updateData() {
    if (!this._hass || !this.config.entity) return;

    const entity = this._hass.states[this.config.entity];
    if (!entity) return;

    const attrs = entity.attributes || {};
    
    // Update carbon intensity
    this._updateIntensity(attrs);
    
    // Update generation mix
    if (this.config.show_generation_mix) {
      this._updateGenerationMix(attrs.generation_mix);
    }
    
    // Update faults banner
    this._updateFaultsBanner(attrs.live_faults);
    
    // Update infrastructure on map
    if (this.config.show_infrastructure && this._map) {
      this._updateMapInfrastructure(attrs);
    }
    
    // Update forecast
    this._updateForecast(attrs.forecast);
  }

  _updateIntensity(attrs) {
    const badge = this.shadowRoot.getElementById("intensity-badge");
    const carbonValue = this.shadowRoot.getElementById("carbon-value");
    const renewableValue = this.shadowRoot.getElementById("renewable-value");
    const lowcarbonValue = this.shadowRoot.getElementById("lowcarbon-value");
    
    const index = attrs.carbon_index || "moderate";
    const intensity = attrs.carbon_intensity || "--";
    
    if (badge) {
      badge.textContent = index;
      badge.style.background = INTENSITY_COLORS[index] || INTENSITY_COLORS.moderate;
    }
    
    if (carbonValue) {
      carbonValue.textContent = intensity;
    }
    
    if (renewableValue && attrs.generation_mix) {
      const renewable = this._calculateRenewable(attrs.generation_mix);
      renewableValue.textContent = renewable.toFixed(1);
    }
    
    if (lowcarbonValue && attrs.generation_mix) {
      const lowCarbon = this._calculateLowCarbon(attrs.generation_mix);
      lowcarbonValue.textContent = lowCarbon.toFixed(1);
    }
  }

  _calculateRenewable(mix) {
    const renewables = ["wind", "solar", "hydro"];
    return mix
      .filter(f => renewables.includes(f.fuel))
      .reduce((sum, f) => sum + f.percentage, 0);
  }

  _calculateLowCarbon(mix) {
    const lowCarbon = ["wind", "solar", "hydro", "nuclear", "biomass"];
    return mix
      .filter(f => lowCarbon.includes(f.fuel))
      .reduce((sum, f) => sum + f.percentage, 0);
  }

  _updateGenerationMix(mix) {
    if (!mix || !mix.length) return;
    
    const bar = this.shadowRoot.getElementById("mix-bar");
    const legend = this.shadowRoot.getElementById("mix-legend");
    
    if (!bar || !legend) return;
    
    // Sort by percentage descending
    const sorted = [...mix].sort((a, b) => b.percentage - a.percentage);
    
    // Build bar
    bar.innerHTML = sorted
      .filter(f => f.percentage > 0)
      .map(f => `
        <div class="mix-segment" 
             style="flex: ${f.percentage}; background: ${FUEL_COLORS[f.fuel] || FUEL_COLORS.other}"
             title="${f.fuel}: ${f.percentage.toFixed(1)}%">
          ${f.percentage > 8 ? `${f.percentage.toFixed(0)}%` : ''}
        </div>
      `).join("");
    
    // Build legend
    legend.innerHTML = sorted
      .filter(f => f.percentage > 0)
      .map(f => `
        <div class="legend-item">
          <span class="legend-dot" style="background: ${FUEL_COLORS[f.fuel] || FUEL_COLORS.other}"></span>
          ${f.fuel.charAt(0).toUpperCase() + f.fuel.slice(1)} ${f.percentage.toFixed(1)}%
        </div>
      `).join("");
  }

  _updateFaultsBanner(faults) {
    const banner = this.shadowRoot.getElementById("faults-banner");
    const text = this.shadowRoot.getElementById("faults-text");
    
    if (!banner || !text) return;
    
    if (!faults || faults.length === 0) {
      banner.style.display = "none";
      return;
    }
    
    banner.style.display = "flex";
    banner.classList.remove("no-faults");
    
    const planned = faults.filter(f => f.type === "planned").length;
    const unplanned = faults.filter(f => f.type === "unplanned").length;
    const customers = faults.reduce((sum, f) => sum + (f.customers || 0), 0);
    
    text.textContent = `${faults.length} active fault${faults.length > 1 ? 's' : ''} (${unplanned} unplanned, ${planned} planned) - ${customers.toLocaleString()} customers affected`;
  }

  _updateMapInfrastructure(attrs) {
    if (!this._map) return;
    
    // Clear existing markers
    this._markers.forEach(m => this._map.removeLayer(m));
    this._markers = [];
    this._lines.forEach(l => this._map.removeLayer(l));
    this._lines = [];
    
    // Add substations
    if (attrs.substations) {
      attrs.substations.forEach(sub => {
        if (sub.lat && sub.lng) {
          const marker = L.circleMarker([sub.lat, sub.lng], {
            radius: sub.type === "grid" ? 8 : sub.type === "primary" ? 6 : 4,
            fillColor: sub.type === "grid" ? "#9B59B6" : sub.type === "primary" ? "#3498DB" : "#2ECC71",
            color: "#fff",
            weight: 2,
            fillOpacity: 0.8,
          }).addTo(this._map);
          
          marker.bindPopup(`
            <strong>${sub.name || 'Substation'}</strong><br>
            Type: ${sub.type}<br>
            ${sub.voltage ? `Voltage: ${sub.voltage}` : ''}
          `);
          
          this._markers.push(marker);
        }
      });
    }
    
    // Add power lines
    if (attrs.power_lines) {
      attrs.power_lines.forEach(line => {
        if (line.coords && line.coords.length > 1) {
          const polyline = L.polyline(line.coords, {
            color: line.voltage === "33kV" ? "#E67E22" : "#9B59B6",
            weight: line.voltage === "33kV" ? 2 : 1.5,
            opacity: 0.7,
          }).addTo(this._map);
          
          polyline.bindPopup(`
            <strong>Power Line</strong><br>
            Voltage: ${line.voltage || 'Unknown'}
          `);
          
          this._lines.push(polyline);
        }
      });
    }
    
    // Add fault markers
    if (this.config.show_faults && attrs.live_faults) {
      attrs.live_faults.forEach(fault => {
        if (fault.lat && fault.lng) {
          const icon = L.divIcon({
            className: "custom-marker",
            html: '<div class="fault-marker"></div>',
            iconSize: [20, 20],
          });
          
          const marker = L.marker([fault.lat, fault.lng], { icon }).addTo(this._map);
          
          marker.bindPopup(`
            <strong>⚡ ${fault.type === 'planned' ? 'Planned Outage' : 'Power Cut'}</strong><br>
            ${fault.postcode ? `Area: ${fault.postcode}` : ''}<br>
            ${fault.customers ? `Affected: ${fault.customers.toLocaleString()} customers` : ''}
          `);
          
          this._markers.push(marker);
        }
      });
    }
    
    // Add embedded generation
    if (attrs.generation_sites) {
      attrs.generation_sites.forEach(site => {
        if (site.lat && site.lng) {
          const colors = {
            solar: "#F1C40F",
            wind: "#3498DB",
            battery: "#E91E63",
            other: "#95A5A6",
          };
          
          const marker = L.circleMarker([site.lat, site.lng], {
            radius: 5,
            fillColor: colors[site.type] || colors.other,
            color: "#fff",
            weight: 1,
            fillOpacity: 0.9,
          }).addTo(this._map);
          
          marker.bindPopup(`
            <strong>${site.name || 'Generation Site'}</strong><br>
            Type: ${site.type}<br>
            ${site.capacity ? `Capacity: ${site.capacity} MW` : ''}
          `);
          
          this._markers.push(marker);
        }
      });
    }
  }

  _updateForecast(forecast) {
    const container = this.shadowRoot.getElementById("forecast-container");
    const chart = this.shadowRoot.getElementById("forecast-chart");
    const bestTime = this.shadowRoot.getElementById("best-time");
    
    if (!container || !forecast || !forecast.length) {
      if (container) container.style.display = "none";
      return;
    }
    
    container.style.display = "block";
    
    // Find max intensity for scaling
    const max = Math.max(...forecast.map(f => f.intensity));
    
    // Build chart bars
    if (chart) {
      chart.innerHTML = forecast.map(f => {
        const height = (f.intensity / max) * 100;
        const color = INTENSITY_COLORS[f.index] || INTENSITY_COLORS.moderate;
        return `<div class="forecast-bar" style="height: ${height}%; background: ${color}" title="${new Date(f.from).toLocaleTimeString()}: ${f.intensity} gCO2/kWh"></div>`;
      }).join("");
    }
    
    // Show best time
    if (bestTime) {
      const best = forecast.reduce((min, f) => f.intensity < min.intensity ? f : min, forecast[0]);
      const bestDate = new Date(best.from);
      bestTime.innerHTML = `🌿 Best time: <strong>${bestDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong> (${best.intensity} gCO2/kWh)`;
    }
  }

  getCardSize() {
    return 6;
  }

  static getConfigElement() {
    return document.createElement("hagrid-map-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.hagrid_grid_map",
      title: "UK Grid Map",
      height: "400px",
      show_generation_mix: true,
      show_infrastructure: true,
      show_faults: true,
    };
  }
}

// Card Editor
class HAGridMapCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  _render() {
    this.innerHTML = `
      <div style="padding: 16px;">
        <p>Configure HAGrid Map Card</p>
        <label>
          Entity:<br>
          <input type="text" id="entity" value="${this._config.entity || ''}" style="width: 100%">
        </label>
        <br><br>
        <label>
          Title:<br>
          <input type="text" id="title" value="${this._config.title || 'UK Grid Map'}" style="width: 100%">
        </label>
        <br><br>
        <label>
          <input type="checkbox" id="show_generation_mix" ${this._config.show_generation_mix !== false ? 'checked' : ''}>
          Show Generation Mix
        </label>
        <br>
        <label>
          <input type="checkbox" id="show_infrastructure" ${this._config.show_infrastructure !== false ? 'checked' : ''}>
          Show Infrastructure
        </label>
        <br>
        <label>
          <input type="checkbox" id="show_faults" ${this._config.show_faults !== false ? 'checked' : ''}>
          Show Live Faults
        </label>
      </div>
    `;

    // Add event listeners
    this.querySelectorAll("input").forEach(input => {
      input.addEventListener("change", () => this._valueChanged());
    });
  }

  _valueChanged() {
    const config = {
      ...this._config,
      entity: this.querySelector("#entity").value,
      title: this.querySelector("#title").value,
      show_generation_mix: this.querySelector("#show_generation_mix").checked,
      show_infrastructure: this.querySelector("#show_infrastructure").checked,
      show_faults: this.querySelector("#show_faults").checked,
    };
    
    const event = new CustomEvent("config-changed", {
      detail: { config },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }
}

// Register custom elements
customElements.define("hagrid-map-card", HAGridMapCard);
customElements.define("hagrid-map-card-editor", HAGridMapCardEditor);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: "hagrid-map-card",
  name: "HAGrid Map Card",
  description: "UK Electrical Grid Map with carbon intensity, generation mix, and infrastructure",
  preview: true,
  documentationURL: "https://github.com/jaylouisw/HA/tree/main/HAGrid",
});

console.info(
  `%c HAGRID-MAP-CARD %c v${VERSION} `,
  "color: white; background: #9B59B6; font-weight: bold;",
  "color: #9B59B6; background: white; font-weight: bold;"
);
