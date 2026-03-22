import sys
import asyncio
import argparse
import logging
from getpass import getpass

from .client import ChargePoint
from .constants import _LOGGER
from .exceptions import LoginError, InvalidSession, CommunicationError


async def main(debug: bool = False):
    stream_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    stream_handler.setFormatter(formatter)
    _LOGGER.addHandler(stream_handler)

    if debug:
        stream_handler.setLevel(logging.DEBUG)
        _LOGGER.setLevel(logging.DEBUG)
    else:
        stream_handler.setLevel(logging.WARNING)
        _LOGGER.setLevel(logging.WARNING)

    username = input("ChargePoint Username: ")

    print("\nAuthentication method:")
    print("  1) Password")
    print("  2) Coulomb token")
    print("  3) SSO token")
    auth_choice = input("Choice [1/2/3]: ").strip()

    try:
        if auth_choice == "2":
            coulomb_token = getpass("Coulomb token: ")
            client = await ChargePoint.create(username, coulomb_token=coulomb_token)
        elif auth_choice == "3":
            sso_token = getpass("SSO token: ")
            client = await ChargePoint.create(username)
            await client.login_with_sso_session(sso_token)
        else:
            password = getpass("Password: ")
            client = await ChargePoint.create(username)
            await client.login_with_password(password)
    except (LoginError, InvalidSession):
        sys.exit(1)

    try:
        print("\n=== Account Information ===")
        acct = await client.get_account()
        print(f"Name: {acct.user.full_name}")
        print(f"Balance: {acct.account_balance.amount} {acct.account_balance.currency}")
        print(f"Country: {client.global_config.default_country.name}")
        print(f"Phone: {acct.user.phone}")

        print("\n=== Vehicles ===")
        evs = await client.get_vehicles()
        for ev in evs:
            print(f"{ev.year} {ev.make} {ev.model}:")
            print(f"  Color: {ev.color}")
            print(f"  Charging Speed: {ev.charging_speed} kW")
            print(f"  DC Charging Speed: {ev.dc_charging_speed} kW")

        home_chargers = await client.get_home_chargers()
        chargers_ready_to_charge = []
        if home_chargers:
            print("\n=== Home Charger ===")
        for c in home_chargers:
            panda = await client.get_home_charger_status(c)
            tech_info = await client.get_home_charger_technical_info(c)

            if panda.charging_status == "AVAILABLE":
                chargers_ready_to_charge.append(panda)

            print(f"{panda.brand} {panda.model}")
            print(f"  Connected: {panda.connected} (Last Seen: {panda.last_connected_at})")
            print(f"  Plugged-In: {panda.plugged_in}")
            print(f"  Status: {panda.charging_status}")
            print(f"  Software Version: {tech_info.software_version}")
            if panda.reminder_enabled:
                print(f"  Reminder: {panda.reminder_time}")

        is_charging = await client.get_user_charging_status()
        print("\n=== Account Charging Status ===")
        if is_charging:
            print(f"Charging at {is_charging.stations[0].name}:")
            session = await client.get_charging_session(is_charging.session_id)
            print(f"  State: {session.charging_state}")
            print(f"  Miles Added: {session.miles_added}")
            print(f"  Energy Used: {session.energy_kwh} kWh")
            print(f"  Cost: {session.total_amount} {session.currency_iso_code}")

            stop_session = input("End current session? [yes|no]: ")
            if stop_session == "yes":
                try:
                    await session.stop()
                    print("Session stopped.")
                except CommunicationError as e:
                    print(f"Failed to stop session: {e.message}")

            start_session = input("Start a new session? [yes|no]: ")
            if start_session == "yes":
                try:
                    await client.start_charging_session(device_id=session.device_id)
                    print(f"Resumed session with new ID: {session.session_id}")
                except CommunicationError as e:
                    print(f"Failed to start session: {e.message}")

        elif chargers_ready_to_charge:
            for panda in chargers_ready_to_charge:
                start_session = input(
                    f"Start a new session on {panda.model} ({panda.charger_id})? [yes|no]: "
                )
                if start_session == "yes":
                    try:
                        await client.start_charging_session(panda.charger_id)
                    except CommunicationError as e:
                        print(f"Failed to start session: {e.message}")
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChargePoint CLI")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    asyncio.run(main(debug=args.debug))
