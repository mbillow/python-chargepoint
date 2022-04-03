from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Optional
from time import sleep

from requests import codes

from .constants import _LOGGER, MAP_URL
from .types import ChargingSessionUpdate, PowerUtility
from .exceptions import ChargePointCommunicationException


def _modify(
    client: "ChargePoint",  # noqa: F821
    action: str,
    device_id: int,
    port_number: int = 1,
    session_id: int = 0,
    max_retry: int = 30,
) -> Optional[int]:
    if action not in ["start", "stop"]:
        raise AttributeError(f"Invalid action: {action}")

    request = {
        "deviceData": client.device_data,
        "deviceId": device_id,
    }

    if action == "stop":
        request["portNumber"] = port_number
        request["sessionId"] = session_id

    action_path = {
        "start": "startsession",
        "stop": "stopSession",
    }

    response = client.session.post(
        f"https://account.chargepoint.com/account/v1/driver/station/{action_path[action]}",
        json=request,
    )

    if response.status_code != codes.ok:
        _LOGGER.error(
            "Failed to send command to station! status_code=%s err=%s",
            response.status_code,
            response.text,
        )
        raise ChargePointCommunicationException(
            response=response, message=f"Failed to {action} ChargePoint session."
        )

    action_status = response.json()
    ack_id = action_status["ackId"]

    for i in range(max_retry):  # pragma: no cover
        _LOGGER.debug(
            "Checking station modification status. (Attempt %d/%d)",
            i + 1,
            max_retry,
        )
        request = {
            "deviceData": client.device_data,
            "ackId": ack_id,
            "action": f"{action}_session",
        }
        response = client.session.post(
            "https://account.chargepoint.com/account/v1/driver/station/session/ack",
            json=request,
        )
        if response.status_code == codes.ok:
            _LOGGER.info("Successfully confirmed %s command.", action)

            # If we just started a new session, return the new ID.
            if action == "start":
                return response.json().get("sessionId")
            # Otherwise, just return.
            return

        if i == max_retry - 1:
            _LOGGER.error(
                "Failed to confirm station modification! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response,
                message=f"Session failed to {action} in time allotted.",
            )
        sleep(1)


@dataclass
class ChargingSession:
    session_id: int
    start_time: datetime

    # Device Information
    device_id: int
    device_name: str
    charging_state: str
    charging_time: int
    energy_kwh: float
    miles_added: float
    miles_added_per_hour: float
    outlet_number: int
    port_level: int
    power_kw: float
    purpose: str

    # Payment
    currency_iso_code: str
    payment_completed: bool
    payment_type: str
    pricing_spec_id: int
    total_amount: float

    # API / Misc.
    api_flag: bool
    enable_stop_charging: bool
    has_charging_receipt: bool
    has_utility_info: bool
    is_home_charger: bool
    is_purpose_finalized: bool
    last_update_data_timestamp: datetime
    stop_charge_supported: bool

    # Owner / Location
    company_id: int
    company_name: str
    latitude: float
    longitude: float
    address: str
    city: str
    state_name: str
    country: str
    zipcode: str

    # Session Update History
    update_data: List[ChargingSessionUpdate]
    update_period: int

    utility: Optional[PowerUtility]

    def __init__(
        self, session_id: int, client: "ChargePoint", *args, **kwargs  # noqa: F821
    ):
        super().__init__(*args, **kwargs)
        self._client = client
        self.session_id = session_id

        self._get()

    def _get(self) -> None:
        _LOGGER.debug("Getting session information for session %s", self.session_id)
        response = None

        # There is some level of eventual consistency where with sessions
        # that are started and then immediately retrieved, this normally
        # becomes consistent within a few seconds, so we will retry this
        # call up to 10 times.
        for attempt in range(1, 11):  # pragma: no cover
            # Today on "Every Internal API is Weird as Hell"...
            # I present to you: passing a JSON blob as a URL parameter.
            response = self._client.session.get(
                f'{MAP_URL}?{{"user_id":{self._client.user_id},"charging_status":{{"mfhs":{{}},"session_id":{self.session_id}}}}}'
            )

            if response.status_code != codes.ok:
                raise ChargePointCommunicationException(
                    response=response, message="Failed to get charging session data."
                )

            json = response.json()
            status = json.get("charging_status", {})
            # Failed calls here have been NullPointers from their API
            # directly returned to the user.
            # There have also been a couple random "this ID doesn't exist"
            # logical errors as well, so lets just cover all the bases.
            error = (
                # Sometimes this key isn't even returned.
                "charging_status" not in json.keys()
                or
                # Logical errors from withing the API returned here.
                "error_message" in status.keys()
                or
                # Raw Java errors are returned here.
                "error" in status.keys()
            )
            if error and attempt < 10:
                _LOGGER.warning("Failed to retrieve session. Attempt (%d/10)", attempt)
                _LOGGER.debug("%s", json)
                sleep(1)
                continue
            elif error:
                raise ChargePointCommunicationException(
                    response=response, message="Failed to get charging session data."
                )
            else:
                break

        _LOGGER.debug("Passed retry loop: %s", response.json())
        status = response.json()["charging_status"]

        self.start_time = datetime.fromtimestamp(
            status["start_time"] / 1000, tz=timezone.utc
        )
        self.device_id = status["device_id"]
        self.device_name = status["device_name"]
        self.charging_state = status["current_charging"]
        self.charging_time = status["charging_time"]
        self.energy_kwh = status["energy_kwh"]
        self.miles_added = status["miles_added"]
        self.miles_added_per_hour = status.get("miles_added_per_hour", 0.0)
        self.outlet_number = status["outlet_number"]
        self.port_level = status["port_level"]
        self.power_kw = status["power_kw"]
        self.purpose = status["purpose"]
        self.currency_iso_code = status["currency_iso_code"]
        self.payment_completed = status["payment_completed"]
        self.payment_type = status["payment_type"]
        self.pricing_spec_id = status["pricing_spec_id"]
        self.total_amount = status["total_amount"]
        self.api_flag = status["api_flag"]
        self.enable_stop_charging = status["enable_stop_charging"]
        self.has_charging_receipt = status["has_charging_receipt"]
        self.has_utility_info = status["has_utility_info"]
        self.is_home_charger = status["is_home_charger"]
        self.is_purpose_finalized = status["is_purpose_finalized"]
        self.last_update_data_timestamp = datetime.fromtimestamp(
            status["last_update_data_timestamp"] / 1000, tz=timezone.utc
        )
        self.stop_charge_supported = status["stop_charge_supported"]
        self.company_id = status["company_id"]
        self.company_name = status["company_name"]
        self.latitude = status["lat"]
        self.longitude = status["lon"]
        self.address = status["address1"]
        self.city = status["city"]
        self.state_name = status["state_name"]
        self.country = status["country"]
        self.zipcode = status["zipcode"]
        self.update_data = [
            ChargingSessionUpdate.from_json(update) for update in status["update_data"]
        ]
        self.update_period = status["update_period"]

        self.utility = None
        utility = status.get("utility")
        if utility:
            self.utility = PowerUtility.from_json(utility)

    def stop(self, max_retry: int = 30) -> None:
        _modify(
            client=self._client,
            action="stop",
            device_id=self.device_id,
            port_number=self.outlet_number,
            session_id=self.session_id,
            max_retry=max_retry,
        )

    @classmethod
    def start(
        cls, device_id: int, client: "ChargePoint", max_retry: int = 30  # noqa: F821
    ):
        session_id = _modify(
            client=client, action="start", device_id=device_id, max_retry=max_retry
        )
        # So, after wayyy too much trial and error, I noticed that the "sessionId"
        # returned by the start session API is significantly higher than normal
        # session IDs... I have no clue what it means, so we are just going to
        # get the correct session ID from the status API.
        status = client.get_user_charging_status()
        if session_id and status:  # pragma: no cover
            return cls(session_id=status.session_id, client=client)
