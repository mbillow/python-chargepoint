import pytest
import responses

from python_chargepoint import ChargePoint
from python_chargepoint.exceptions import (
    ChargePointLoginError,
    ChargePointCommunicationException,
)


@responses.activate
def test_client_auth_wrapper(authenticated_client: ChargePoint):
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v1/driver/profile/account/logout",
        json={},
    )

    authenticated_client.logout()
    with pytest.raises(RuntimeError):
        authenticated_client.get_home_chargers()


@responses.activate
def test_client_invalid_auth():
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v2/driver/profile/account/login",
        status=500,
    )

    with pytest.raises(ChargePointLoginError) as exc:
        ChargePoint("test", "demo")

    assert exc.value.response.status_code == 500


@responses.activate
def test_client_logout_failed(authenticated_client: ChargePoint):
    responses.add(
        responses.POST,
        "https://account.chargepoint.com/account/v2/driver/profile/account/logout",
        status=500,
    )

    with pytest.raises(ChargePointCommunicationException) as exc:
        authenticated_client.logout()

    assert exc.value.response.status_code == 500
