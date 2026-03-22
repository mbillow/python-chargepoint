from typing import List, Optional
from functools import wraps
from time import sleep
from importlib.metadata import version, PackageNotFoundError
from urllib.parse import unquote

from requests import Session, codes, Response, post, get
from requests.exceptions import RequestException, HTTPError, JSONDecodeError

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
    ChargePointInvalidSession,
    ChargePointDatadomeCaptcha,
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
COULOMB_SESSION = "coulomb_sess"
SSO_SESSION = "auth-session"
COOKIE_DOMAIN = ".chargepoint.com"


def _require_login(func):
    @wraps(func)
    def check_login(*args, **kwargs):
        self: ChargePoint = args[0]
        if self.coulomb_token is None:
            raise RuntimeError("Must login to use ChargePoint API")
        return func(*args, **kwargs)

    return check_login


class ChargePoint:
    def __init__(
        self,
        username: str,
        coulomb_token: str = "",
    ):
        self._session = Session()
        self._username = username
        self._user_id = None

        self._session.headers.update({"user-agent": USER_AGENT})

        self._global_config = self._get_configuration(username)

        if coulomb_token:
            self._set_coulomb_token(coulomb_token)

        if coulomb_token:
            self._init_account_parameters()

    @property
    def user_id(self) -> Optional[str]:
        return self._user_id

    @property
    def session(self) -> Session:
        return self._session

    @property
    def coulomb_token(self) -> str | None:
        return self._session.cookies.get("coulomb_sess", domain=COOKIE_DOMAIN)

    def _set_coulomb_token(self, token: str):
        if token:
            parsed = unquote(token)
            self._session.cookies.set("coulomb_sess", parsed, domain=".chargepoint.com")
        else:
            raise ValueError("empty session token provided")

    @property
    def global_config(self) -> ChargePointGlobalConfiguration:
        return self._global_config

    def _request(self, method: str, url: str, **kwargs) -> Response:
        _LOGGER.debug("[%s] %s", method, url)
        r = self._session.request(method, url, **kwargs)
        _LOGGER.debug("Status: %d", r.status_code)
        _LOGGER.debug("Request Headers: %s", r.request.headers)
        _LOGGER.debug("Response Headers: %s", r.headers)
        try:
            r.raise_for_status()
        except HTTPError as e:
            if e.response.status_code == codes.unauthorized:
                raise ChargePointInvalidSession(
                    e.response, "Session token has expired. Please login again!"
                ) from e
            if e.response.status_code == codes.forbidden:
                try:
                    body = e.response.json()
                    if "url" in body.keys():
                        raise ChargePointDatadomeCaptcha(
                            body["url"], f"[{method}] {url} blocked by Datadome."
                        )
                except JSONDecodeError:
                    raise ChargePointCommunicationException(
                        e.response, f"FORBIDDEN: [{method}] {url}"
                    )
        except RequestException as e:
            _LOGGER.error(str(e))
        return r

    def _init_account_parameters(self):
        account: ChargePointAccount = self.get_account()
        self._user_id = str(account.user.user_id)
        if account.user.username != self._username:
            _LOGGER.warning(
                "Username used for discovery (%s) does not match session (%s), using value from session.",
                self._username,
                account.user.username,
            )
            self._username = account.user.username

        self.session.headers.update(
            {
                "cp-session-type": "CP_SESSION_TOKEN",
                "cp-session-token": self.coulomb_token or "",
                "cp-region": self._global_config.region,
            }
        )

    def login_with_password(self, password: str) -> None:
        """
        Create a session and login to ChargePoint
        :param password: Account password
        """
        login_url = f"{self._global_config.endpoints.sso}v1/user/login"

        request = {
            "username": self._username,
            "password": password,
        }
        _LOGGER.debug(
            "Attempting client login (%s) with user: %s", login_url, self._username
        )
        login = post(login_url, json=request)

        coulomb_token = login.cookies.get(COULOMB_SESSION)
        if login.status_code == codes.ok and coulomb_token:
            self._set_coulomb_token(coulomb_token)
            self._init_account_parameters()
            return

        _LOGGER.error(
            "Failed to get auth token! status_code=%s err=%s",
            login.status_code,
            login.text,
        )
        raise ChargePointLoginError(login, "Failed to authenticate to ChargePoint!")

    def login_with_sso_session(self, sso_jwt: str):
        _LOGGER.debug("Requesting coulomb session token")
        url = f"{self._global_config.endpoints.portal_domain}index.php/nghelper/getSession"
        response = get(url, cookies={SSO_SESSION: sso_jwt})

        coulomb_token = response.cookies.get(COULOMB_SESSION)
        if response.status_code == codes.ok and coulomb_token:
            self._set_coulomb_token(coulomb_token)
            self._init_account_parameters()
            return

        raise ChargePointInvalidSession(
            response, "Failed to exchange sso auth token for coulomb session."
        )

    def logout(self):
        response = self._request(
            "POST",
            f"{self._global_config.endpoints.sso}v1/user/logout",
        )

        if response.status_code != codes.ok:
            raise ChargePointCommunicationException(
                response=response, message="Failed to log out!"
            )

        self._session.cookies.clear_session_cookies()
        self._logged_in = False
        self._user_id = None

    def _get_configuration(self, username: str) -> ChargePointGlobalConfiguration:
        _LOGGER.debug("Discovering account region for username %s", username)
        request = {"username": username}
        response = self._request("POST", DISCOVERY_API, json=request)
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

    @_require_login
    def get_account(self) -> ChargePointAccount:
        _LOGGER.debug("Getting ChargePoint Account Details")
        response = self._request(
            "GET",
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
        response = self._request(
            "GET",
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
        response = self._request(
            "POST",
            f"{self._global_config.endpoints.webservices}mobileapi/v5",
            json=get_pandas,
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
        response = self._request(
            "POST",
            f"{self._global_config.endpoints.webservices}mobileapi/v5",
            json=get_status,
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

        response = self._request(
            "POST",
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
        response = self._request(
            "POST", f"{self._global_config.endpoints.mapcache}v2", json=request
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
        self, charger_id: int, amperage_limit: int
    ) -> None:
        _LOGGER.debug(f"Setting amperage limit for {charger_id} to {amperage_limit}")

        request = {
            "chargeAmperageLimit": amperage_limit,
        }
        response = self._request(
            "POST",
            f"{self._global_config.endpoints.internal_api}/driver/charger/{charger_id}/config/v1/charge-amperage-limit",
            json=request,
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

    @_require_login
    def restart_home_charger(self, charger_id: int) -> None:
        _LOGGER.debug("Sending restart command for panda: %s", charger_id)
        restart = {
            "user_id": self.user_id,
            "restart_panda": {"device_id": charger_id, "mfhs": {}},
        }
        response = self._request(
            "POST",
            f"{self._global_config.endpoints.webservices}mobileapi/v5",
            json=restart,
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
