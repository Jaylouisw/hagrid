# HAGrid - UK Electrical Grid Map 🔌

<p align="center">
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.1+-blue?style=for-the-badge&logo=home-assistant" alt="Home Assistant">
  <img src="https://img.shields.io/badge/HACS-Custom-orange?style=for-the-badge" alt="HACS">
  <img src="https://img.shields.io/github/actions/workflow/status/Jaylouisw/hagrid/tests.yml?style=for-the-badge&label=CI" alt="CI">
  <img src="https://img.shields.io/github/v/release/Jaylouisw/hagrid?style=for-the-badge&label=Release" alt="Release">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

**HAGrid** brings the UK electrical grid into Home Assistant: real-time carbon intensity, generation
mix, live faults, and your local grid infrastructure on an interactive map.

## 📦 Installation

### HACS

1. Open HACS in Home Assistant
2. Click the three dots → **Custom repositories**
3. Add `https://github.com/jaylouisw/hagrid` — Category: **Integration**
4. Search for **HAGrid** and install
5. Restart Home Assistant
6. **Settings → Devices & Services → Add Integration → HAGrid**, then enter your postcode

### Manual

1. Download the latest release
2. Copy `custom_components/hagrid/` into your `config/custom_components/` — the folder must be named
   exactly `hagrid`
3. Copy `www/hagrid-map/` into your `config/www/`
4. Restart Home Assistant

### The map card

The integration installs the sensors; the map is a separate Lovelace resource. Copy
`www/hagrid-map/hagrid-map.js` to `config/www/hagrid-map/` and add it under
**Settings → Dashboards → Resources** as `/local/hagrid-map/hagrid-map.js` (JavaScript module), then:

```yaml
type: custom:hagrid-map-card
entity: sensor.hagrid_grid_map
title: UK Grid Map
height: 400px
show_generation_mix: true
show_infrastructure: true
show_faults: true
```

| Option | Type | Description |
|---|---|---|
| `entity` | string | Map data sensor (required) |
| `title` | string | Card title |
| `height` | string | Map height (default: 400px) |
| `show_generation_mix` | boolean | Show generation bar chart |
| `show_infrastructure` | boolean | Show substations/lines on map |
| `show_faults` | boolean | Show live faults on map |
| `center` | [lat, lng] | Map center coordinates |
| `zoom` | number | Initial zoom level (default: 5) |

## ⚙️ Configuration

1. Enter your UK postcode (e.g. `SW1A 1AA`)
2. Select your electricity region (auto-detected from the postcode)
3. Configure update intervals and display options

| Option | Default | Description |
|---|---|---|
| Update interval | 120s | How often to fetch new data |
| Show infrastructure | ✓ | Display substations and power lines |
| Show live faults | ✓ | Display active power cuts |
| Include forecast | ✓ | Fetch 48-hour carbon forecast |

## ✨ Features

- **Carbon intelligence** — real-time intensity (gCO2/kWh), carbon index, 48-hour forecast, and
  "best time" recommendations for low-carbon use
- **Generation mix** — live breakdown by source, renewables vs fossil fuels
- **Grid map** — substations (grid/primary/secondary), 33kV and HV overhead lines, embedded
  generation (solar, wind, batteries)
- **Fault monitoring** — live and planned outages in your DNO region with affected-customer counts

## 📡 Sensors

| Sensor | Description |
|---|---|
| `sensor.hagrid_carbon_intensity` | Current carbon intensity (gCO2/kWh) |
| `sensor.hagrid_carbon_index` | Carbon index (very low → very high) |
| `sensor.hagrid_generation_mix` | Dominant fuel source |
| `sensor.hagrid_live_faults` | Number of active faults |
| `sensor.hagrid_carbon_forecast` | Trend direction |
| `sensor.hagrid_grid_map` | Full map data for the Lovelace card |
| `sensor.hagrid_*_generation` | Individual fuel percentages |

## 🔧 Services

| Service | Description |
|---|---|
| `hagrid.refresh_data` | Force refresh all data |
| `hagrid.refresh_infrastructure` | Refresh cached infrastructure |
| `hagrid.get_best_time` | Optimal time for low-carbon usage |
| `hagrid.check_postcode` | Get data for any UK postcode |
| `hagrid.get_regional_comparison` | Compare all UK regions |

## 📊 Automation example

```yaml
automation:
  - alias: "Low Carbon Alert"
    trigger:
      - platform: state
        entity_id: sensor.hagrid_carbon_index
        to: "very low"
    action:
      - service: notify.mobile_app
        data:
          title: "🌿 Low Carbon Electricity!"
          message: >-
            Good time to charge EVs or run appliances. Intensity:
            {{ states('sensor.hagrid_carbon_intensity') }} gCO2/kWh
```

## 🗂️ Data sources

| Source | Data | Licence |
|---|---|---|
| [Carbon Intensity API](https://api.carbonintensity.org.uk/) | Carbon intensity, generation mix, forecasts | Open Government Licence |
| [UKPN Open Data](https://ukpowernetworks.opendatasoft.com/) | Substations, power lines, faults, embedded generation | CC BY 4.0 |

Every source used by the core GB feature is free and keyless. The DNO layer currently covers
**UK Power Networks** (London, Eastern, South Eastern); other DNOs are roadmap items, and the
non-GB TSO clients in the code are unverified — treat the GB path as what works.

## 🛣️ Roadmap

- [ ] More DNO sources (SSEN, ENWL, NPG, SPEN, NGED)
- [ ] Energy Dashboard integration
- [ ] Smart meter data import
- [ ] Price signals (Octopus Agile, etc.)
- [ ] Grid frequency monitoring
- [ ] Custom region overlays

## 📝 Changelog

### 1.1.0

- **Fixed: the integration could not load at all.** `CircuitFlow` in `api.py` declared
  `fuel_type: str | None = None` before `timestamp: datetime`, which is illegal in a Python
  dataclass — every module in the integration raised
  `TypeError: non-default argument 'timestamp' follows default argument 'fuel_type'` at import. Home
  Assistant reported this as `Config flow could not be loaded: {"message":"Invalid handler specified"}`
  because the config-flow handler could not be imported. The two fields are reordered; all call sites
  already constructed `CircuitFlow` with keyword arguments, so nothing else changed. Reported as
  issue #3 against the previous repository.
- **HAGrid now lives in its own repository.** It previously sat at
  `jaylouisw/HA` → `HAGrid/custom_components/hagrid`, two levels below the repository root, which is
  not where HACS looks — so HACS could never offer it, and the `hagrid.zip` asset declared in that
  repo's `hacs.json` was never attached to any release. The integration is now at the repository root
  as `custom_components/hagrid/`, which is what HACS reads. Reported as issue #2.
- `manifest.json` documentation and issue-tracker URLs now point here; version aligned to 1.1.0.

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  Made with ⚡ for the Home Assistant community
</p>
