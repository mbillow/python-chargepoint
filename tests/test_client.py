import logging

import pytest

from python_chargepoint import ChargePoint
from python_chargepoint.global_config import GlobalConfiguration
from python_chargepoint.constants import DISCOVERY_API
from python_chargepoint.exceptions import (
    LoginError,
    CommunicationError,
    InvalidSession,
)

from .test_session import _add_start_function_responses


async def test_client_auth_wrapper(aioresponses, authenticated_client: ChargePoint):
    aioresponses.post(
        f"{authenticated_client.global_config.endpoints.sso_endpoint}v1/user/logout",
        payload={},
    )

    await authenticated_client.logout()
    with pytest.raises(RuntimeError):
        await authenticated_client.get_home_chargers()


async def test_client_login_with_password_failure(
    aioresponses, global_config_json: dict, global_config: GlobalConfiguration
):
    aioresponses.post(DISCOVERY_API, status=200, payload=global_config_json)
    aioresponses.post(
        f"{global_config.endpoints.sso_endpoint}v1/user/login",
        status=500,
    )

    with pytest.raises(LoginError) as exc:
        client = await ChargePoint.create("test")
        await client.login_with_password("demo")

    assert exc.value.response.status == 500


async def test_client_login_with_password(
    aioresponses,
    global_config_json: dict,
    global_config: GlobalConfiguration,
    account_json: dict,
):
    coulomb_token = "rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US"
    aioresponses.post(DISCOVERY_API, status=200, payload=global_config_json)
    aioresponses.post(
        f"{global_config.endpoints.sso_endpoint}v1/user/login",
        status=200,
        headers={"Set-Cookie": f"coulomb_sess={coulomb_token}; Domain=.chargepoint.com; Path=/"},
    )
    aioresponses.get(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/profile/user",
        status=200,
        payload=account_json,
    )

    client = await ChargePoint.create("test")
    await client.login_with_password("demo")

    assert client.coulomb_token == coulomb_token
    assert client.user_id == account_json["user"]["userId"]


async def test_client_unable_to_discover(aioresponses):
    aioresponses.post(DISCOVERY_API, status=500)
    with pytest.raises(CommunicationError) as exc:
        await ChargePoint.create("foo", "bar")

    assert exc.value.response.status == 500


async def test_client_expired_session(
    aioresponses,
    global_config_json: dict,
    global_config: GlobalConfiguration,
    account_json: dict,
):
    aioresponses.post(DISCOVERY_API, status=200, payload=global_config_json)
    aioresponses.get(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/profile/user",
        status=200,
        payload=account_json,
    )
    aioresponses.get(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/profile/user",
        status=401,
    )

    client = await ChargePoint.create(
        username="test",
        coulomb_token="rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US",
    )
    with pytest.raises(InvalidSession) as exc:
        await client.get_account()

    assert exc.value.response.status == 401


async def test_client_with_coulomb_token(
    aioresponses,
    global_config_json: dict,
    global_config: GlobalConfiguration,
    account_json: dict,
):
    aioresponses.post(DISCOVERY_API, status=200, payload=global_config_json)
    aioresponses.get(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/profile/user",
        status=200,
        payload=account_json,
    )

    coulomb_token = "rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US"

    client = await ChargePoint.create(username="test", coulomb_token=coulomb_token)

    assert client.coulomb_token == coulomb_token
    assert client.user_id == account_json["user"]["userId"]


async def test_client_login_with_sso(
    aioresponses,
    global_config_json: dict,
    global_config: GlobalConfiguration,
    account_json: dict,
):
    coulomb_token = "rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US"
    aioresponses.post(DISCOVERY_API, status=200, payload=global_config_json)
    aioresponses.get(
        f"{global_config.endpoints.portal_domain_endpoint}index.php/nghelper/getSession",
        status=200,
        headers={"Set-Cookie": f"coulomb_sess={coulomb_token}; Domain=.chargepoint.com; Path=/"},
    )
    aioresponses.get(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/profile/user",
        status=200,
        payload=account_json,
    )

    client = await ChargePoint.create("test")
    await client.login_with_sso_session("some-sso-jwt")

    assert client.coulomb_token == coulomb_token
    assert client.user_id == account_json["user"]["userId"]


async def test_client_login_with_sso_failure(
    aioresponses,
    global_config_json: dict,
    global_config: GlobalConfiguration,
):
    aioresponses.post(DISCOVERY_API, status=200, payload=global_config_json)
    aioresponses.get(
        f"{global_config.endpoints.portal_domain_endpoint}index.php/nghelper/getSession",
        status=401,
    )

    with pytest.raises(InvalidSession):
        client = await ChargePoint.create("test")
        await client.login_with_sso_session("bad-jwt")


async def test_client_logout_failed(aioresponses, authenticated_client: ChargePoint):
    aioresponses.post(
        f"{authenticated_client.global_config.endpoints.sso_endpoint}v1/user/logout",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.logout()

    assert exc.value.response.status == 500


async def test_client_get_account(
    aioresponses, authenticated_client: ChargePoint, account_json: dict
):
    aioresponses.get(
        f"{authenticated_client.global_config.endpoints.accounts_endpoint}v1/driver/profile/user",
        status=200,
        payload=account_json,
    )

    acct = await authenticated_client.get_account()
    assert acct.user.user_id == 1234567890


async def test_client_get_account_failure(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.get(
        f"{authenticated_client.global_config.endpoints.accounts_endpoint}v1/driver/profile/user",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.get_account()

    assert exc.value.response.status == 500


async def test_client_get_vehicles(
    aioresponses, authenticated_client: ChargePoint, electric_vehicle_json: dict
):
    aioresponses.get(
        f"{authenticated_client.global_config.endpoints.accounts_endpoint}v1/driver/vehicle",
        status=200,
        payload=[electric_vehicle_json],
    )

    evs = await authenticated_client.get_vehicles()
    assert len(evs) == 1
    assert evs[0].color == "Green"


async def test_client_get_vehicles_failure(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.get(
        f"{authenticated_client.global_config.endpoints.accounts_endpoint}v1/driver/vehicle",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.get_vehicles()

    assert exc.value.response.status == 500


async def test_client_get_home_chargers(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.get(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/users/1/chargers",
        status=200,
        payload={"data": [{"id": "1234567890", "label": None, "protocolIdentifier": None, "coordinates": None, "location": None}], "pagination": {"nextCursor": "none"}},
    )

    chargers = await authenticated_client.get_home_chargers()

    assert len(chargers) == 1
    assert chargers[0] == 1234567890


async def test_client_get_home_chargers_failure(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.get(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/users/1/chargers",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.get_home_chargers()

    assert exc.value.response.status == 500


async def test_client_get_home_charger_status(
    aioresponses, authenticated_client: ChargePoint, home_charger_json: dict
):
    aioresponses.get(
        f"{authenticated_client.global_config.endpoints.hcpo_hcm_endpoint}api/v1/configuration/users/1/chargers/1234567890/status",
        status=200,
        payload=home_charger_json,
    )

    charger = await authenticated_client.get_home_charger_status(1234567890)

    assert charger.charger_id == 1234567890
    assert charger.amperage_limit == 28
    assert charger.is_plugged_in is True


async def test_client_get_home_charger_status_failure(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.get(
        f"{authenticated_client.global_config.endpoints.hcpo_hcm_endpoint}api/v1/configuration/users/1/chargers/1234567890/status",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.get_home_charger_status(1234567890)

    assert exc.value.response.status == 500


async def test_client_get_home_charger_technical_info(
    aioresponses,
    authenticated_client: ChargePoint,
    home_charger_tech_info_json: dict,
):
    aioresponses.get(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/users/1/chargers/1234567890/technical-info",
        status=200,
        payload=home_charger_tech_info_json,
    )

    tech = await authenticated_client.get_home_charger_technical_info(1234567890)

    assert tech.software_version == "1.2.3.4"
    assert tech.model_number == "CPH50-NEMA6-50-L23"
    assert tech.stop_charge_supported is True


async def test_client_get_home_charger_technical_info_failure(
    aioresponses,
    authenticated_client: ChargePoint,
):
    aioresponses.get(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/users/1/chargers/1234567890/technical-info",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.get_home_charger_technical_info(1234567890)

    assert exc.value.response.status == 500


async def test_client_get_user_charging_status(
    aioresponses,
    authenticated_client: ChargePoint,
    user_charging_status_json: dict,
):
    aioresponses.post(
        f"{authenticated_client.global_config.endpoints.mapcache_endpoint}v2",
        status=200,
        payload={"user_status": user_charging_status_json},
    )

    status = await authenticated_client.get_user_charging_status()

    assert status is not None
    assert status.session_id == 1


async def test_client_set_amperage_limit(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.put(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/chargers/1234567890/charge-amperage-limit",
        status=200,
        payload={"name": "Charge Amperage Limit", "desiredValue": "28", "status": "APPLYING"},
    )

    assert await authenticated_client.set_amperage_limit(1234567890, 28) is None

    aioresponses.put(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/chargers/1234567890/charge-amperage-limit",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.set_amperage_limit(1234567890, 0)

    assert exc.value.response.status == 500


async def test_client_set_led_brightness(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.put(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/chargers/1234567890/led-brightness",
        status=200,
        payload={"name": "LED Brightness", "desiredValue": "4", "status": "APPLYING"},
    )

    assert await authenticated_client.set_led_brightness(1234567890, 4) is None

    aioresponses.put(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/chargers/1234567890/led-brightness",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.set_led_brightness(1234567890, 4)

    assert exc.value.response.status == 500


async def test_client_get_user_charging_status_not_charging(
    aioresponses,
    authenticated_client: ChargePoint,
):
    aioresponses.post(
        f"{authenticated_client.global_config.endpoints.mapcache_endpoint}v2",
        status=200,
        payload={"user_status": {}},
    )

    status = await authenticated_client.get_user_charging_status()

    assert status is None


async def test_client_get_get_user_charging_status_failure(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.post(
        f"{authenticated_client.global_config.endpoints.mapcache_endpoint}v2",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.get_user_charging_status()

    assert exc.value.response.status == 500


async def test_client_restart_home_charger(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.post(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/users/1/chargers/1234567890/restart",
        status=200,
    )

    assert await authenticated_client.restart_home_charger(1234567890) is None


async def test_client_restart_home_charger_failure(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.post(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/users/1/chargers/1234567890/restart",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.restart_home_charger(1234567890)

    assert exc.value.response.status == 500


async def test_client_get_home_charger_config(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.get(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/users/1/chargers/1234567890/configurations",
        status=200,
        payload={
            "settings": {
                "serialNumber": "214841066755",
                "macAddress": "0024B100000698BA",
                "stationNickname": "ChargePoint Home",
                "streetAddress": "123 Main St",
                "hasUtilityInfo": True,
                "utility": {
                    "id": 22,
                    "name": "Austin Energy",
                    "plans": [{"id": 80693, "name": "Residential", "code": "R", "isEvPlan": False}],
                },
                "indicatorLightEcoMode": "OFF",
                "flashlightReset": False,
                "worksWithNest": False,
                "isPairedWithNest": False,
                "isInstalledByInstaller": False,
                "led": {
                    "brightness": {
                        "level": "5",
                        "inProgress": False,
                        "supportedLevels": ["0", "1", "2", "3", "4", "5"],
                        "isEnabled": True,

                    }
                },
            }
        },
    )

    config = await authenticated_client.get_home_charger_config(1234567890)

    assert config.serial_number == "214841066755"
    assert config.station_nickname == "ChargePoint Home"
    assert config.utility.name == "Austin Energy"
    assert config.led_brightness.level == 5
    assert config.led_brightness.supported_levels == [0, 1, 2, 3, 4, 5]


async def test_client_get_home_charger_config_failure(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.get(
        authenticated_client.global_config.endpoints.hcpo_hcm_endpoint / "api/v1/configuration/users/1/chargers/1234567890/configurations",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.get_home_charger_config(1234567890)

    assert exc.value.response.status == 500


async def test_start_session(
    aioresponses,
    authenticated_client: ChargePoint,
    user_charging_status_json: dict,
    charging_status_json: dict,
    caplog,
):
    caplog.set_level(logging.INFO)
    _add_start_function_responses(
        aioresponses=aioresponses,
        global_config=authenticated_client.global_config,
    )

    aioresponses.post(
        f"{authenticated_client.global_config.endpoints.mapcache_endpoint}v2",
        status=200,
        payload={"user_status": user_charging_status_json},
    )
    aioresponses.post(
        authenticated_client.global_config.endpoints.internal_api_gateway_endpoint / "driver-bff/v1/sessions/1",
        status=200,
        payload={"charging_status": charging_status_json},
    )

    new = await authenticated_client.start_charging_session(device_id=1)
    assert new.session_id == 1
    assert "Successfully confirmed start command." in caplog.text
