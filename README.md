# python-chargepoint

A simple Pythonic wrapper around the ChargePoint EV Charging Network API.

## DISCLAIMER

I, nor this project, are in _any way_ associated with ChargePoint. Use this project at your own risk.
ChargePoint is a registered trademark of ChargePoint, Inc.

I just wanted a way to retrieve and store charging data from my ChargePoint Home Flex
in a way that is easy to model and query. This project is the first step in getting that data into a
more robust time series database.

## Use

### Login

```python
from python_chargepoint import ChargePoint

client = ChargePoint(username="user", password="password")
print(client.user_id)
# 1234567890
```

### Home Chargers
```python
from python_chargepoint import ChargePoint

client = ChargePoint(username="user", password="password")
chargers = client.get_home_chargers()
print(chargers)
# [12345678]

for charger_id in chargers:
    charger = client.get_home_charger_status(charger_id=charger_id)
    print(charger)
# HomeChargerStatus(
#   brand='CP', 
#   plugged_in=True, 
#   connected=True, 
#   charging_status='NOT_CHARGING', 
#   last_connected_at=datetime.datetime(2022, 1, 30, 15, 14, 36), 
#   reminder_enabled=False, 
#   reminder_time='21:00', 
#   model='CPH50-NEMA6-50-L23', 
#   mac_address='0024B10000012345',
#   amperage_limit=25,
#   possible_amperage_limits=[20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32])
```

### Account Charging Status and Session

```python
from python_chargepoint import ChargePoint

client = ChargePoint(username="user", password="password")
charging = client.get_user_charging_status()
if charging:
    print(charging)
# UserChargingStatus(
#   session_id=1234567890,
#   start_time=datetime.datetime(2022, 1, 30, 13, 32, 45), 
#   state='fully_charged', 
#   stations=[
#     ChargePointStation(
#       id=12345678,  
#       name='CP HOME ',
#       latitude=30.0000000,
#       longitude=-90.0000000)
#     ])

    session = client.get_charging_session(charging.session_id)
    print(session)
#  ChargingSession(
#    session_id=1234567890, 
#    start_time=datetime.datetime(2022, 1, 30, 13, 32, 45), 
#    device_id=12345678, 
#    device_name='CP HOME', 
#    charging_state='fully_charged', 
#    charging_time=2426000, 
#    energy_kwh=4.3404, 
#    miles_added=15.024461538461539, 
#    miles_added_per_hour=0.0, 
#    outlet_number=1, 
#    port_level=2, 
#    power_kw=0.0, 
#    purpose='PERSONAL', 
#    currency_iso_code='USD', 
#    payment_completed=True, 
#    payment_type='none', 
#    pricing_spec_id=0, 
#    total_amount=0.67, 
#    api_flag=False, 
#    enable_stop_charging=True, 
#    has_charging_receipt=False, 
#    has_utility_info=True, 
#    is_home_charger=True, 
#    is_purpose_finalized=True, 
#    last_update_data_timestamp=datetime.datetime(2022, 1, 30, 15, 12, 48), 
#    stop_charge_supported=True, 
#    company_id=12345, 
#    company_name='CP Home', 
#    latitude=30.0000000, 
#    longitude=-90.0000000, 
#    address='Home Charger', 
#    city='City', 
#    state_name='State', 
#    country='United States', 
#    zipcode='12345', 
#    update_data=[
#      ChargingSessionUpdate(
#        energy_kwh=0.0,
#        power_kw=0.0002, 
#        timestamp=datetime.datetime(2022, 1, 30, 13, 32, 57)),
#      ChargingSessionUpdate(
#        energy_kwh=0.0001,
#        power_kw=0.1568,
#        timestamp=datetime.datetime(2022, 1, 30, 13, 33, 9)),
#      ChargingSessionUpdate(
#        energy_kwh=0.0025, 
#        power_kw=3.7337, 
#        timestamp=datetime.datetime(2022, 1, 30, 13, 33, 12)),
#      ChargingSessionUpdate(
#        energy_kwh=0.0161, 
#        power_kw=1.3854, 
#        timestamp=datetime.datetime(2022, 1, 30, 13, 33, 33)),
#      ...],
#    update_period=300000, 
#    utility=PowerUtility(
#      id=0, 
#      name='Energy Company', 
#      plans=[
#        PowerUtilityPlan(
#          code='R', 
#          id=12345, 
#          is_ev_plan=False, 
#          name='Residential')
#      ]))
```

#### Starting or Stopping a Session

```python
from python_chargepoint import ChargePoint

client = ChargePoint(username="user", password="password")
charging = client.get_user_charging_status()

if charging:
    session = client.get_charging_session(charging.session_id)
    session.stop()

    # If you wanted to charge again, you can start a new session.
    session = client.start_charging_session(session.device_id)
```

You can also start a new session by providing any device ID you want to start charging on.

```python
from python_chargepoint import ChargePoint

client = ChargePoint(username="user", password="password")
home_flex_id = client.get_home_chargers()[0]
home_flex = client.get_home_charger_status(home_flex_id)

if home_flex.charging_status == "AVAILABLE":
    session = client.start_charging_session(home_flex_id)
```

#### Setting the amperage limit

```python
from python_chargepoint import ChargePoint

client = ChargePoint(username="user", password="password")
home_flex_id = client.get_home_chargers()[0]

# Print out valid amperage values.
print(client.get_home_charger_status(home_flex_id).possible_amperage_limits)
# [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]

client.set_amperage_limit(home_flex_id, 23)
print(client.get_home_charger_status(home_flex_id).amperage_limit)
# 23
```
