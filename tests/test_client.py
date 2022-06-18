import logging

import pytest
import responses

from python_chargepoint import ChargePoint
from python_chargepoint.global_config import ChargePointGlobalConfiguration
from python_chargepoint.constants import DISCOVERY_API
from python_chargepoint.exceptions import (
    ChargePointLoginError,
    ChargePointCommunicationException,
    ChargePointInvalidSession,
    ChargePointBaseException,
)

from .test_session import _add_start_function_responses


@responses.activate
def test_client_auth_wrapper(authenticated_client: ChargePoint):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.accounts}v1/driver/profile/account/logout",
        json={},
    )

    authenticated_client.logout()
    with pytest.raises(RuntimeError):
        authenticated_client.get_home_chargers()


@responses.activate
def test_client_invalid_auth(
    global_config_json: dict, global_config: ChargePointGlobalConfiguration
):
    responses.add(responses.POST, DISCOVERY_API, status=200, json=global_config_json)
    responses.add(
        responses.POST,
        f"{global_config.endpoints.accounts}v2/driver/profile/account/login",
        status=500,
    )

    with pytest.raises(ChargePointLoginError) as exc:
        ChargePoint("test", "demo")

    assert exc.value.response.status_code == 500


@responses.activate
def test_client_unable_to_discover():
    responses.add(responses.POST, DISCOVERY_API, status=500)
    with pytest.raises(ChargePointCommunicationException) as exc:
        ChargePoint("foo", "bar")

    assert exc.value.response.status_code == 500


@responses.activate
def test_client_expired_session(
    global_config_json: dict,
    global_config: ChargePointGlobalConfiguration,
    account_json: dict,
):
    responses.add(responses.POST, DISCOVERY_API, status=200, json=global_config_json)
    responses.add(
        responses.GET,
        f"{global_config.endpoints.accounts}v1/driver/profile/user",
        status=200,
        json=account_json,
    )
    responses.add(
        responses.GET,
        f"{global_config.endpoints.accounts}v1/driver/profile/user",
        status=401,
    )

    client = ChargePoint(
        username="test",
        password="demo",
        session_token="rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US",
    )
    with pytest.raises(ChargePointInvalidSession) as exc:
        client.get_account()

    assert exc.value.response.status_code == 401


@responses.activate
def test_client_invalid_token_format(global_config_json: dict):
    responses.add(responses.POST, DISCOVERY_API, status=200, json=global_config_json)
    with pytest.raises(ChargePointBaseException):
        ChargePoint(username="test", password="demo", session_token="bad-token")


@responses.activate
def test_client_with_session_token(
    global_config_json: dict,
    global_config: ChargePointGlobalConfiguration,
    account_json: dict,
):
    responses.add(responses.POST, DISCOVERY_API, status=200, json=global_config_json)
    responses.add(
        responses.GET,
        f"{global_config.endpoints.accounts}v1/driver/profile/user",
        status=200,
        json=account_json,
    )

    session_token = "rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US"

    client = ChargePoint(username="test", password="demo", session_token=session_token)

    assert client.session_token == session_token
    assert client.user_id == str(account_json["user"]["userId"])


@responses.activate
def test_client_expired_session_token(
    global_config_json: dict,
    global_config: ChargePointGlobalConfiguration,
):
    session_token = "rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US"
    responses.add(responses.POST, DISCOVERY_API, status=200, json=global_config_json)
    responses.add(
        responses.GET,
        f"{global_config.endpoints.accounts}v1/driver/profile/user",
        status=401,
    )
    responses.add(
        responses.POST,
        f"{global_config.endpoints.accounts}v2/driver/profile/account/login",
        status=200,
        json={
            "user": {"userId": 1},
            "sessionId": session_token,
        },
    )

    client = ChargePoint(
        username="test",
        password="demo",
        session_token="expired#D???????#RNA-US",
    )

    assert client.session_token == session_token


@responses.activate
def test_client_logout_failed(authenticated_client: ChargePoint):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.accounts}v1/driver/profile/account/logout",
        status=500,
    )

    with pytest.raises(ChargePointCommunicationException) as exc:
        authenticated_client.logout()

    assert exc.value.response.status_code == 500


@responses.activate
def test_client_get_account(authenticated_client: ChargePoint, account_json: dict):
    responses.add(
        responses.GET,
        f"{authenticated_client.global_config.endpoints.accounts}v1/driver/profile/user",
        status=200,
        json=account_json,
    )

    acct = authenticated_client.get_account()
    assert acct.user.user_id == 1234567890


@responses.activate
def test_client_get_account_failure(authenticated_client: ChargePoint):
    responses.add(
        responses.GET,
        f"{authenticated_client.global_config.endpoints.accounts}v1/driver/profile/user",
        status=500,
    )

    with pytest.raises(ChargePointCommunicationException) as exc:
        authenticated_client.get_account()

    assert exc.value.response.status_code == 500


@responses.activate
def test_client_get_vehicles(
    authenticated_client: ChargePoint, electric_vehicle_json: dict
):
    responses.add(
        responses.GET,
        f"{authenticated_client.global_config.endpoints.accounts}v1/driver/vehicle",
        status=200,
        json=[electric_vehicle_json],
    )

    evs = authenticated_client.get_vehicles()
    assert len(evs) == 1
    assert evs[0].color == "Green"


@responses.activate
def test_client_get_vehicles_failure(authenticated_client: ChargePoint):
    responses.add(
        responses.GET,
        f"{authenticated_client.global_config.endpoints.accounts}v1/driver/vehicle",
        status=500,
    )

    with pytest.raises(ChargePointCommunicationException) as exc:
        authenticated_client.get_vehicles()

    assert exc.value.response.status_code == 500


@responses.activate
def test_client_get_home_chargers(authenticated_client: ChargePoint):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.webservices}mobileapi/v5",
        status=200,
        json={"get_pandas": {"device_ids": [1234567890]}},
    )

    chargers = authenticated_client.get_home_chargers()

    assert len(chargers) == 1
    assert chargers[0] == 1234567890


@responses.activate
def test_client_get_home_chargers_failure(authenticated_client: ChargePoint):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.webservices}mobileapi/v5",
        status=500,
    )

    with pytest.raises(ChargePointCommunicationException) as exc:
        authenticated_client.get_home_chargers()

    assert exc.value.response.status_code == 500


@responses.activate
def test_client_get_home_charger_status(
    authenticated_client: ChargePoint, home_charger_json: dict
):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.webservices}mobileapi/v5",
        status=200,
        json={"get_panda_status": home_charger_json},
    )

    charger = authenticated_client.get_home_charger_status(1234567890)

    assert charger.charger_id == 1234567890


@responses.activate
def test_client_get_home_charger_status_failure(authenticated_client: ChargePoint):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.webservices}mobileapi/v5",
        status=500,
    )

    with pytest.raises(ChargePointCommunicationException) as exc:
        authenticated_client.get_home_charger_status(1234567890)

    assert exc.value.response.status_code == 500


@responses.activate
def test_client_get_home_charger_technical_info(
    authenticated_client: ChargePoint, home_charger_tech_info_json: dict
):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.webservices}mobileapi/v5",
        status=200,
        json={"get_station_technical_info": home_charger_tech_info_json},
    )

    tech = authenticated_client.get_home_charger_technical_info(1234567890)

    assert tech.software_version == "1.2.3.4"


@responses.activate
def test_client_get_home_charger_technical_info_failure(
    authenticated_client: ChargePoint,
):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.webservices}mobileapi/v5",
        status=500,
    )

    with pytest.raises(ChargePointCommunicationException) as exc:
        authenticated_client.get_home_charger_technical_info(1234567890)

    assert exc.value.response.status_code == 500


@responses.activate
def test_client_get_user_charging_status(
    authenticated_client: ChargePoint, user_charging_status_json: dict
):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.mapcache}v2",
        status=200,
        json={"user_status": user_charging_status_json},
    )

    status = authenticated_client.get_user_charging_status()

    assert status is not None
    assert status.session_id == 1


@responses.activate
def test_client_get_user_charging_status_not_charging(
    authenticated_client: ChargePoint,
):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.mapcache}v2",
        status=200,
        json={"user_status": {}},
    )

    status = authenticated_client.get_user_charging_status()

    assert status is None


@responses.activate
def test_client_get_get_user_charging_status_failure(authenticated_client: ChargePoint):
    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.mapcache}v2",
        status=500,
    )

    with pytest.raises(ChargePointCommunicationException) as exc:
        authenticated_client.get_user_charging_status()

    assert exc.value.response.status_code == 500


@responses.activate
def test_start_session(
    authenticated_client: ChargePoint,
    user_charging_status_json: dict,
    charging_status_json: dict,
    caplog,
):
    caplog.set_level(logging.INFO)
    _add_start_function_responses(global_config=authenticated_client.global_config)

    responses.add(
        responses.POST,
        f"{authenticated_client.global_config.endpoints.mapcache}v2",
        status=200,
        json={"user_status": user_charging_status_json},
    )
    responses.add(
        responses.GET,
        f"{authenticated_client.global_config.endpoints.mapcache}v2?%7B%22user_id%22%3A1%2C%22charging_status"
        + "%22%3A%7B%22mfhs%22%3A%7B%7D%2C%22session_id%22%3A1%7D%7D",
        status=200,
        json={
            "charging_status": charging_status_json,
        },
    )

    new = authenticated_client.start_charging_session(device_id=1)
    assert new.session_id == 1
    assert "Successfully confirmed start command." in caplog.text
