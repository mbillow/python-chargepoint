from uuid import uuid4
from typing import List, Optional
from functools import wraps

from requests import Session, codes, post

from .types import (
    ChargePointAccount,
    ElectricVehicle,
    HomeChargerStatus,
    HomeChargerTechnicalInfo,
    UserChargingStatus,
)
from .exceptions import (
    ChargePointLoginError,
    ChargePointCommunicationException,
    ChargePointBaseException,
    ChargePointInvalidSession,
)
from .session import ChargingSession
from .constants import _LOGGER, V5_URL, MAP_URL


def _dict_for_query(device_data: dict) -> dict:
    """
    GET requests send device data as a nested object.
    To avoid storing the device data block in two
    formats, we are just going to compute the flat
    dictionary.
    """
    return {f"deviceData[{key}]": value for key, value in device_data.items()}


def _require_login(func):
    @wraps(func)
    def check_login(*args, **kwargs):
        self = args[0]
        if not self._logged_in:
            raise RuntimeError("Must login to use ChargePoint API")
        try:
            return func(*args, **kwargs)
        except ChargePointCommunicationException as exc:
            if exc.response.status_code == codes.unauthorized:
                raise ChargePointInvalidSession(
                    exc.response, "Session token has expired. Please login again!"
                ) from exc
            else:
                raise

    return check_login


class ChargePoint:
    def __init__(
        self,
        username: str,
        password: str,
        session_token: str = "",
        app_version: str = "5.91.0",
    ):
        self._session = Session()
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
        self._user_id = None
        self._logged_in = False
        self._session_token = None

        if session_token:
            self._set_session_token(session_token)
            self._logged_in = True
            try:
                account: ChargePointAccount = self.get_account()
                self._user_id = str(account.user.user_id)
                return
            except ChargePointCommunicationException:
                _LOGGER.warning(
                    "Provided session token is expired, will attempt to re-login"
                )
                self._logged_in = False

        self.login(username, password)

    @property
    def user_id(self) -> Optional[str]:
        return self._user_id

    @property
    def session(self) -> Session:
        return self._session

    @property
    def session_token(self) -> Optional[str]:
        return self._session_token

    @property
    def device_data(self) -> dict:
        return self._device_data

    def login(self, username: str, password: str) -> None:
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
        _LOGGER.debug("Attempting client login with user: %s", username)
        login = post(login_url, json=request, headers=headers)
        _LOGGER.debug(login.cookies.get_dict())
        _LOGGER.debug(login.headers)

        if login.status_code == codes.ok:
            req = login.json()
            self._user_id = req["user"]["userId"]
            _LOGGER.debug("Authentication success! User ID: %s", self._user_id)
            self._set_session_token(req["sessionId"])
            self._logged_in = True
            return

        _LOGGER.error(
            "Failed to get account information! status_code=%s err=%s",
            login.status_code,
            login.text,
        )
        raise ChargePointLoginError(login, "Failed to authenticate to ChargePoint!")

    def logout(self):
        response = self._session.post(
            "https://account.chargepoint.com/account/v1/driver/profile/account/logout",
            json={"deviceData": self._device_data},
        )

        if response.status_code != codes.ok:
            raise ChargePointCommunicationException(
                response=response, message="Failed to log out!"
            )

        self._session.headers = {}
        self._session.cookies.clear_session_cookies()
        self._session_token = None
        self._logged_in = False

    def _set_session_token(self, session_token: str):
        try:
            self._session.headers = {
                "cp-session-type": "CP_SESSION_TOKEN",
                "cp-session-token": session_token,
                # Data:       |------------------Token Data------------------||---?---||-Reg-|
                # Session ID: rAnDomBaSe64EnCodEdDaTaToKeNrAnDomBaSe64EnCodEdD#D???????#RNA-US
                "cp-region": session_token.split("#R")[1],
                "user-agent": "ChargePoint/225 (iPhone; iOS 15.3; Scale/3.00)",
            }
        except IndexError:
            raise ChargePointBaseException("Invalid session token format.")

        self._session_token = session_token
        self._session.cookies.set("coulomb_sess", session_token)

    @_require_login
    def get_account(self) -> ChargePointAccount:
        _LOGGER.debug("Getting ChargePoint Account Details")
        response = self._session.get(
            "https://account.chargepoint.com/account/v1/driver/profile/user",
            params=self._device_query_params,
        )

        if response.status_code != codes.ok:
            _LOGGER.error(
                "Failed to get account information! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to get user information."
            )

        account = response.json()
        return ChargePointAccount.from_json(account)

    @_require_login
    def get_vehicles(self) -> List[ElectricVehicle]:
        _LOGGER.debug("Listing vehicles")
        response = self._session.get(
            "https://account.chargepoint.com/account/v1/driver/vehicle",
            params=self._device_query_params,
        )

        if response.status_code != codes.ok:
            _LOGGER.error(
                "Failed to list vehicles! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to retrieve EVs."
            )

        evs = response.json()
        return [ElectricVehicle.from_json(ev) for ev in evs]

    @_require_login
    def get_home_chargers(self) -> List[int]:
        _LOGGER.debug("Searching for registered pandas")
        get_pandas = {"user_id": self.user_id, "get_pandas": {"mfhs": {}}}
        response = self._session.post(V5_URL, json=get_pandas)

        if response.status_code != codes.ok:
            _LOGGER.error(
                "Failed to get home chargers! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to retrieve Home Flex chargers."
            )

        # {"get_pandas":{"device_ids":[12345678]}}
        pandas = response.json()["get_pandas"]["device_ids"]
        _LOGGER.debug(
            "Discovered %d connected pandas: %s",
            len(pandas),
            ",".join([str(p) for p in pandas]),
        )
        return pandas

    @_require_login
    def get_home_charger_status(self, charger_id: int) -> HomeChargerStatus:
        _LOGGER.debug("Getting status for panda: %s", charger_id)
        get_status = {
            "user_id": self.user_id,
            "get_panda_status": {"device_id": charger_id, "mfhs": {}},
        }
        response = self._session.post(V5_URL, json=get_status)

        if response.status_code != codes.ok:
            _LOGGER.error(
                "Failed to determine home charger status! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to get home charger status."
            )

        status = response.json()

        _LOGGER.debug(status)

        return HomeChargerStatus.from_json(
            charger_id=charger_id, json=status["get_panda_status"]
        )

    @_require_login
    def get_home_charger_technical_info(
        self, charger_id: int
    ) -> HomeChargerTechnicalInfo:
        _LOGGER.debug("Getting tech info for panda: %s", charger_id)
        get_tech_info = {
            "user_id": self.user_id,
            "get_station_technical_info": {"device_id": charger_id, "mfhs": {}},
        }

        response = self._session.post(V5_URL, json=get_tech_info)

        if response.status_code != codes.ok:
            _LOGGER.error(
                "Failed to determine home charger tech info! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to get home charger tech info."
            )

        status = response.json()

        _LOGGER.debug(status)

        return HomeChargerTechnicalInfo.from_json(
            json=status["get_station_technical_info"]
        )

    @_require_login
    def get_user_charging_status(self) -> Optional[UserChargingStatus]:
        _LOGGER.debug("Checking account charging status")
        request = {"deviceData": self._device_data, "user_status": {"mfhs": {}}}
        response = self._session.post(MAP_URL, json=request)

        if response.status_code != codes.ok:
            _LOGGER.error(
                "Failed to get account charging status! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to get user charging status."
            )

        status = response.json()
        if not status["user_status"]:
            _LOGGER.debug("No user status returned, assuming not charging.")
            return None

        _LOGGER.debug("Raw status: %s", status)

        return UserChargingStatus.from_json(status["user_status"])

    @_require_login
    def get_charging_session(self, session_id: int) -> ChargingSession:
        return ChargingSession(session_id=session_id, client=self)

    @_require_login
    def start_charging_session(
        self, device_id: int, max_retry: int = 30
    ) -> ChargingSession:

        return ChargingSession.start(
            device_id=device_id, client=self, max_retry=max_retry
        )
