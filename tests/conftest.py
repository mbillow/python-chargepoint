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
def station_info_json():
    return {
        "name": ["TEST STATION", "PORT A"],
        "deviceId": 99991111,
        "address": {"address1": "1 Test Ave", "city": "Testville", "state": "Teststate"},
        "description": "Test level 2 station",
        "modelNumber": "CT4020-HD-GW",
        "network": {
            "name": "ChargePoint Network",
            "displayName": "ChargePoint Network",
            "logoUrl": "https://example.com/logo.png",
            "inNetwork": True,
        },
        "portsInfo": {
            "ports": [
                {
                    "outletNumber": 1,
                    "powerRange": {"unit": "kW", "max": "7.2"},
                    "status": "available",
                    "statusV2": "available",
                    "displayLevel": "AC",
                    "level": "L2",
                    "parkingAccessibility": "NONE",
                    "connectorList": [
                        {
                            "status": "available",
                            "statusV2": "available",
                            "displayPlugType": "J1772",
                            "plugType": "J1772",
                        }
                    ],
                }
            ],
            "portCount": 1,
            "dc": False,
        },
        "stationStatus": "available",
        "stationStatusV2": "available",
        "latitude": 0.1,
        "longitude": 0.1,
        "hostName": "Test Host",
        "openCloseStatus": "open",
        "maxPower": {"unit": "kW", "max": "7.2"},
        "accessRestriction": "NONE",
        "parkingAccessibility": "NONE",
        "stopChargeSupported": True,
        "remoteStartCharge": True,
        "stationPrice": {
            "currencyCode": "USD",
            "energyFee": {
                "touFeeList": [
                    {"day": "alldays", "startTime": 0, "endTime": 0, "fee": {"amount": 0.10, "unit": "KWH"}}
                ]
            },
            "guestFee": {"amount": 0.99, "unit": "SESSION"},
            "taxes": [{"name": "State Tax", "percent": 6.25}],
        },
        "deviceSoftwareVersion": "V4.6.0.95",
        "lastChargedDate": "2026-01-01",
    }


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
def nearby_stations_json():
    return {
        "map_data": {
            "favorites": [],
            "stations": [
                {
                    "device_id": 99991111,
                    "lat": 0.1,
                    "lon": 0.1,
                    "name1": "TEST STATION",
                    "name2": "UNIT A",
                    "address1": "1 Test Ave",
                    "city": "Testville",
                    "network_display_name": "ChargePoint Network",
                    "station_status": "available",
                    "station_status_v2": "available",
                    "payment_type": "paid",
                    "total_port_count": 2,
                    "ports": [
                        {
                            "status_v2": "available",
                            "port_type": 3,
                            "outlet_number": 1,
                            "parking_accessibility": "NONE",
                            "available_power": "7.2",
                            "status": "available",
                        }
                    ],
                    "has_l2": True,
                    "max_power": {"unit": "kW", "max": 7.2},
                    "can_remote_start_charge": True,
                    "waitlist_allowed": False,
                    "access_restriction": "NONE",
                },
                {
                    "device_id": 99992222,
                    "lat": 0.2,
                    "lon": 0.2,
                    "station_status": "in_use",
                    "station_status_v2": "in_use",
                    "payment_type": "free",
                    "is_home": True,
                    "charging_status": "fully_charged",
                    "charging_info": {
                        "session_id": 1000000001,
                        "session_time": 3600000,
                        "energy_kwh": 10.5,
                        "energy_kwh_display": "10.5",
                        "currency_iso_code": "USD",
                        "current_charging": "fully_charged",
                        "miles_added": 40.0,
                        "total_amount": 0.0,
                        "payment_type": "none",
                        "start_time": 1000000000000,
                        "last_update_data_timestamp": 1000003600000,
                        "utility": {"id": 1, "name": "Test Utility", "plans": []},
                        "vehicle_info": {
                            "vehicle_id": 1111,
                            "make": "TestMake",
                            "model": "TestModel",
                            "year": 2024,
                            "ev_range": 300,
                            "battery_capacity": 75.0,
                            "is_primary_vehicle": True,
                        },
                    },
                    "total_port_count": 1,
                    "ports": [],
                    "has_l2": True,
                },
            ],
        }
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
