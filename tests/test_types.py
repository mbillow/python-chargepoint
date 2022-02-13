from python_chargepoint.types import (
    ElectricVehicle,
    ChargePointAccount,
    HomeChargerStatus,
    UserChargingStatus,
)


def test_electric_vehicle_from_json():
    json = {
        "id": 0,
        "make": {"id": 0, "name": "Pytest"},
        "model": {"defaultSelect": False, "id": 1, "name": "Test"},
        "modelYear": {"chargingSpeed": 11.0, "dcChargingSpeed": 150.0, "year": 2021},
        "modelYearColor": {
            "colorId": 0,
            "colorName": "Green",
            "defaultSelect": False,
            "imageUrl": "https://pytest.com",
        },
        "primaryVehicle": True,
    }
    ev = ElectricVehicle.from_json(json)
    assert ev.year == 2021
    assert ev.color == "Green"
    assert ev.make == "Pytest"
    assert ev.model == "Test"
    assert ev.charging_speed == 11.0
    assert ev.dc_charging_speed == 150.0
    assert ev.image_url == "https://pytest.com"
    assert ev.primary_vehicle is True


def test_account_from_json():
    json = {
        "user": {
            "email": "test@pytest.com",
            "evatarUrl": "https://pytest.com",
            "familyName": "Test",
            "fullName": "Pytest Test",
            "givenName": "Pytest",
            "phone": "1234567890",
            "phoneCountryId": 1,
            "userId": 1234567890,
            "username": "pytest",
        },
        "accountBalance": {
            "accountNumber": "1234567890",
            "accountState": "test",
            "balance": {
                "amount": "0.0",
                "currency": "USD",
            },
        },
    }

    acct = ChargePointAccount.from_json(json)

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


def test_home_charger_status_from_json(timestamp):
    json = {
        "brand": "CP",
        "is_plugged_in": True,
        "is_connected": True,
        "charging_status": "AVAILABLE",
        "last_connected_at": timestamp.timestamp() * 1000,
        "is_reminder_enabled": False,
        "plug_in_reminder_time": "0:00",
        "model": "HOME FLEX",
        "mac_address": "00:00:00:00:00:00",
    }

    home = HomeChargerStatus.from_json(charger_id=1, json=json)

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
