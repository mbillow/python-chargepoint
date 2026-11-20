import logging
from datetime import datetime
from typing import Optional

import pytest

from python_chargepoint import ChargePoint, session as session_module
from python_chargepoint.exceptions import APIError, CommunicationError
from python_chargepoint.global_config import GlobalConfiguration
from python_chargepoint.session import ChargingSession, _send_command


def _add_start_function_responses(
    aioresponses,
    global_config: GlobalConfiguration,
    session_id: Optional[int] = 12345,
) -> None:
    aioresponses.post(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/station/startsession",
        status=200,
        payload={"ackId": 1},
    )
    aioresponses.post(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/station/session/ack",
        status=200,
        payload={"sessionId": session_id},
    )


async def test_get_session(charging_session: ChargingSession, timestamp: datetime):
    assert charging_session.session_id == 1
    assert charging_session.utility.name == "Power Company"
    assert len(charging_session.update_data) == 1
    assert charging_session.update_data[0].timestamp == timestamp


async def test_send_command_invalid_action():
    with pytest.raises(AttributeError):
        await _send_command(action="invalid", client=None, device_id=1)


async def test_stop_session_failure(
    aioresponses,
    global_config: GlobalConfiguration,
    charging_session: ChargingSession,
):
    aioresponses.post(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/station/stopSession",
        status=400,
    )

    with pytest.raises(CommunicationError) as exc:
        await charging_session.stop()

    assert exc.value.response.status == 400


async def test_stop_session(
    aioresponses,
    global_config: GlobalConfiguration,
    charging_session: ChargingSession,
    caplog,
):
    caplog.set_level(logging.INFO)
    aioresponses.post(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/station/stopSession",
        status=200,
        payload={"ackId": 1},
    )
    aioresponses.post(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/station/session/ack",
        status=200,
        payload={},
    )

    assert await charging_session.stop() is None
    assert "Successfully confirmed stop command." in caplog.text


async def test_stop_session_ack_failure(
    aioresponses,
    global_config: GlobalConfiguration,
    charging_session: ChargingSession,
):
    aioresponses.post(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/station/stopSession",
        status=200,
        payload={"ackId": 1},
    )
    aioresponses.post(
        f"{global_config.endpoints.accounts_endpoint}v1/driver/station/session/ack",
        status=403,
        payload={"error": "failed to stop session"},
    )

    with pytest.raises(CommunicationError):
        await charging_session.stop()


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
        authenticated_client.global_config.endpoints.internal_api_gateway_endpoint
        / "driver-bff/v1/sessions/1",
        status=200,
        payload={"charging_status": charging_status_json},
    )

    new = await ChargingSession.start(client=authenticated_client, device_id=1)
    assert new.session_id == 1
    assert "Successfully confirmed start command." in caplog.text


@pytest.mark.parametrize("pending", ["missing", "wrong_device", "missing_details"])
async def test_start_polls_until_requested_session_is_visible(
    aioresponses,
    authenticated_client,
    user_charging_status_json,
    charging_status_json,
    monkeypatch,
    pending,
):
    monkeypatch.setattr(session_module, "_START_SESSION_POLL_INTERVAL", 0)
    config = authenticated_client.global_config
    _add_start_function_responses(aioresponses, config)
    status_url = config.endpoints.mapcache_endpoint / "v2"
    session_url = (
        config.endpoints.internal_api_gateway_endpoint / "driver-bff/v1/sessions"
    )
    first_status = {}
    if pending == "wrong_device":
        first_status = {
            "charging": {**user_charging_status_json["charging"], "sessionId": 2}
        }
        aioresponses.post(
            session_url / "2",
            payload={"charging_status": {**charging_status_json, "device_id": 2}},
        )
    elif pending == "missing_details":
        first_status = user_charging_status_json
        aioresponses.post(
            session_url / "1",
            payload={"charging_status": {"error_message": "Session data pending"}},
        )
    aioresponses.post(status_url, payload={"user_status": first_status})
    aioresponses.post(status_url, payload={"user_status": user_charging_status_json})
    aioresponses.post(
        session_url / "1", payload={"charging_status": charging_status_json}
    )

    session = await authenticated_client.start_charging_session(device_id=1)
    assert (session.session_id, session.device_id) == (1, 1)
    start_url = config.endpoints.accounts_endpoint / "v1/driver/station/startsession"
    starts = aioresponses.requests[("POST", start_url)]
    assert [request.kwargs["json"] for request in starts] == [{"deviceId": 1}]
    assert len(aioresponses.requests[("POST", status_url)]) == 2


async def test_acknowledged_start_with_no_session_times_out_without_resending(
    aioresponses, authenticated_client, monkeypatch
):
    monkeypatch.setattr(session_module, "_START_SESSION_POLL_INTERVAL", 0.005)
    monkeypatch.setattr(session_module, "_START_SESSION_LOOKUP_TIMEOUT", 0.05)
    config = authenticated_client.global_config
    _add_start_function_responses(aioresponses, config)
    status_url = config.endpoints.mapcache_endpoint / "v2"
    aioresponses.post(status_url, payload={"user_status": {}}, repeat=True)

    with pytest.raises(APIError, match="Start was acknowledged"):
        await authenticated_client.start_charging_session(device_id=1)

    start_url = config.endpoints.accounts_endpoint / "v1/driver/station/startsession"
    starts = aioresponses.requests[("POST", start_url)]
    assert [request.kwargs["json"] for request in starts] == [{"deviceId": 1}]
    assert ("POST", status_url) in aioresponses.requests


async def test_get_charging_session_error(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.post(
        authenticated_client.global_config.endpoints.internal_api_gateway_endpoint
        / "driver-bff/v1/sessions/1",
        status=500,
    )

    with pytest.raises(CommunicationError) as exc:
        await authenticated_client.get_charging_session(session_id=1)

    assert exc.value.response.status == 500


async def test_get_charging_session_error_body(
    aioresponses, authenticated_client: ChargePoint
):
    aioresponses.post(
        authenticated_client.global_config.endpoints.internal_api_gateway_endpoint
        / "driver-bff/v1/sessions/1",
        status=200,
        payload={"charging_status": {"error": "java.lang.NullPointerException"}},
    )

    with pytest.raises(CommunicationError):
        await authenticated_client.get_charging_session(session_id=1)


async def test_get_charging_session_no_utility(
    aioresponses, authenticated_client: ChargePoint, charging_status_json: dict
):
    charging_status_json["utility"] = None

    aioresponses.post(
        authenticated_client.global_config.endpoints.internal_api_gateway_endpoint
        / "driver-bff/v1/sessions/1",
        status=200,
        payload={"charging_status": charging_status_json},
    )

    session = await authenticated_client.get_charging_session(session_id=1)
    assert session.utility is None


async def test_get_charging_session_no_pricing_spec_id(
    aioresponses, authenticated_client: ChargePoint, charging_status_partial_json: dict
):
    aioresponses.post(
        authenticated_client.global_config.endpoints.internal_api_gateway_endpoint
        / "driver-bff/v1/sessions/1",
        status=200,
        payload={"charging_status": charging_status_partial_json},
    )

    session = await authenticated_client.get_charging_session(session_id=1)
    assert session.pricing_spec_id == 0
