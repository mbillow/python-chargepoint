import json
from datetime import datetime, timezone

import pytest
import responses

from python_chargepoint import ChargePoint
from python_chargepoint.global_config import ChargePointGlobalConfiguration
from python_chargepoint.constants import DISCOVERY_API


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
def global_config(global_config_json) -> ChargePointGlobalConfiguration:
    return ChargePointGlobalConfiguration.from_json(global_config_json)


@pytest.fixture
@responses.activate
def authenticated_client(global_config_json) -> ChargePoint:
    responses.add(responses.POST, DISCOVERY_API, status=200, json=global_config_json)
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v2/driver/profile/account/login",
        status=200,
        json={
            "user": {"userId": 1},
            "sessionId": "rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US",
        },
    )

    return ChargePoint(username="test", password="demo")


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
def home_charger_json(timestamp: datetime):
    return {
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


@pytest.fixture
def home_charger_tech_info_json(timestamp: datetime):
    return {
        "model_number": "CPH50-NEMA6-50-L23",
        "serial_number": "1234567890",
        "wifi_mac": "00:00:00:00:00:00",
        "mac_address": "00:00:00:00:00:00",
        "software_version": "1.2.3.4",
        "last_ota_update": timestamp.timestamp() * 1000,
        "device_ip": "10.0.0.1",
        "last_connected_at": timestamp.timestamp() * 1000,
        "is_stop_charge_supported": True,
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
@responses.activate
def charging_session(authenticated_client: ChargePoint, charging_status_json: dict):
    responses.add(
        responses.GET,
        "https://mc.chargepoint.com/map-prod/v2?%7B%22user_id%22%3A1%2C%22charging_status"
        + "%22%3A%7B%22mfhs%22%3A%7B%7D%2C%22session_id%22%3A1%7D%7D",
        status=200,
        json={
            "charging_status": charging_status_json,
        },
    )

    return authenticated_client.get_charging_session(session_id=1)
