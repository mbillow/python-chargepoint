import asyncio
import json
import logging
import os
import sys
from functools import wraps
from getpass import getpass

import click

from .client import ChargePoint
from .constants import _LOGGER
from .exceptions import CommunicationError, InvalidSession, LoginError
from .types import MapFilter, ZoomBounds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def async_cmd(f):
    """Decorator: run an async click command inside asyncio.run()."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


def _setup_logging(debug: bool) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    level = logging.DEBUG if debug else logging.WARNING
    handler.setLevel(level)
    _LOGGER.setLevel(level)
    _LOGGER.addHandler(handler)


async def _make_client(debug: bool) -> ChargePoint:
    """Build an authenticated ChargePoint client from env vars / prompts.

    Auth priority:
      1. CP_COULOMB_TOKEN  — long-lived session token
      2. CP_SSO_JWT        — SSO JWT, exchanged for a session token
      3. Password prompt   — falls back to interactive password login
    """
    _setup_logging(debug)
    username = os.environ.get("CP_USERNAME") or click.prompt("ChargePoint Username")
    coulomb_token = os.environ.get("CP_COULOMB_TOKEN", "")
    sso_jwt = os.environ.get("CP_SSO_JWT", "")

    try:
        client = await ChargePoint.create(username, coulomb_token=coulomb_token)
        if not coulomb_token:
            if sso_jwt:
                await client.login_with_sso_session(sso_jwt)
            else:
                password = getpass("Password: ")
                await client.login_with_password(password)
    except (LoginError, InvalidSession) as e:
        click.echo(f"Authentication failed: {e.message}", err=True)
        sys.exit(1)

    return client


def _dump_json(obj) -> None:
    """Serialize a Pydantic model or list of models to JSON and print it."""
    if isinstance(obj, list):
        click.echo(json.dumps([o.model_dump(mode="json") for o in obj], indent=2))
    else:
        click.echo(json.dumps(obj.model_dump(mode="json"), indent=2))


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging.")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.pass_context
def cli(ctx, debug: bool, as_json: bool) -> None:
    """ChargePoint command-line interface."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["as_json"] = as_json


# ---------------------------------------------------------------------------
# account
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
@async_cmd
async def account(ctx) -> None:
    """Show account information and balance."""
    client = await _make_client(ctx.obj["debug"])
    try:
        acct = await client.get_account()
        if ctx.obj["as_json"]:
            _dump_json(acct)
        else:
            click.echo(f"Name:    {acct.user.full_name}")
            click.echo(f"Email:   {acct.user.email}")
            click.echo(f"Phone:   {acct.user.phone or '—'}")
            click.echo(f"Balance: {acct.account_balance.amount} {acct.account_balance.currency}")
            click.echo(f"Country: {client.global_config.default_country.name}")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# vehicles
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
@async_cmd
async def vehicles(ctx) -> None:
    """List registered electric vehicles."""
    client = await _make_client(ctx.obj["debug"])
    try:
        evs = await client.get_vehicles()
        if ctx.obj["as_json"]:
            _dump_json(evs)
        else:
            if not evs:
                click.echo("No vehicles registered.")
                return
            for ev in evs:
                primary = " (primary)" if ev.primary_vehicle else ""
                click.echo(f"{ev.year} {ev.make} {ev.model}{primary}")
                click.echo(f"  Color:    {ev.color}")
                click.echo(f"  AC Speed: {ev.charging_speed} kW")
                click.echo(f"  DC Speed: {ev.dc_charging_speed} kW")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# charging-status
# ---------------------------------------------------------------------------

@cli.command("charging-status")
@click.pass_context
@async_cmd
async def charging_status(ctx) -> None:
    """Show current charging session status."""
    client = await _make_client(ctx.obj["debug"])
    try:
        status = await client.get_user_charging_status()
        if status is None:
            click.echo("Not currently charging.")
            return
        if ctx.obj["as_json"]:
            _dump_json(status)
        else:
            click.echo(f"Session: {status.session_id}")
            click.echo(f"State:   {status.state}")
            click.echo(f"Started: {status.start_time.strftime('%Y-%m-%d %H:%M %Z')}")
            for st in status.stations:
                click.echo(f"Station: {st.name} (device {st.id})")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# station
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("device_id", type=int)
@click.pass_context
@async_cmd
async def station(ctx, device_id: int) -> None:
    """Show detailed information about a charging station."""
    client = await _make_client(ctx.obj["debug"])
    try:
        info = await client.get_station(device_id)
        if ctx.obj["as_json"]:
            _dump_json(info)
        else:
            click.echo(" / ".join(info.name))
            click.echo(f"  Status:    {info.station_status_v2}")
            click.echo(f"  Address:   {info.address.address1}, {info.address.city}, {info.address.state}")
            click.echo(f"  Network:   {info.network.display_name}")
            click.echo(f"  Host:      {info.host_name}")
            if info.description:
                click.echo(f"  Notes:     {info.description}")
            if info.max_power:
                click.echo(f"  Max Power: {info.max_power.max} {info.max_power.unit}")
            click.echo(f"  Ports:     {info.ports_info.port_count} ({'DC' if info.ports_info.dc else 'AC'})")
            for port in info.ports_info.ports:
                click.echo(
                    f"    Port {port.outlet_number}: {port.status_v2}"
                    f" — {port.level} {port.power_range.max} {port.power_range.unit}"
                )
                for c in port.connector_list:
                    click.echo(f"      {c.display_plug_type}: {c.status_v2}")
            if info.station_price:
                p = info.station_price
                for tou in p.tou_fees:
                    click.echo(f"  Rate:      {tou.fee.amount} {p.currency_code}/{tou.fee.unit}")
                if p.guest_fee:
                    click.echo(f"  Guest Fee: {p.guest_fee.amount} {p.currency_code}/{p.guest_fee.unit}")
                for tax in p.taxes:
                    click.echo(f"  Tax:       {tax.name} {tax.percent}%")
            if info.last_charged_date:
                click.echo(f"  Last Used: {info.last_charged_date}")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# nearby
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--sw-lat", type=float, required=True, help="Southwest corner latitude.")
@click.option("--sw-lon", type=float, required=True, help="Southwest corner longitude.")
@click.option("--ne-lat", type=float, required=True, help="Northeast corner latitude.")
@click.option("--ne-lon", type=float, required=True, help="Northeast corner longitude.")
@click.option("--connector-l2", is_flag=True, help="Filter: Level 2 connectors.")
@click.option("--connector-combo", is_flag=True, help="Filter: CCS combo connectors.")
@click.option("--connector-chademo", is_flag=True, help="Filter: CHAdeMO connectors.")
@click.option("--connector-tesla", is_flag=True, help="Filter: Tesla connectors.")
@click.option("--dc-fast", is_flag=True, help="Filter: DC fast charging only.")
@click.option("--available-only", is_flag=True, help="Filter: Show only available stations.")
@click.option("--free-only", is_flag=True, help="Filter: Show only free stations.")
@click.pass_context
@async_cmd
async def nearby(
    ctx,
    sw_lat: float,
    sw_lon: float,
    ne_lat: float,
    ne_lon: float,
    connector_l2: bool,
    connector_combo: bool,
    connector_chademo: bool,
    connector_tesla: bool,
    dc_fast: bool,
    available_only: bool,
    free_only: bool,
) -> None:
    """List charging stations within a bounding box."""
    client = await _make_client(ctx.obj["debug"])
    try:
        bounds = ZoomBounds(sw_lat=sw_lat, sw_lon=sw_lon, ne_lat=ne_lat, ne_lon=ne_lon)
        station_filter = None
        if any([connector_l2, connector_combo, connector_chademo,
                connector_tesla, dc_fast, available_only, free_only]):
            station_filter = MapFilter(
                connector_l2=connector_l2,
                connector_combo=connector_combo,
                connector_chademo=connector_chademo,
                connector_tesla=connector_tesla,
                dc_fast_charging=dc_fast,
                status_available=available_only,
                price_free=free_only,
            )

        stations = await client.get_nearby_stations(bounds, station_filter=station_filter)

        if ctx.obj["as_json"]:
            _dump_json(stations)
        else:
            if not stations:
                click.echo("No stations found in that area.")
                return
            for s in stations:
                home_tag = " [HOME]" if s.is_home else ""
                name = s.name1 + (f" / {s.name2}" if s.name2 else "")
                click.echo(f"{name}{home_tag}")
                click.echo(f"  Status:  {s.station_status_v2}")
                click.echo(f"  Address: {s.address1 or '—'}, {s.city or '—'}")
                click.echo(f"  Network: {s.network_display_name or '—'}")
                power = f"{s.max_power.max} {s.max_power.unit}" if s.max_power else "?"
                click.echo(f"  Ports:   {s.total_port_count} ({power})")
                click.echo(f"  Payment: {s.payment_type}")
                if s.is_home and s.charging_info:
                    ci = s.charging_info
                    click.echo(
                        f"  Session: {ci.current_charging}"
                        f"  {ci.energy_kwh:.3f} kWh"
                        f"  +{ci.miles_added:.1f} mi"
                    )
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# charger subgroup
# ---------------------------------------------------------------------------

@cli.group()
def charger() -> None:
    """Home charger management."""
    pass


@charger.command("list")
@click.pass_context
@async_cmd
async def charger_list(ctx) -> None:
    """List registered home charger IDs."""
    client = await _make_client(ctx.obj["debug"])
    try:
        charger_ids = await client.get_home_chargers()
        if ctx.obj["as_json"]:
            click.echo(json.dumps(charger_ids, indent=2))
        else:
            if not charger_ids:
                click.echo("No home chargers registered.")
                return
            for cid in charger_ids:
                click.echo(str(cid))
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


@charger.command("status")
@click.argument("charger_id", type=int)
@click.pass_context
@async_cmd
async def charger_status(ctx, charger_id: int) -> None:
    """Show home charger status and amperage settings."""
    client = await _make_client(ctx.obj["debug"])
    try:
        status = await client.get_home_charger_status(charger_id)
        if ctx.obj["as_json"]:
            _dump_json(status)
        else:
            click.echo(f"Charger:     {charger_id}")
            click.echo(f"Brand/Model: {status.brand or '—'} {status.model}")
            click.echo(f"Status:      {status.charging_status}")
            click.echo(f"Plugged In:  {status.is_plugged_in}")
            click.echo(f"Connected:   {status.is_connected}")
            click.echo(f"Amperage:    {status.amperage_limit} A")
            click.echo(f"Possible:    {status.possible_amperage_limits}")
            if status.is_reminder_enabled:
                click.echo(f"Reminder:    {status.plug_in_reminder_time}")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


@charger.command("tech-info")
@click.argument("charger_id", type=int)
@click.pass_context
@async_cmd
async def charger_tech_info(ctx, charger_id: int) -> None:
    """Show home charger technical information."""
    client = await _make_client(ctx.obj["debug"])
    try:
        info = await client.get_home_charger_technical_info(charger_id)
        if ctx.obj["as_json"]:
            _dump_json(info)
        else:
            click.echo(f"Model:        {info.model_number}")
            click.echo(f"Serial:       {info.serial_number}")
            click.echo(f"MAC:          {info.mac_address}")
            click.echo(f"WiFi MAC:     {info.wifi_mac}")
            click.echo(f"Firmware:     {info.software_version}")
            click.echo(f"Last OTA:     {info.last_ota_update.strftime('%Y-%m-%d %H:%M %Z')}")
            click.echo(f"Last Seen:    {info.last_connected_at.strftime('%Y-%m-%d %H:%M %Z')}")
            click.echo(f"Stop Charge:  {info.stop_charge_supported}")
            if info.device_ip:
                click.echo(f"IP:           {info.device_ip}")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


@charger.command("config")
@click.argument("charger_id", type=int)
@click.pass_context
@async_cmd
async def charger_config(ctx, charger_id: int) -> None:
    """Show home charger configuration."""
    client = await _make_client(ctx.obj["debug"])
    try:
        config = await client.get_home_charger_config(charger_id)
        if ctx.obj["as_json"]:
            _dump_json(config)
        else:
            click.echo(f"Serial:      {config.serial_number}")
            click.echo(f"MAC:         {config.mac_address}")
            click.echo(f"Nickname:    {config.station_nickname or '—'}")
            click.echo(f"Address:     {config.street_address or '—'}")
            click.echo(f"LED Level:   {config.led_brightness.level} "
                       f"(options: {config.led_brightness.supported_levels})")
            click.echo(f"LED Enabled: {config.led_brightness.is_enabled}")
            if config.utility:
                click.echo(f"Utility:     {config.utility.name}")
                for plan in config.utility.plans:
                    click.echo(f"  Plan: {plan.name} (EV plan: {plan.is_ev_plan})")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


@charger.command("set-amperage")
@click.argument("charger_id", type=int)
@click.argument("amps", type=int)
@click.pass_context
@async_cmd
async def charger_set_amperage(ctx, charger_id: int, amps: int) -> None:
    """Set the charge amperage limit for a home charger."""
    client = await _make_client(ctx.obj["debug"])
    try:
        await client.set_amperage_limit(charger_id, amps)
        click.echo(f"Amperage limit set to {amps} A.")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


@charger.command("set-led")
@click.argument("charger_id", type=int)
@click.argument("level", type=click.IntRange(0, 5))
@click.pass_context
@async_cmd
async def charger_set_led(ctx, charger_id: int, level: int) -> None:
    """Set LED brightness level (0=off, 1=20%, 2=40%, 3=60%, 4=80%, 5=100%)."""
    client = await _make_client(ctx.obj["debug"])
    try:
        await client.set_led_brightness(charger_id, level)
        labels = {0: "off", 1: "20%", 2: "40%", 3: "60%", 4: "80%", 5: "100%"}
        click.echo(f"LED brightness set to level {level} ({labels[level]}).")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


@charger.command("restart")
@click.argument("charger_id", type=int)
@click.confirmation_option(prompt="Send restart command to charger?")
@click.pass_context
@async_cmd
async def charger_restart(ctx, charger_id: int) -> None:
    """Send a restart command to a home charger."""
    client = await _make_client(ctx.obj["debug"])
    try:
        await client.restart_home_charger(charger_id)
        click.echo("Restart command sent.")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# session subgroup
# ---------------------------------------------------------------------------

@cli.group()
def session() -> None:
    """Charging session management."""
    pass


@session.command("get")
@click.argument("session_id", type=int)
@click.pass_context
@async_cmd
async def session_get(ctx, session_id: int) -> None:
    """Show details of a charging session."""
    client = await _make_client(ctx.obj["debug"])
    try:
        s = await client.get_charging_session(session_id)
        if ctx.obj["as_json"]:
            _dump_json(s)
        else:
            click.echo(f"Session:   {s.session_id}")
            click.echo(f"Device:    {s.device_id} — {s.device_name}")
            click.echo(f"State:     {s.charging_state}")
            click.echo(f"Started:   {s.start_time.strftime('%Y-%m-%d %H:%M %Z')}")
            click.echo(f"Energy:    {s.energy_kwh:.3f} kWh")
            click.echo(f"Power:     {s.power_kw:.1f} kW")
            click.echo(f"Miles:     +{s.miles_added:.1f} mi")
            click.echo(f"Cost:      {s.total_amount} {s.currency_iso_code}")
            click.echo(f"Location:  {s.address}, {s.city}, {s.state_name}")
            if s.vehicle_info:
                click.echo(f"Vehicle:   {s.vehicle_info.year} {s.vehicle_info.make} {s.vehicle_info.model}")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


@session.command("start")
@click.argument("device_id", type=int)
@click.pass_context
@async_cmd
async def session_start(ctx, device_id: int) -> None:
    """Start a charging session on a device."""
    client = await _make_client(ctx.obj["debug"])
    try:
        s = await client.start_charging_session(device_id=device_id)
        if ctx.obj["as_json"]:
            _dump_json(s)
        else:
            click.echo(f"Session started: {s.session_id}")
            click.echo(f"State: {s.charging_state}")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


@session.command("stop")
@click.argument("session_id", type=int)
@click.confirmation_option(prompt="Stop this charging session?")
@click.pass_context
@async_cmd
async def session_stop(ctx, session_id: int) -> None:
    """Stop an active charging session."""
    client = await _make_client(ctx.obj["debug"])
    try:
        s = await client.get_charging_session(session_id)
        await s.stop()
        click.echo("Session stopped.")
    except CommunicationError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
