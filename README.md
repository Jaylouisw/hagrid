# HAGrid - UK Electrical Grid Map 🔌

<p align="center">
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.1+-blue?style=for-the-badge&logo=home-assistant" alt="Home Assistant">
  <img src="https://img.shields.io/badge/HACS-Custom-orange?style=for-the-badge" alt="HACS">
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
6. **Settings → Devices & Services → Add Integration → HAGrid**. HAGrid takes your grid region
   from the home location already set in Home Assistant, so there is no postcode to enter.

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

HAGrid uses the home location already set in Home Assistant (**Settings → System → General → Home
location**). That location becomes a UK postcode through postcodes.io, and the postcode picks your
carbon intensity region and your DNO. There is no postcode to type in.

If Home Assistant is not installed in Great Britain, or you want grid data for somewhere else, the
integration offers the region list instead and your choice overrides the automatic detection. The
same list is what you get when the lookup service cannot be reached.

| Where the region comes from | What happens when the home location changes |
|---|---|
| The home location (the default) | Re-checked on every restart, so moving house corrects itself |
| A region picked by hand | Stays as set. Turn **Follow the Home Assistant home location** back on in Options to hand it back |

| Option | Default | Description |
|---|---|---|
| Follow the HA home location | On | Keep the grid region in step with the home location |
| Update interval | 300s | How often to fetch new data |
| Show infrastructure | ✓ | Display substations and power lines |
| Show live faults | ✓ | Display active power cuts |
| Include forecast | ✓ | Fetch 48-hour carbon forecast |

### API key storage

Any API keys you enter are stored in the Home Assistant configuration entry at
`config/.storage/core.config_entries` as plain text on disk. They are **not** encrypted.
Access is protected only by the file permissions on the `.storage` directory. Keep that
directory readable only by the Home Assistant process and treat the keys like any other
credential stored on the same host.

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
| [postcodes.io](https://postcodes.io/) | Reverse geocoding: the Home Assistant home location to a UK postcode | Open Government Licence |
| [NGED Connected Data](https://connecteddata.nationalgrid.co.uk/) | Live power cuts, live GSP flows and demand for the Midlands, South Wales and the South West | Open data (IB1-O) |
| [UKPN Open Data](https://ukpowernetworks.opendatasoft.com/) and NGED's live layer, as above | Live power cuts with affected-customer counts | CC BY 4.0 / Open Government Licence |

Every source used by the core GB feature is free and keyless. The non-GB TSO clients in the code are
unverified — treat the GB path as what works.

### Which network operators are covered

| Your network operator | Live power cuts | Substations and lines on the map |
|---|---|---|
| UK Power Networks (London, Eastern, South Eastern) | yes, keyless | UKPN's own open data, plus OpenStreetMap |
| NGED (East Midlands, West Midlands, South West, South Wales) | yes, keyless | OpenStreetMap, plus NGED's own locations if you register for a key |
| SSEN, ENWL, Northern Powergrid, SP Energy | not yet | OpenStreetMap |

The map does not depend on your network operator at all. It is drawn from OpenStreetMap around the
home location set in Home Assistant, at whatever radius you choose, and OpenStreetMap covers the whole
country: measured 2026-09-20, a 10 km radius on Birmingham returns 10,090 power features, of which
1,709 are substations, 413 power lines, 394 towers and 89 minor lines. It is community-mapped, so
treat it as indicative rather than authoritative, and set the radius to something sensible.

Both fault feeds are open data, so nobody needs an account for the power cuts. NGED restricts its
substation locations and its generation capacity register to registered users: that restriction is
the mitigation its own Data Sharing Assessment relies on, so it is not something this integration
routes around. If you want those layers, register on NGED's portal and paste your own key into the
integration; if you do not, everything else still works.

One difference worth knowing: UKPN publishes coordinates for each incident and NGED does not, so
NGED's power cuts appear in the Live Faults sensor's attributes with their licence area but not as
markers on the map.

## 🛣️ Roadmap

- [x] NGED live layer (East Midlands, West Midlands, South West, South Wales)
- [ ] NGED static layers (substation locations, generation capacity register)
- [ ] More DNO sources (SSEN, ENWL, NPG, SPEN)
- [ ] Energy Dashboard integration
- [ ] Smart meter data import
- [ ] Price signals (Octopus Agile, etc.)
- [ ] Grid frequency monitoring
- [ ] Custom region overlays

## 📝 Changelog

### Unreleased

- **There is no postcode to enter any more.** HAGrid reads the home location already set in Home
  Assistant, turns it into a postcode through postcodes.io, and uses that for the carbon intensity
  region and the DNO. A home location outside Great Britain, or a lookup service that cannot be
  reached, falls back to picking a region by hand, which is where the region list now lives.
- The map card and the OpenStreetMap queries centre on the Home Assistant home location instead of
  on whichever substation happened to come first in the list, which was central London when the
  substation list was empty.
- 300s is the default update interval, as the code has always said. The table here said 120s.

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
