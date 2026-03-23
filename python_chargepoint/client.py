from typing import List, Optional
from functools import wraps
from time import sleep
from importlib.metadata import version, PackageNotFoundError

from requests import Session, codes

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
from .global_config import ChargePointGlobalConfiguration
from .session import ChargingSession
from .constants import _LOGGER, DISCOVERY_API
from . import __name__ as MODULE_NAME

try:
    MODULE_VERSION = version(MODULE_NAME)
except PackageNotFoundError:
    MODULE_VERSION = "unknown"

USER_AGENT = f"{MODULE_NAME}/{MODULE_VERSION}"

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
        session_token: Optional[str] = "",
        auth_token: Optional[str] = "",
    ):
        self._session = Session()
        self._user_id = None
        self._logged_in = False

        self._session.headers = {
                "user-agent": USER_AGENT,
            }
        
        self._global_config = self._get_configuration(username)

        if session_token or auth_token:
            self._set_session_token(session_token)
            self._set_auth_token(auth_token)
            self._logged_in = True
            try:
                self._get_initial_session_token()
                account: ChargePointAccount = self.get_account()
                self._user_id = str(account.user.user_id)
                self.refresh_session_token()
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
        return self._get_session_token()


    @property
    def global_config(self) -> ChargePointGlobalConfiguration:
        return self._global_config

    def login(self, username: str, password: str) -> None:
        """
        Create a session and login to ChargePoint
        :param username: Account username
        :param password: Account password
        """
        login_url = (
            f"{self._global_config.endpoints.sso}v1/user/login"
        )
        
        request = {
            "username": username,
            "password": password,
        }
        _LOGGER.debug("Attempting client login with user: %s", username)
        login = self._session.post(login_url, json=request)
        _LOGGER.debug(login.cookies.get_dict())
        _LOGGER.debug(login.headers)

        if login.status_code == codes.ok:
            self._logged_in = True
            self._get_initial_session_token()
            account: ChargePointAccount = self.get_account()
            self._user_id = str(account.user.user_id)
            self.refresh_session_token()
            return

        _LOGGER.error(
            "Failed to get auth token! status_code=%s err=%s",
            login.status_code,
            login.text,
        )
        raise ChargePointLoginError(login, "Failed to authenticate to ChargePoint!")

    def logout(self):
        response = self._session.post(
            f"{self._global_config.endpoints.sso}v1/user/logout",
        )

        if response.status_code != codes.ok:
            raise ChargePointCommunicationException(
                response=response, message="Failed to log out!"
            )

        self._session.cookies.clear_session_cookies()
        self._logged_in = False

    def _get_configuration(self, username: str) -> ChargePointGlobalConfiguration:
        _LOGGER.debug("Discovering account region for username %s", username)
        request = {"username": username}
        response = self._session.post(DISCOVERY_API, json=request)
        if response.status_code != codes.ok:
            raise ChargePointCommunicationException(
                response=response,
                message="Failed to discover region for provided username!",
            )
        config = ChargePointGlobalConfiguration.from_json(response.json())
        _LOGGER.debug(
            "Discovered account region: %s / %s (%s)",
            config.region,
            config.default_country.name,
            config.default_country.code,
        )
        return config

    def _get_initial_session_token(self):
        _LOGGER.debug("Requesting inital session token")
        response = self._session.post(
            f"{self._global_config.endpoints.portal_domain}index.php/nghelper/getSession", json={"user_id": self.user_id}
        )

        if (response.status_code != codes.ok):
            _LOGGER.error(
                "Failed to get session! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to retrieve session."
            )

    def refresh_session_token(self):
        _LOGGER.debug("Requesting long lived token")
        response = self._session.post(
            f"{self._global_config.endpoints.webservices}mobileapi/v5", json={"user_id": self.user_id}
        )

        if (response.status_code != codes.ok):
            _LOGGER.error(
                "Failed to get long lived token! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to retrieve long lived token."
            )
        
        self._session.cookies.clear(domain='')

    def _get_session_token(self) -> str:
        out =''
        token = [cookie for cookie in self._session.cookies if cookie.name == 'coulomb_sess']

        if token:
            out = token[0].value

        return out

    def _set_session_token(self, session_token: str):
        if session_token:
            self._session.cookies.set("coulomb_sess", session_token)

    def _set_auth_token(self, auth_token: str):
        if auth_token:
            self._session.cookies.set("auth-session", auth_token)

    @_require_login
    def get_account(self) -> ChargePointAccount:
        _LOGGER.debug("Getting ChargePoint Account Details")
        response = self._session.get(
            f"{self._global_config.endpoints.accounts}v1/driver/profile/user",
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
            f"{self._global_config.endpoints.accounts}v1/driver/vehicle",
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
        response = self._session.post(
            f"{self._global_config.endpoints.webservices}mobileapi/v5", json=get_pandas
        )

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
        response = self._session.post(
            f"{self._global_config.endpoints.webservices}mobileapi/v5", json=get_status
        )

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

        response = self._session.post(
            f"{self._global_config.endpoints.webservices}mobileapi/v5",
            json=get_tech_info,
        )

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
        request = {"user_status": {"mfhs": {}}}
        response = self._session.post(
            f"{self._global_config.endpoints.mapcache}v2", json=request
        )

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
    def set_amperage_limit(
        self, charger_id: int, amperage_limit: int, max_retry: int = 5
    ) -> None:
        _LOGGER.debug(f"Setting amperage limit for {charger_id} to {amperage_limit}")

        headers = {
                "cp-session-type": "CP_SESSION_TOKEN",
                "cp-session-token": self._get_session_token(),
                "cp-region": self._global_config.region,
        }
        headers.update(self._session.headers)

        request = {
            "chargeAmperageLimit": amperage_limit,
        }
        response = self._session.post(
            f"{self._global_config.endpoints.internal_api}/driver/charger/{charger_id}/config/v1/charge-amperage-limit",
            json=request,
            headers=headers,
        )

        if response.status_code != codes.ok:
            _LOGGER.error(
                "Failed to set amperage limit! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to set amperage limit."
            )
        status = response.json()
        # The API can return 200 but still have a failure status.
        if status["status"] != "success":
            message = status.get("message", "empty message")
            _LOGGER.error(
                "Failed to set amperage limit! status=%s err=%s",
                status["status"],
                message,
            )
            raise ChargePointCommunicationException(
                response=response, message=f"Failed to set amperage limit: {message}"
            )

        # This is eventually consistent so we wait until the new limit is reflected.
        for _ in range(1, max_retry):  # pragma: no cover
            charger_status = self.get_home_charger_status(charger_id)
            if charger_status.amperage_limit == amperage_limit:
                return
            sleep(1)

        raise ChargePointCommunicationException(
            response=response,
            message="New amperage limit did not persist to charger after retries",
        )

    @_require_login
    def restart_home_charger(self, charger_id: int) -> None:
        _LOGGER.debug("Sending restart command for panda: %s", charger_id)
        restart = {
            "user_id": self.user_id,
            "restart_panda": {"device_id": charger_id, "mfhs": {}},
        }
        response = self._session.post(
            f"{self._global_config.endpoints.webservices}mobileapi/v5", json=restart
        )

        if response.status_code != codes.ok:
            _LOGGER.error(
                "Failed to restart charger! status_code=%s err=%s",
                response.status_code,
                response.text,
            )
            raise ChargePointCommunicationException(
                response=response, message="Failed to restart charger."
            )

        status = response.json()
        _LOGGER.debug(status)
        return

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
