import logging
from datetime import datetime
from typing import Optional

import pytest
import responses

from python_chargepoint import ChargePoint
from python_chargepoint.session import ChargingSession, _modify
from python_chargepoint.exceptions import ChargePointCommunicationException


def _add_start_function_responses(session_id: Optional[int] = 12345) -> None:
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/station/startsession",
        status=200,
        json={"ackId": 1},
    )
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/station/session/ack",
        status=403,
        json={"error": "failed to start session"},
    )
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/station/session/ack",
        status=200,
        json={"sessionId": session_id},
    )


@responses.activate
def test_get_session(charging_session: ChargingSession, timestamp: datetime):
    assert charging_session.session_id == 1
    assert charging_session.utility.name == "Power Company"
    assert len(charging_session.update_data) == 1
    assert charging_session.update_data[0].timestamp == timestamp


def test_modify_invalid_action():
    with pytest.raises(AttributeError):
        _modify(action="invalid", client=None, device_id=1)


@responses.activate
def test_stop_session_failure(charging_session: ChargingSession):
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/station/stopSession",
        status=400,
    )

    with pytest.raises(ChargePointCommunicationException) as exc:
        charging_session.stop()

    assert exc.value.response.status_code == 400


@responses.activate
def test_stop_session(charging_session: ChargingSession, caplog):
    caplog.set_level(logging.INFO)
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/station/stopSession",
        status=200,
        json={"ackId": 1},
    )
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/station/session/ack",
        status=403,
        json={"error": "failed to stop session"},
    )
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/station/session/ack",
        status=200,
        json={},
    )

    assert charging_session.stop() is None
    assert "Successfully confirmed stop command." in caplog.text


@responses.activate
def test_stop_session_exceed_retry(charging_session: ChargingSession):
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/station/stopSession",
        status=200,
        json={"ackId": 1},
    )
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/station/session/ack",
        status=403,
        json={"error": "attempt 1"},
    )
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/station/session/ack",
        status=403,
        json={"error": "attempt 2"},
    )
    with pytest.raises(ChargePointCommunicationException) as exc:
        charging_session.stop(max_retry=2)

    assert exc.value.response.json()["error"] == "attempt 2"


@responses.activate
def test_start_session(
    authenticated_client: ChargePoint,
    charging_session: ChargingSession,
    user_charging_status_json: dict,
    charging_status_json: dict,
    caplog,
):
    caplog.set_level(logging.INFO)
    _add_start_function_responses()

    responses.add(
        responses.POST,
        "https://mc.chargepoint.com/map-prod/v2",
        status=200,
        json={"user_status": user_charging_status_json},
    )
    responses.add(
        responses.GET,
        "https://mc.chargepoint.com/map-prod/v2?%7B%22user_id%22%3A1%2C%22charging_status"
        + "%22%3A%7B%22mfhs%22%3A%7B%7D%2C%22session_id%22%3A1%7D%7D",
        status=200,
        json={
            "charging_status": charging_status_json,
        },
    )

    new = charging_session.start(client=authenticated_client, device_id=1)
    assert new.session_id == 1
    assert "Successfully confirmed start command." in caplog.text


@responses.activate
def test_get_session_eventual_consistency(
    authenticated_client: ChargePoint,
    user_charging_status_json: dict,
    charging_status_json: dict,
):
    _add_start_function_responses()

    responses.add(
        responses.POST,
        "https://mc.chargepoint.com/map-prod/v2",
        status=200,
        json={"user_status": user_charging_status_json},
    )
    responses.add(
        responses.GET,
        "https://mc.chargepoint.com/map-prod/v2?%7B%22user_id%22%3A1%2C%22charging_status"
        + "%22%3A%7B%22mfhs%22%3A%7B%7D%2C%22session_id%22%3A1%7D%7D",
        status=200,
        json={"charging_status": {"error": "java.lang.NullPointerException"}},
    )
    responses.add(
        responses.GET,
        "https://mc.chargepoint.com/map-prod/v2?%7B%22user_id%22%3A1%2C%22charging_status"
        + "%22%3A%7B%22mfhs%22%3A%7B%7D%2C%22session_id%22%3A1%7D%7D",
        status=200,
        json={"charging_status": charging_status_json},
    )

    session = ChargingSession.start(device_id=1, client=authenticated_client)
    assert session.session_id == 1


@responses.activate
def test_get_session_eventual_consistency_failure(
    authenticated_client: ChargePoint, user_charging_status_json: dict
):
    _add_start_function_responses()

    responses.add(
        responses.POST,
        "https://mc.chargepoint.com/map-prod/v2",
        status=200,
        json={"user_status": user_charging_status_json},
    )
    for i in range(0, 12):
        responses.add(
            responses.GET,
            "https://mc.chargepoint.com/map-prod/v2?%7B%22user_id%22%3A1%2C%22charging_status"
            + "%22%3A%7B%22mfhs%22%3A%7B%7D%2C%22session_id%22%3A1%7D%7D",
            status=200,
            json={"charging_status": {"error": "java.lang.NullPointerException"}},
        )

    with pytest.raises(ChargePointCommunicationException) as exc:
        ChargingSession.start(device_id=1, client=authenticated_client)

    assert exc.value.response.status_code == 200


@responses.activate
def test_get_charging_session_error(authenticated_client: ChargePoint):
    responses.add(
        responses.GET,
        "https://mc.chargepoint.com/map-prod/v2?%7B%22user_id%22%3A1%2C%22charging_status"
        + "%22%3A%7B%22mfhs%22%3A%7B%7D%2C%22session_id%22%3A1%7D%7D",
        status=500,
    )

    with pytest.raises(ChargePointCommunicationException) as exc:
        authenticated_client.get_charging_session(session_id=1)

    assert exc.value.response.status_code == 500


@responses.activate
def test_get_charging_session_no_utility(
    authenticated_client: ChargePoint, charging_status_json: dict
):
    charging_status_json["utility"] = None

    responses.add(
        responses.GET,
        "https://mc.chargepoint.com/map-prod/v2?%7B%22user_id%22%3A1%2C%22charging_status"
        + "%22%3A%7B%22mfhs%22%3A%7B%7D%2C%22session_id%22%3A1%7D%7D",
        status=200,
        json={"charging_status": charging_status_json},
    )

    session = authenticated_client.get_charging_session(session_id=1)
    assert session.utility is None
