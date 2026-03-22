import sys
import logging
from getpass import getpass

from .client import ChargePoint
from .constants import _LOGGER
from .exceptions import ChargePointLoginError

if __name__ == "__main__":
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    stream_handler.setFormatter(formatter)
    _LOGGER.addHandler(stream_handler)
    _LOGGER.setLevel(logging.DEBUG)

    username = input("ChargePoint Username: ")
    password = getpass("Password: ")

    try:
        client = ChargePoint(username)
        client.login_with_sso_session("eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJ1cm46Y3A6dXNlcjpuYS11czowMDZlNzAyMi05MDM0LTRlOWQtOThhMy1iY2E0ODRiZjA1ZWYiLCJpYXQiOjE3NzQyMDk1MjQsIm5iZiI6MTc3NDIwOTUyNCwiZXhwIjoxNzc0MjE2NzI0LCJpc3MiOiJjaGFyZ2Vwb2ludCIsInJvbGUiOiJkcml2ZXIiLCJub3N1c2VyaWQiOjI3NTI0OTgxLCJ1c2VyaWQiOiJ1cm46Y3A6dXNlcjpuYS11czowMDZlNzAyMi05MDM0LTRlOWQtOThhMy1iY2E0ODRiZjA1ZWYiLCJ1c2VybmFtZSI6Im1iaWxsb3ciLCJlbWFpbCI6Im1hcmNAYmlsbG93Lm1lIiwicmVnaW9uIjoiTkEtVVMiLCJ0aW1lem9uZSI6IkNEVCIsInRpbWV6b25lX29mZnNldCI6LTE4MDAwLCJ6b25lX2lkIjoiQW1lcmljYS9DaGljYWdvIiwicHJlZmVycmVkX2lkcF9pZCI6LTEsInRlbmFudF9pZCI6Im5vcyIsImlkcF91c2VyX2lkIjoiIiwianRpIjoiWVRSaU16VTJNRE10TlRBM1ppMDBNVGxtTFdFeE5USXRZMk5qTURnMU4yTXdOVEV3I1UyOWFmYWYjUk5BLVVTIiwiYXVkIjoiQ2hhcmdlUG9pbnQifQ.cghE-nHWKgYNJxwd3w_-z401x9AxTuJ8b5HQNWLyNqrKn4RC31Uevr-8uqzpNMpYqVQ6PgAc63ICMg3xXk_yYA")
    except ChargePointLoginError:
        sys.exit(1)

    print("\n=== Account Information ===")
    acct = client.get_account()
    print(f"Name: {acct.user.full_name}")
    print(f"Balance: {acct.account_balance.amount} {acct.account_balance.currency}")
    print(f"Country: {client.global_config.default_country.name}")
    print(f"Phone: {acct.user.phone}")

    print("\n=== Vehicles ===")
    evs = client.get_vehicles()
    for ev in evs:
        print(f"{ev.year} {ev.make} {ev.model}:")
        print(f"  Color: {ev.color}")
        print(f"  Charging Speed: {ev.charging_speed} kW")
        print(f"  DC Charging Speed: {ev.dc_charging_speed} kW")

    home_chargers = client.get_home_chargers()
    chargers_ready_to_charge = []
    if home_chargers:
        print("\n=== Home Charger ===")
    for c in home_chargers:
        panda = client.get_home_charger_status(c)
        tech_info = client.get_home_charger_technical_info(c)

        if panda.charging_status == "AVAILABLE":
            chargers_ready_to_charge.append(panda)

        print(f"{panda.brand} {panda.model}")
        print(f"  Connected: {panda.connected} (Last Seen: {panda.last_connected_at})")
        print(f"  Plugged-In: {panda.plugged_in}")
        print(f"  Status: {panda.charging_status}")
        print(f"  Software Version: {tech_info.software_version}")
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

        stop_session = input("End current session? [yes|no]: ")
        if stop_session == "yes":
            session.stop()

        start_session = input("Start a new session? [yes|no]: ")
        if start_session == "yes":
            client.start_charging_session(device_id=session.device_id)
            print(f"Resumed session with new ID: {session.session_id}")

    elif chargers_ready_to_charge:
        for panda in chargers_ready_to_charge:
            start_session = input(
                f"Start a new session on {panda.model} ({panda.charger_id})? [yes|no]: "
            )
            if start_session == "yes":
                client.start_charging_session(panda.charger_id)
