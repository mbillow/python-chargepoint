from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import aiohttp
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, Union

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from .client import ChargePoint

from .constants import _LOGGER
from .exceptions import APIError, CommunicationError
from .types import ChargingSessionUpdate, PowerUtility, VehicleInfo


async def _send_command(
    client: ChargePoint,
    action: str,
    device_id: int,
    port_number: int = 1,
    session_id: int = 0,
) -> None:
    if action not in ["start", "stop"]:
        raise AttributeError(f"Invalid action: {action}")

    request = {
        "deviceId": device_id,
    }

    if action == "stop":
        request["portNumber"] = port_number
        request["sessionId"] = session_id

    action_path = {
        "start": "startsession",
        "stop": "stopSession",
    }

    response = await client._request(
        "POST",
        client.global_config.endpoints.accounts_endpoint
        / f"v1/driver/station/{action_path[action]}",
        json=request,
    )

    if response.status != 200:
        text = await response.text()
        _LOGGER.error(
            "Failed to send command to station! status_code=%s err=%s",
            response.status,
            text,
        )
        raise CommunicationError(
            response=response, message=f"Failed to {action} ChargePoint session."
        )

    action_status = await response.json()
    ack_id = action_status.get("ackId")

    ack_request = {
        "ackId": ack_id,
        "action": f"{action}_session",
    }
    ack_url = (
        client.global_config.endpoints.accounts_endpoint
        / "v1/driver/station/session/ack"
    )

    ack_response: Optional[aiohttp.ClientResponse] = None
    body: dict = {}
    error_message = f"Session failed to {action}."
    error_id: Optional[int] = None
    error_category: Optional[str] = None

    for attempt in range(1, 21):
        _LOGGER.debug(
            "Checking station modification status for ackId=%s (attempt %d/20)",
            ack_id,
            attempt,
        )
        ack_response = await client._request("POST", ack_url, json=ack_request)

        if ack_response.status == 200:
            _LOGGER.info("Successfully confirmed %s command.", action)
            await ack_response.release()
            return

        try:
            body = await ack_response.json(content_type=None) or {}
        except Exception:
            body = {}
        error_message = body.get("errorMessage", f"Session failed to {action}.")
        error_id = body.get("errorId")
        error_category = body.get("errorCategory")
        _LOGGER.warning(
            "Station modification not yet confirmed (attempt %d/20): status_code=%s err=%s (id=%s, category=%s)",
            attempt,
            ack_response.status,
            error_message,
            error_id,
            error_category,
        )

        if attempt < 20:
            await asyncio.sleep(3)

    assert ack_response is not None
    _LOGGER.error(
        "Failed to confirm station modification after 20 attempts: err=%s (id=%s, category=%s)",
        error_message,
        error_id,
        error_category,
    )
    full_message = (
        f"[{error_category}] {error_message}" if error_category else error_message
    )
    raise CommunicationError(
        response=ack_response,
        message=full_message,
        body=body,
    )


class _ChargingStatusData(BaseModel):
    """Parses the charging_status payload from the driver-bff API."""

    start_time: datetime
    device_id: int = 0
    device_name: str = ""
    charging_state: str = Field("", alias="current_charging")
    charging_time: int = 0
    energy_kwh: float = 0.0
    miles_added: float = 0.0
    miles_added_per_hour: float = 0.0
    outlet_number: int = 0
    port_level: int = 0
    power_kw: float = 0.0
    purpose: str = ""
    currency_iso_code: Union[str, int] = ""
    payment_completed: bool = False
    payment_type: str = ""
    pricing_spec_id: int = 0
    total_amount: float = 0.0
    api_flag: bool = False
    enable_stop_charging: bool = False
    has_charging_receipt: bool = False
    has_utility_info: bool = False
    is_home_charger: bool = False
    is_purpose_finalized: bool = False
    last_update_data_timestamp: datetime
    stop_charge_supported: bool = False
    company_id: int = 0
    company_name: str = ""
    latitude: float = Field(0.0, alias="lat")
    longitude: float = Field(0.0, alias="lon")
    address: str = Field("", alias="address1")
    city: str = ""
    state_name: str = ""
    country: str = ""
    zipcode: str = ""
    update_data: List[ChargingSessionUpdate] = Field(default_factory=list)
    update_period: int = 0
    utility: Optional[PowerUtility] = None
    vehicle_info: Optional[VehicleInfo] = None

    @field_validator("start_time", "last_update_data_timestamp", mode="before")
    @classmethod
    def parse_ms_timestamp(cls, v: float) -> datetime:
        return datetime.fromtimestamp(v / 1000, tz=timezone.utc)


@dataclass
class ChargingSession:
    session_id: int

    # Device Information
    device_id: int = 0
    device_name: str = ""
    charging_state: str = ""
    charging_time: int = 0
    energy_kwh: float = 0.0
    miles_added: float = 0.0
    miles_added_per_hour: float = 0.0
    outlet_number: int = 0
    port_level: int = 0
    power_kw: float = 0.0
    purpose: str = ""

    # Payment
    currency_iso_code: str = ""
    payment_completed: bool = False
    payment_type: str = ""
    pricing_spec_id: int = 0
    total_amount: float = 0.0

    # API / Misc.
    api_flag: bool = False
    enable_stop_charging: bool = False
    has_charging_receipt: bool = False
    has_utility_info: bool = False
    is_home_charger: bool = False
    is_purpose_finalized: bool = False
    stop_charge_supported: bool = False

    # Owner / Location
    company_id: int = 0
    company_name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    address: str = ""
    city: str = ""
    state_name: str = ""
    country: str = ""
    zipcode: str = ""

    # Session Update History
    update_period: int = 0

    # Typed as Optional since they're populated on first async_refresh()
    start_time: Optional[datetime] = None
    last_update_data_timestamp: Optional[datetime] = None
    update_data: Optional[List[ChargingSessionUpdate]] = None
    utility: Optional[PowerUtility] = None
    vehicle_info: Optional[VehicleInfo] = None

    _client: Optional[ChargePoint] = field(default=None, init=False, repr=False)

    def _apply(self, data: _ChargingStatusData) -> None:
        for field_name in _ChargingStatusData.model_fields:
            setattr(self, field_name, getattr(data, field_name))

    async def async_refresh(self) -> None:
        assert (
            self._client is not None
        ), "ChargingSession._client must be set before calling async_refresh()"
        _LOGGER.debug("Getting session information for session %s", self.session_id)

        response = await self._client._request(
            "POST",
            self._client.global_config.endpoints.internal_api_gateway_endpoint
            / f"driver-bff/v1/sessions/{self.session_id}",
            json={"charging_status": {"session_id": self.session_id, "mfhs": []}},
        )

        if response.status != 200:
            await response.release()
            raise CommunicationError(
                response=response, message="Failed to get charging session data."
            )

        json_data = await response.json()
        status = json_data.get("charging_status", {})

        if (
            "charging_status" not in json_data
            or "error_message" in status
            or "error" in status
        ):
            raise CommunicationError(
                response=response, message="Failed to get charging session data."
            )

        _LOGGER.debug("Passed session fetch: %s", json_data)
        self._apply(_ChargingStatusData.model_validate(status))

    async def stop(self) -> None:
        assert (
            self._client is not None
        ), "ChargingSession._client must be set before calling stop()"
        await _send_command(
            client=self._client,
            action="stop",
            device_id=self.device_id,
            port_number=self.outlet_number,
            session_id=self.session_id,
        )

    @classmethod
    async def start(cls, device_id: int, client: ChargePoint) -> ChargingSession:
        await _send_command(client=client, action="start", device_id=device_id)
        # So, after wayyy too much trial and error, I noticed that the "sessionId"
        # returned by the start session API is significantly higher than normal
        # session IDs... I have no clue what it means, so we are just going to
        # get the correct session ID from the status API.
        status = await client.get_user_charging_status()
        if status is None:
            raise APIError("No active charging session found after start command.")
        session = cls(session_id=status.session_id)
        session._client = client
        await session.async_refresh()
        return session
