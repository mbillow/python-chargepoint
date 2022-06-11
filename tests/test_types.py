from datetime import datetime
from python_chargepoint.types import (
    ElectricVehicle,
    ChargePointAccount,
    HomeChargerStatus,
    HomeChargerTechnicalInfo,
    UserChargingStatus,
)


def test_electric_vehicle_from_json(electric_vehicle_json: dict):
    ev = ElectricVehicle.from_json(electric_vehicle_json)

    assert ev.year == 2021
    assert ev.color == "Green"
    assert ev.make == "Pytest"
    assert ev.model == "Test"
    assert ev.charging_speed == 11.0
    assert ev.dc_charging_speed == 150.0
    assert ev.image_url == "https://pytest.com"
    assert ev.primary_vehicle is True


def test_account_from_json(account_json: dict):
    acct = ChargePointAccount.from_json(account_json)

    assert acct.user.email == "test@pytest.com"
    assert acct.user.evatar_url == "https://pytest.com"
    assert acct.user.family_name == "Test"
    assert acct.user.full_name == "Pytest Test"
    assert acct.user.given_name == "Pytest"
    assert acct.user.phone == "1234567890"
    assert acct.user.phone_country_id == 1
    assert acct.user.user_id == 1234567890
    assert acct.user.username == "pytest"

    assert acct.account_balance.account_number == "1234567890"
    assert acct.account_balance.account_state == "test"
    assert acct.account_balance.amount == "0.0"
    assert acct.account_balance.currency == "USD"


def test_home_charger_status_from_json(timestamp: datetime, home_charger_json: dict):
    home = HomeChargerStatus.from_json(charger_id=1, json=home_charger_json)

    assert home.charger_id == 1
    assert home.brand == "CP"
    assert home.plugged_in is True
    assert home.connected is True
    assert home.charging_status == "AVAILABLE"
    assert home.last_connected_at == timestamp
    assert home.reminder_enabled is False
    assert home.reminder_time == "0:00"
    assert home.model == "HOME FLEX"
    assert home.mac_address == "00:00:00:00:00:00"


def test_home_charger_technical_info_from_json(
    timestamp: datetime, home_charger_tech_info_json: dict
):
    tech = HomeChargerTechnicalInfo.from_json(home_charger_tech_info_json)

    assert tech.model == "CPH50-NEMA6-50-L23"
    assert tech.serial_number == "1234567890"
    assert tech.mac_address == "00:00:00:00:00:00"
    assert tech.software_version == "1.2.3.4"
    assert tech.last_ota_update == timestamp
    assert tech.device_ip == "10.0.0.1"
    assert tech.last_connected_at == timestamp
    assert tech.is_stop_charge_supported


def test_home_charger_technical_info_without_ip(home_charger_tech_info_json):
    del home_charger_tech_info_json["device_ip"]
    tech = HomeChargerTechnicalInfo.from_json(home_charger_tech_info_json)

    assert tech.device_ip is None


def test_user_charging_status_from_json(timestamp, user_charging_status_json: dict):
    status = UserChargingStatus.from_json(user_charging_status_json)

    assert status.session_id == 1
    assert status.start_time == timestamp
    assert status.state == "in_use"
    assert len(status.stations) == 1
    assert status.stations[0].name == "CP HOME"
    assert status.stations[0].id == 1
    assert status.stations[0].latitude == 30.0
    assert status.stations[0].longitude == 70.0


def test_user_charging_status_unknown_state_from_json(caplog, timestamp):
    json = {
        "charging": {
            "sessionId": 1,
            "startTimeUTC": timestamp.timestamp(),
            "stations": [],
        }
    }

    UserChargingStatus.from_json(json)
    assert "Charging status returned without a state." in caplog.text
