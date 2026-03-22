import json
from datetime import datetime, timezone

import pytest
from aioresponses import aioresponses as _aioresponses

from python_chargepoint import ChargePoint
from python_chargepoint.global_config import GlobalConfiguration
from python_chargepoint.constants import DISCOVERY_API


@pytest.fixture
def aioresponses():
    with _aioresponses() as m:
        yield m


@pytest.fixture(scope="session")
def timestamp() -> datetime:
    return datetime.now(tz=timezone.utc)


@pytest.fixture(scope="session")
def global_config_json():
    with open("tests/example/global_config.json") as file:
        return json.load(file)


@pytest.fixture
def user_charging_status_json(timestamp: datetime):
    return {
        "charging": {
            "sessionId": 1,
            "state": "in_use",
            "startTimeUTC": timestamp.timestamp(),
            "stations": [
                {
                    "deviceId": 1,
                    "name": "CP HOME",
                    "lat": 30.0,
                    "lon": 70.0,
                }
            ],
        }
    }


@pytest.fixture(scope="session")
def global_config(global_config_json) -> GlobalConfiguration:
    return GlobalConfiguration.model_validate(global_config_json)


@pytest.fixture
async def authenticated_client(aioresponses, global_config_json) -> ChargePoint:
    aioresponses.post(DISCOVERY_API, status=200, payload=global_config_json)
    aioresponses.get(
        "https://account.chargepoint.com/account/v1/driver/profile/user",
        status=200,
        payload={
            "user": {
                "email": "test@pytest.com",
                "evatarUrl": "https://pytest.com",
                "familyName": "Test",
                "fullName": "Test User",
                "givenName": "Test",
                "phone": "1234567890",
                "phoneCountryId": 1,
                "userId": 1,
                "username": "test",
            },
            "accountBalance": {
                "accountNumber": "1",
                "accountState": "test",
                "balance": {"amount": "0.0", "currency": "USD"},
            },
        },
    )

    client = await ChargePoint.create(
        username="test",
        coulomb_token="rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US",
    )
    yield client
    await client.close()


@pytest.fixture
def electric_vehicle_json():
    return {
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


@pytest.fixture
def account_json():
    return {
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


@pytest.fixture
def home_charger_json():
    return {
        "brand": "CP",
        "isPluggedIn": True,
        "isConnected": True,
        "chargingStatus": "AVAILABLE",
        "isReminderEnabled": False,
        "plugInReminderTime": "0:00",
        "model": "HOME FLEX",
        "macAddress": "00:00:00:00:00:00",
        "hasUtilityInfo": False,
        "isDuringScheduledTime": False,
        "chargeAmperageSettings": {
            "chargeLimit": 28,
            "inProgress": False,
            "possibleChargeLimit": [
                20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32,
            ],
        },
    }


@pytest.fixture
def home_charger_tech_info_json(timestamp: datetime):
    return {
        "modelNumber": "CPH50-NEMA6-50-L23",
        "serialNumber": "1234567890",
        "wifiMac": "00:00:00:00:00:00",
        "macAddress": "00:00:00:00:00:00",
        "softwareVersion": "1.2.3.4",
        "lastOtaUpdate": timestamp.timestamp() * 1000,
        "deviceIp": "10.0.0.1",
        "lastConnectedAt": timestamp.timestamp() * 1000,
        "stopChargeSupported": True,
    }


@pytest.fixture
def charging_status_json(timestamp: datetime) -> dict:
    return {
        "start_time": timestamp.timestamp() * 1000,
        "device_id": 1,
        "device_name": "CP HOME",
        "current_charging": "CHARGING",
        "charging_time": 1,
        "energy_kwh": 1.1,
        "miles_added": 1.1,
        "miles_added_per_hour": 0.0,
        "outlet_number": 1,
        "port_level": 2,
        "power_kw": 10.1,
        "purpose": "PERSONAL",
        "currency_iso_code": 1,
        "payment_completed": True,
        "payment_type": "CARD",
        "pricing_spec_id": 1,
        "total_amount": 0.0,
        "api_flag": False,
        "enable_stop_charging": True,
        "has_charging_receipt": False,
        "has_utility_info": True,
        "is_home_charger": True,
        "is_purpose_finalized": True,
        "last_update_data_timestamp": timestamp.timestamp() * 1000,
        "stop_charge_supported": True,
        "company_id": 1,
        "company_name": "CP",
        "lat": 30.0,
        "lon": 70.0,
        "address1": "123 Main St.",
        "city": "Pytest",
        "state_name": "New York",
        "country": "US",
        "zipcode": "12345",
        "update_data": [
            {
                "energy_kwh": 1.0,
                "power_kw": 11.0,
                "timestamp": timestamp.timestamp() * 1000,
            }
        ],
        "update_period": 1,
        "utility": {
            "id": 1,
            "name": "Power Company",
            "plans": [
                {
                    "id": 1,
                    "name": "Power Plan",
                    "code": 1,
                    "is_ev_plan": False,
                }
            ],
        },
    }


@pytest.fixture
def charging_status_partial_json(timestamp: datetime) -> dict:
    return {
        "start_time": timestamp.timestamp() * 1000,
        "device_id": 1,
        "device_name": "CP PUBLIC",
        "current_charging": "CHARGING",
        "charging_time": 1,
        "energy_kwh": 1.1,
        "miles_added": 1.1,
        "miles_added_per_hour": 0.0,
        "outlet_number": 1,
        "port_level": 2,
        "power_kw": 10.1,
        "purpose": "PERSONAL",
        "currency_iso_code": 1,
        "payment_completed": True,
        "payment_type": "CARD",
        "total_amount": 0.0,
        "api_flag": False,
        "enable_stop_charging": True,
        "has_charging_receipt": False,
        "is_purpose_finalized": True,
        "last_update_data_timestamp": timestamp.timestamp() * 1000,
        "stop_charge_supported": True,
        "company_id": 1,
        "company_name": "CP",
        "lat": 30.0,
        "lon": 70.0,
        "address1": "123 Main St.",
        "city": "Pytest",
        "state_name": "New York",
        "country": "US",
        "zipcode": "12345",
        "update_data": [
            {
                "energy_kwh": 1.0,
                "power_kw": 11.0,
                "timestamp": timestamp.timestamp() * 1000,
            }
        ],
        "update_period": 1,
    }


@pytest.fixture
async def charging_session(
    aioresponses, authenticated_client: ChargePoint, charging_status_json: dict
):
    aioresponses.post(
        "https://internal-api-us.chargepoint.com/driver-bff/v1/sessions/1",
        status=200,
        payload={"charging_status": charging_status_json},
    )

    return await authenticated_client.get_charging_session(session_id=1)
