# python-chargepoint

A simple, async Pythonic wrapper around the ChargePoint EV Charging Network API.

## Disclaimer

This project is not affiliated with or endorsed by ChargePoint in any way. Use at your own risk.
ChargePoint is a registered trademark of ChargePoint, Inc.

---

## Installation

```bash
pip install python-chargepoint
```

---

## Library Usage

All client methods are `async` and must be called from an async context.

### Authentication

Three authentication methods are supported. The client is created via the async factory `ChargePoint.create()`.

**Password:**
```python
import asyncio
from python_chargepoint import ChargePoint

async def main():
    client = await ChargePoint.create(username="user@example.com")
    await client.login_with_password("password")
    # ...
    await client.close()

asyncio.run(main())
```

**Long-lived session token** (recommended for automation):
```python
client = await ChargePoint.create(
    username="user@example.com",
    coulomb_token="<coulomb_sess cookie value>",
)
```

**SSO JWT:**
```python
client = await ChargePoint.create(username="user@example.com")
await client.login_with_sso_session("<sso jwt>")
# you can then grab client.coulomb_token and use the above pattern going forward
```

---

### Obtaining Tokens Manually

Password-based login may be blocked by bot-protection (Datadome). When that happens,
you can capture a token directly from your browser and pass it to the client.

1. Open [https://driver.chargepoint.com](https://driver.chargepoint.com) in your browser and log in normally.
2. Open Developer Tools and navigate to **Application > Cookies > https://driver.chargepoint.com**.
3. Copy the value of one of the following cookies:

| Cookie | Use as |
|---|---|
| `coulomb_sess` | `coulomb_token=` (recommended — long-lived) |
| `auth-session` | `login_with_sso_session()` (shorter-lived JWT) |

> **Note:** The `coulomb_sess` value contains `#` and `?` characters. The library handles both raw and URL-encoded (`%23`, `%3F`) forms automatically. When setting it as a shell environment variable, always wrap the value in **double quotes** to prevent the shell from interpreting `#` as a comment:
>
> ```bash
> export CP_COULOMB_TOKEN="Ab3dEf...token...#D???????#RNA-US"
> ```

---

### Account

```python
acct = await client.get_account()
print(acct.user.full_name)        # "Jane Smith"
print(acct.account_balance.amount)  # "12.34"

evs = await client.get_vehicles()
for ev in evs:
    print(f"{ev.year} {ev.make} {ev.model}")  # "2023 Polestar 2"
    print(f"  AC: {ev.charging_speed} kW  DC: {ev.dc_charging_speed} kW")
```

---

### Home Charger

```python
charger_ids = await client.get_home_chargers()
# [12345678]

charger_id = charger_ids[0]

status = await client.get_home_charger_status(charger_id)
# HomeChargerStatus(
#   charger_id=12345678,
#   brand='CP',
#   model='HOME FLEX',
#   charging_status='AVAILABLE',
#   is_plugged_in=True,
#   is_connected=True,
#   amperage_limit=28,
#   possible_amperage_limits=[20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32])

tech = await client.get_home_charger_technical_info(charger_id)
# HomeChargerTechnicalInfo(
#   model_number='CPH50-NEMA6-50-L23',
#   serial_number='...',
#   software_version='1.2.3.4',
#   last_connected_at=datetime(...))

config = await client.get_home_charger_config(charger_id)
# HomeChargerConfiguration(
#   station_nickname='Home Flex',
#   led_brightness=LEDBrightness(level=5, supported_levels=[0,1,2,3,4,5]),
#   utility=PowerUtility(name='Austin Energy', ...))
```

#### Amperage limit

```python
# Print valid amperage values
print(status.possible_amperage_limits)
# [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]

await client.set_amperage_limit(charger_id, 24)
```

#### LED brightness

Levels map to: `0`=off, `1`=20%, `2`=40%, `3`=60%, `4`=80%, `5`=100%.
Available levels are returned by `get_home_charger_config()`.

```python
await client.set_led_brightness(charger_id, 3)  # 60%
```

#### Restart

```python
await client.restart_home_charger(charger_id)
```

---

### Charging Status and Sessions

```python
status = await client.get_user_charging_status()
if status:
    print(status.state)       # "fully_charged"
    print(status.session_id)  # 1234567890

    session = await client.get_charging_session(status.session_id)
    print(session.charging_state)  # "fully_charged"
    print(session.energy_kwh)      # 6.42
    print(session.miles_added)     # 22.3
```

#### Starting and stopping a session

```python
# Stop the current session
session = await client.get_charging_session(status.session_id)
await session.stop()

# Start a new session on any device
new_session = await client.start_charging_session(device_id=charger_id)
print(new_session.session_id)
```

---

### Station Info

Fetch detailed information about any station by device ID — ports, pricing, connector types, and real-time status.

```python
info = await client.get_station(device_id=13055991)
print(f"{' / '.join(info.name)}")          # "DOMAIN TOWER 2 / LVL 2_STATION 2"
print(info.address.address1)               # "10025 Alterra Pkwy"
print(info.station_status_v2)              # "available"
print(info.ports_info.port_count)          # 2

for port in info.ports_info.ports:
    print(f"Port {port.outlet_number}: {port.status_v2} ({port.level})")
    for c in port.connector_list:
        print(f"  {c.display_plug_type}: {c.status_v2}")

if info.station_price:
    for tou in info.station_price.tou_fees:
        print(f"Rate: {tou.fee.amount} {info.station_price.currency_code}/{tou.fee.unit}")
```

---

### Nearby Stations

Fetch all charging stations visible within a geographic bounding box. Results include
both public stations and the user's home charger (if it falls within the bounds).

```python
from python_chargepoint.types import MapFilter, ZoomBounds

bounds = ZoomBounds(sw_lat=30.37, sw_lon=-97.66, ne_lat=30.40, ne_lon=-97.64)

# No filter — return all stations
stations = await client.get_nearby_stations(bounds)

# Optional: filter by connector type or status
f = MapFilter(connector_l2=True, connector_combo=True, status_available=True)
stations = await client.get_nearby_stations(bounds, station_filter=f)

for s in stations:
    print(f"{s.name1} — {s.station_status_v2}")
    if s.is_home and s.charging_info:
        print(f"  Charging: {s.charging_info.current_charging}")
```

**`MapFilter` fields** (all `bool`, default `False`):

| Field | Description |
|---|---|
| `connector_l2` | Level 2 AC |
| `connector_combo` | CCS combo (DC) |
| `connector_chademo` | CHAdeMO (DC) |
| `connector_tesla` | Tesla proprietary |
| `connector_l1` | Level 1 AC |
| `connector_l2_tesla` | Tesla Level 2 |
| `connector_l2_nema_1450` | NEMA 14-50 |
| `dc_fast_charging` | Any DC fast charger |
| `status_available` | Only available stations |
| `price_free` | Only free stations |
| `van_accessible` | Van-accessible spaces |
| `disabled_parking` | Disability-accessible parking |
| `network_chargepoint` | ChargePoint network |
| `network_blink` | Blink network |
| `network_evgo` | EVgo network |
| `network_flo` | FLO network |
| `network_ionna` | IONNA network |
| `network_evconnect` | EV Connect |
| `network_evgateway` | EV Gateway |
| `network_bchydro` | BC Hydro |
| `network_greenlots` | Greenlots |
| `network_mercedes` | Mercedes-Benz |
| `network_circuitelectric` | Circuit Électrique |

---

## CLI

After installation, a `chargepoint` command is available.

### Authentication

Credentials are read from environment variables. The CLI falls back to prompting for a password if no token is set.

```bash
export CP_USERNAME="user@example.com"
export CP_COULOMB_TOKEN="<coulomb_sess cookie value>"
# or
export CP_SSO_JWT="<sso jwt>"
```

### Global options

```
chargepoint [--debug] [--json] <command>
```

`--json` dumps the raw API response as JSON — useful for scripting.

### Commands

```bash
# Account
chargepoint account
chargepoint vehicles

# Charging status
chargepoint charging-status

# Station info
chargepoint station <device_id>

# Nearby stations
chargepoint nearby --sw-lat 30.37 --sw-lon -97.66 --ne-lat 30.40 --ne-lon -97.64 \
    [--connector-l2] [--connector-combo] [--connector-chademo] [--connector-tesla] \
    [--dc-fast] [--available-only] [--free-only]

# Home charger
chargepoint charger list
chargepoint charger status <charger_id>
chargepoint charger tech-info <charger_id>
chargepoint charger config <charger_id>
chargepoint charger set-amperage <charger_id> <amps>
chargepoint charger set-led <charger_id> <level>   # 0=off 1=20% 2=40% 3=60% 4=80% 5=100%
chargepoint charger restart <charger_id>

# Sessions
chargepoint session get <session_id>
chargepoint session start <device_id>
chargepoint session stop <session_id>
```

Use `--help` on any command or subgroup for details:

```bash
chargepoint nearby --help
chargepoint charger --help
```

---

## Development

### Setup

```bash
git clone https://github.com/mbillow/python-chargepoint.git
cd python-chargepoint
poetry install
poetry run pre-commit install
```

### Checks

The following checks run automatically on every commit via pre-commit, and are also enforced in CI:

| Tool | Purpose |
|---|---|
| `black` | Code formatting |
| `flake8` | Style and error linting |
| `mypy` | Static type checking |
| `pyright` | Pylance-compatible type checking |

To run them manually:

```bash
poetry run pre-commit run --all-files
```

Or individually:

```bash
poetry run black --check python_chargepoint/ tests/
poetry run flake8 python_chargepoint/ tests/
poetry run mypy python_chargepoint/
poetry run pyright python_chargepoint/
```

### Tests

```bash
poetry run pytest
```
