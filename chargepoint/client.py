from time import sleep
from uuid import uuid4
from typing import List, Optional

from requests import Session, codes, post

from . import LOGGER
from .types import (
    ChargePointAccount,
    ElectricVehicle,
    HomeChargerStatus,
    UserChargingStatus,
    ChargingSession,
)
from .exceptions import ChargePointLoginError, ChargePointCommunicationException


def _dict_for_query(device_data: dict) -> dict:
    """
    GET requests send device data as a nested object.
    To avoid storing the device data block in two
    formats, we are just going to compute the flat
    dictionary.
    """
    return {f"deviceData[{key}]": value for key, value in device_data.items()}


class ChargePoint:
    _v5_url = "https://webservices.chargepoint.com/backend.php/mobileapi/v5"
    _map_url = "https://mc.chargepoint.com/map-prod/v2"

    def __init__(self, username: str, password: str, app_version: str = "5.91.0"):
        self._app_version = app_version
        self._device_data = {
            "appId": "com.coulomb.ChargePoint",
            "manufacturer": "Apple",
            "model": "iPhone",
            "notificationId": "",
            "notificationIdType": "",
            "type": "IOS",
            "udid": str(uuid4()),
            "version": app_version,
        }
        self._device_query_params = _dict_for_query(self._device_data)

        self._user_id, session_id = self._login(username, password)
        self._session = Session()
        self._session.headers = {
            "cp-session-type": "CP_SESSION_TOKEN",
            "cp-session-token": session_id,
            # Data:       |------------------Token Data------------------||---?---||-Reg-|
            # Session ID: rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US
            "cp-region": session_id.split("#R")[1],
            "user-agent": "ChargePoint/225 (iPhone; iOS 15.3; Scale/3.00)",
        }
        self._session.cookies.set("coulomb_sess", session_id)

    @property
    def user_id(self):
        return self._user_id

    def _login(self, username: str, password: str) -> tuple:
        """
        Create a session and login to ChargePoint
        :param username: Account username
        :param password: Account password
        """
        login_url = (
            "https://account.chargepoint.com/account/v2/driver/profile/account/login"
        )
        headers = {
            "User-Agent": f"com.coulomb.ChargePoint/{self._app_version} CFNetwork/1329 Darwin/21.3.0"
        }
        request = {
            "deviceData": self._device_data,
            "username": username,
            "password": password,
        }
        LOGGER.debug("Attempting client login with user: %s", username)
        login = post(login_url, json=request, headers=headers)

        if login.status_code == codes.ok:
            req = login.json()
            user_id = req["user"]["userId"]
            LOGGER.debug("Authentication success! User ID: %s", user_id)
            return user_id, req["sessionId"]

        LOGGER.error(
            "Failed to get account information! status_code=%s err=%s",
            login.status_code,
            login.text,
        )
        raise ChargePointLoginError(login, "Failed to authenticate to ChargePoint!")

    def get_account(self) -> ChargePointAccount:
        LOGGER.debug("Getting ChargePoint Account Details")
        response = self._session.get(
            "https://account.chargepoint.com/account/v1/driver/profile/user",
            params=self._device_query_params,
        )

        if response.status_code != codes.ok:
            LOGGER.error(
                "Failed to get account information! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to get user information."
            )

        account = response.json()
        return ChargePointAccount.from_json(account)

    def get_vehicles(self) -> List[ElectricVehicle]:
        response = self._session.get(
            "https://account.chargepoint.com/account/v1/driver/vehicle",
            params=self._device_query_params,
        )

        if response.status_code != codes.ok:
            LOGGER.error(
                "Failed to list vehicles! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to retrieve EVs."
            )

        evs = response.json()
        return [ElectricVehicle.from_json(ev) for ev in evs]

    def get_home_chargers(self) -> List[int]:
        get_pandas = {"user_id": self.user_id, "get_pandas": {"mfhs": {}}}
        response = self._session.post(self._v5_url, json=get_pandas)

        if response.status_code != codes.ok:
            LOGGER.error(
                "Failed to get home chargers! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to retrieve Home Flex chargers."
            )

        # {"get_pandas":{"device_ids":[12345678]}}
        return response.json()["get_pandas"]["device_ids"]

    def get_home_charger_status(self, charger_id: int) -> HomeChargerStatus:
        get_status = {
            "user_id": self.user_id,
            "get_panda_status": {"device_id": charger_id, "mfhs": {}},
        }
        response = self._session.post(self._v5_url, json=get_status)

        if response.status_code != codes.ok:
            LOGGER.error(
                "Failed to determine home charger status! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to get home charger status."
            )

        status = response.json()
        return HomeChargerStatus.from_json(status["get_panda_status"])

    def get_user_charging_status(self) -> Optional[UserChargingStatus]:
        request = {"deviceData": self._device_data, "user_status": {"mfhs": {}}}
        response = self._session.post(self._map_url, json=request)

        if response.status_code != codes.ok:
            LOGGER.error(
                "Failed to get account charging status! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to get user charging status."
            )

        status = response.json()
        if not status["user_status"]:
            LOGGER.debug("No user status returned, assuming not charging.")
            return None

        return UserChargingStatus.from_json(status["user_status"])

    def get_charging_session(self, session_id: int):
        # Today on "Every Internal API is Weird as Hell"...
        # I present to you: passing a JSON blob as a URL parameter.

        response = self._session.get(
            f'{self._map_url}?{{"user_id":{self.user_id},"charging_status":{{"mfhs":{{}},"session_id":{session_id}}}}}'
        )

        if response.status_code != codes.ok:
            raise ChargePointCommunicationException(
                response=response, message="Failed to get charging session data."
            )

        session = response.json()
        return ChargingSession.from_json(
            json=session["charging_status"],
            mod_func=self._mod_charging_session,
        )

    def _mod_charging_session(
        self,
        action: str,
        device_id: int,
        port_number: int = 1,
        session_id: int = 0,
        max_retry: int = 10,
    ) -> None:
        if action not in ["start", "stop"]:
            raise AttributeError(f"Invalid action: {action}")

        request = {
            "deviceData": self._device_data,
            "deviceId": device_id,
        }

        if action == "stop":
            request["portNumber"] = port_number
            request["sessionId"] = session_id

        action_path = {
            "start": "startsession",
            "stop": "stopSession",
        }

        response = self._session.post(
            f"https://account.chargepoint.com/account/v1/driver/station/{action_path[action]}",
            json=request,
        )

        if response.status_code != codes.ok:
            LOGGER.error(
                "Failed to send command to station! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message=f"Failed to {action} ChargePoint session."
            )

        action = response.json()
        ack_id = action["ackId"]

        for i in range(max_retry):
            LOGGER.debug(
                "Checking station modification status. Attempt (%d/%d)",
                i + 1,
                max_retry,
            )
            request = {
                "deviceData": self._device_data,
                "ackId": ack_id,
                "action": f"{action}_session",
            }
            response = self._session.post(
                "https://account.chargepoint.com/account/v1/driver/station/session/ack",
                json=request,
            )
            if response.status_code == codes.ok:
                LOGGER.info("Successfully confirmed %s command.", action)
                return

            if i == max_retry - 1:
                LOGGER.error(
                    "Failed to confirm station modification! status_code=%s err=%s",
                    response.status_code,
                    response.text,
                )
                raise ChargePointCommunicationException(
                    response=response,
                    message=f"Session failed to {action} in time allotted.",
                )
            sleep(1)

    def start_charging_session(self, device_id: int, max_retry: int = 10) -> None:
        self._mod_charging_session(
            action="start", device_id=device_id, max_retry=max_retry
        )

    def stop_charging_session(
        self, device_id: int, port_number: int, session_id: int, max_retry: int = 10
    ) -> None:
        self._mod_charging_session(
            action="stop",
            device_id=device_id,
            port_number=port_number,
            session_id=session_id,
            max_retry=max_retry,
        )
