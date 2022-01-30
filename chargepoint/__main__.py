import sys
import logging
from getpass import getpass

from . import LOGGER
from .client import ChargePoint
from .exceptions import ChargePointLoginError

if __name__ == "__main__":
    stream_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(stream_handler)

    username = input("ChargePoint Username: ")
    password = getpass("Password: ")

    try:
        client = ChargePoint(username, password)
    except ChargePointLoginError:
        sys.exit(1)

    print("\n=== Account Information ===")
    acct = client.get_account()
    print(f"Name: {acct.user.fullName}")
    print(f"Balance: {acct.accountBalance.amount} {acct.accountBalance.currency}")

    print("\n=== Vehicles ===")
    evs = client.get_vehicles()
    for ev in evs:
        print(f"{ev.year} {ev.make} {ev.model}:")
        print(f"  Color: {ev.color}")
        print(f"  Charging Speed: {ev.charging_speed} kW")
        print(f"  DC Charging Speed: {ev.dc_charging_speed} kW")

    home_chargers = client.get_home_chargers()
    if home_chargers:
        print("\n=== Home Charger ===")
    for c in home_chargers:
        panda = client.get_home_charger_status(c)
        print(f"{panda.brand} {panda.model}")
        print(f"  Connected: {panda.connected} (Last Seen: {panda.last_connected_at})")
        print(f"  Plugged-In: {panda.plugged_in}")
        print(f"  Status: {panda.charging_status}")
        if panda.reminder_enabled:
            print(f"  Reminder: {panda.reminder_time}")

    is_charging = client.get_user_charging_status()
    print("\n=== Account Charging Status ===")
    if is_charging:
        print(f"Charging at {is_charging.stations[0].name}:")
        session = client.get_charging_session(is_charging.session_id)
        print(f"  State: {session.charging_state}")
        print(f"  Miles Added: {session.miles_added}")
        print(f"  Energy Used: {session.energy_kwh} kWh")
        print(f"  Cost: {session.total_amount} {session.currency_iso_code}")
