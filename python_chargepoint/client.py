from __future__ import annotations

from typing import List, Optional
from functools import wraps
from importlib.metadata import version, PackageNotFoundError
from urllib.parse import unquote
from http.cookies import SimpleCookie

import aiohttp
from yarl import URL

from .types import (
    Account,
    ElectricVehicle,
    HomeChargerConfiguration,
    HomeChargerStatus,
    HomeChargerTechnicalInfo,
    MapFilter,
    MapStation,
    StationInfo,
    UserChargingStatus,
)
from .global_config import GlobalConfiguration, ZoomBounds
from .exceptions import (
    LoginError,
    CommunicationError,
    InvalidSession,
    DatadomeCaptcha,
)
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
    async def check_login(*args, **kwargs):
        self: ChargePoint = args[0]
        if self.coulomb_token is None:
            raise RuntimeError("Must login to use ChargePoint API")
        return await func(*args, **kwargs)

    return check_login


class ChargePoint:
    def __init__(
        self,
        username: str,
        coulomb_token: str = "",
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self._username = username
        self._user_id: Optional[int] = None
        self._global_config: GlobalConfiguration
        self._request_headers = {"user-agent": USER_AGENT}
        self._owns_session = session is None

        if session is not None:
            self._session = session
        else:
            self._session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar()
            )

        if coulomb_token:
            self._set_coulomb_token(coulomb_token)

    @classmethod
    async def create(
        cls,
        username: str,
        coulomb_token: str = "",
        session: Optional[aiohttp.ClientSession] = None,
    ) -> ChargePoint:
        client = cls(username, coulomb_token, session)
        client._global_config = await client._get_configuration(username)
        if coulomb_token:
            await client._init_account_parameters()
        return client

    async def close(self) -> None:
        if self._owns_session:
            await self._session.close()

    @property
    def user_id(self) -> Optional[int]:
        return self._user_id

    @property
    def session(self) -> aiohttp.ClientSession:
        return self._session

    @property
    def coulomb_token(self) -> Optional[str]:
        cookies = self._session.cookie_jar.filter_cookies(
            URL(f"https://account{COOKIE_DOMAIN}/")
        )
        morsel = cookies.get(COULOMB_SESSION)
        return morsel.value if morsel else None

    def _set_coulomb_token(self, token: str):
        if token:
            parsed = unquote(token)
            cookie: SimpleCookie = SimpleCookie()
            cookie[COULOMB_SESSION] = parsed
            cookie[COULOMB_SESSION]["domain"] = COOKIE_DOMAIN
            cookie[COULOMB_SESSION]["path"] = "/"
            self._session.cookie_jar.update_cookies(
                cookie, response_url=URL(f"https://account{COOKIE_DOMAIN}/")
            )
        else:
            raise ValueError("empty session token provided")

    @property
    def global_config(self) -> GlobalConfiguration:
        return self._global_config

    async def _request(self, method: str, url: URL, **kwargs) -> aiohttp.ClientResponse:
        _LOGGER.debug("[%s] %s", method, url)
        headers = {**self._request_headers, **kwargs.pop("headers", {})}
        response = await self._session.request(method, url, headers=headers, **kwargs)
        _LOGGER.debug("Status: %d", response.status)
        _LOGGER.debug("Request Headers: %s", response.request_info.headers)
        _LOGGER.debug("Response Headers: %s", response.headers)

        if response.status == 401:
            await response.release()
            raise InvalidSession(
                response, "Session token has expired. Please login again!"
            )
        if response.status == 403:
            try:
                body = await response.json(content_type=None)
                if "url" in body:
                    raise DatadomeCaptcha(
                        body["url"], f"[{method}] {url} blocked by Datadome."
                    )
            except Exception:
                pass
            raise CommunicationError(
                response, f"FORBIDDEN: [{method}] {url}"
            )

        return response

    async def _init_account_parameters(self):
        account: Account = await self.get_account()
        self._user_id = account.user.user_id
        if account.user.username != self._username:
            _LOGGER.warning(
                "Username used for discovery (%s) does not match session (%s), using value from session.",
                self._username,
                account.user.username,
            )
            self._username = account.user.username

        self._request_headers.update(
            {
                "cp-session-type": "CP_SESSION_TOKEN",
                "cp-session-token": self.coulomb_token or "",
                "cp-region": self._global_config.region,
            }
        )

    async def login_with_password(self, password: str) -> None:
        """
        Login to ChargePoint with a username and password.
        :param password: Account password
        """
        login_url = self._global_config.endpoints.sso_endpoint / "v1/user/login"
        request = {
            "username": self._username,
            "password": password,
        }
        _LOGGER.debug(
            "Attempting client login (%s) with user: %s", login_url, self._username
        )
        async with self._session.post(login_url, json=request) as login:
            cookie_morsel = login.cookies.get(COULOMB_SESSION)
            if login.status == 200 and cookie_morsel:
                self._set_coulomb_token(cookie_morsel.value)
                await self._init_account_parameters()
                return

            _LOGGER.error(
                "Failed to get auth token! status_code=%s err=%s",
                login.status,
                await login.text(),
            )
            raise LoginError(login, "Failed to authenticate to ChargePoint!")

    async def login_with_sso_session(self, sso_jwt: str) -> None:
        _LOGGER.debug("Requesting coulomb session token")
        url = self._global_config.endpoints.portal_domain_endpoint / "index.php/nghelper/getSession"
        async with self._session.get(url, cookies={SSO_SESSION: sso_jwt}) as response:
            cookie_morsel = response.cookies.get(COULOMB_SESSION)
            if response.status == 200 and cookie_morsel:
                self._set_coulomb_token(cookie_morsel.value)
                await self._init_account_parameters()
                return

            raise InvalidSession(
                response, "Failed to exchange sso auth token for coulomb session."
            )

    async def logout(self) -> None:
        response = await self._request(
            "POST",
            self._global_config.endpoints.sso_endpoint / "v1/user/logout",
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error("Failed to log out! status_code=%s err=%s", response.status, text)
            raise CommunicationError(
                response=response, message="Failed to log out!"
            )

        await response.release()
        self._session.cookie_jar.clear()
        self._user_id = None

    async def _get_configuration(self, username: str) -> GlobalConfiguration:
        _LOGGER.debug("Discovering account region for username %s", username)
        request = {"username": username}
        response = await self._request("POST", DISCOVERY_API, json=request)
        if response.status != 200:
            text = await response.text()
            _LOGGER.error("Failed to discover region! status_code=%s err=%s", response.status, text)
            raise CommunicationError(
                response=response,
                message="Failed to discover region for provided username!",
            )
        config = GlobalConfiguration.model_validate(await response.json())
        _LOGGER.debug(
            "Discovered account region: %s / %s (%s)",
            config.region,
            config.default_country.name,
            config.default_country.code,
        )
        return config

    @_require_login
    async def get_account(self) -> Account:
        _LOGGER.debug("Getting ChargePoint Account Details")
        response = await self._request(
            "GET",
            self._global_config.endpoints.accounts_endpoint / "v1/driver/profile/user",
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to get account information! status_code=%s err=%s",
                response.status,
                text,
            )
            raise CommunicationError(
                response=response, message="Failed to get user information."
            )

        return Account.model_validate(await response.json())

    @_require_login
    async def get_vehicles(self) -> List[ElectricVehicle]:
        _LOGGER.debug("Listing vehicles")
        response = await self._request(
            "GET",
            self._global_config.endpoints.accounts_endpoint / "v1/driver/vehicle",
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to list vehicles! status_code=%s err=%s",
                response.status,
                text,
            )
            raise CommunicationError(
                response=response, message="Failed to retrieve EVs."
            )

        evs = await response.json()
        return [ElectricVehicle.model_validate(ev) for ev in evs]

    @_require_login
    async def get_home_chargers(self) -> List[int]:
        _LOGGER.debug("Searching for registered home chargers")
        response = await self._request(
            "GET",
            self._global_config.endpoints.hcpo_hcm_endpoint / f"api/v1/configuration/users/{self.user_id}/chargers",
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to get home chargers! status_code=%s err=%s",
                response.status,
                text,
            )
            raise CommunicationError(
                response=response, message="Failed to retrieve Home Flex chargers."
            )

        data = (await response.json())["data"]
        chargers = [int(item["id"]) for item in data]
        _LOGGER.debug(
            "Discovered %d home charger(s): %s",
            len(chargers),
            ",".join([str(c) for c in chargers]),
        )
        return chargers

    @_require_login
    async def get_home_charger_status(self, charger_id: int) -> HomeChargerStatus:
        _LOGGER.debug("Getting status for panda: %s", charger_id)
        response = await self._request(
            "GET",
            self._global_config.endpoints.hcpo_hcm_endpoint / f"api/v1/configuration/users/{self.user_id}/chargers/{charger_id}/status",
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to determine home charger status! status_code=%s err=%s",
                response.status,
                text,
            )
            raise CommunicationError(
                response=response, message="Failed to get home charger status."
            )

        status = await response.json()
        _LOGGER.debug(status)
        return HomeChargerStatus.model_validate({"charger_id": charger_id, **status})

    @_require_login
    async def get_home_charger_technical_info(
        self, charger_id: int
    ) -> HomeChargerTechnicalInfo:
        _LOGGER.debug("Getting tech info for charger: %s", charger_id)
        response = await self._request(
            "GET",
            self._global_config.endpoints.hcpo_hcm_endpoint / f"api/v1/configuration/users/{self.user_id}/chargers/{charger_id}/technical-info",
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to get home charger tech info! status_code=%s err=%s",
                response.status,
                text,
            )
            raise CommunicationError(
                response=response, message="Failed to get home charger tech info."
            )

        return HomeChargerTechnicalInfo.model_validate(await response.json())

    @_require_login
    async def get_user_charging_status(self) -> Optional[UserChargingStatus]:
        _LOGGER.debug("Checking account charging status")
        request: dict = {"user_status": {"mfhs": {}}}
        response = await self._request(
            "POST", self._global_config.endpoints.mapcache_endpoint / "v2", json=request
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to get account charging status! status_code=%s err=%s",
                response.status,
                text,
            )
            raise CommunicationError(
                response=response, message="Failed to get user charging status."
            )

        status = await response.json()
        if not status["user_status"]:
            _LOGGER.debug("No user status returned, assuming not charging.")
            return None

        _LOGGER.debug("Raw status: %s", status)
        return UserChargingStatus.model_validate(status["user_status"])

    @_require_login
    async def set_amperage_limit(self, charger_id: int, amperage_limit: int) -> None:
        _LOGGER.debug("Setting amperage limit for %s to %s", charger_id, amperage_limit)
        response = await self._request(
            "PUT",
            self._global_config.endpoints.hcpo_hcm_endpoint / f"api/v1/configuration/chargers/{charger_id}/charge-amperage-limit",
            json={"chargeAmperageLimit": amperage_limit},
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to set amperage limit! status_code=%s err=%s",
                response.status,
                text,
            )
            raise CommunicationError(
                response=response, message="Failed to set amperage limit."
            )

        await response.release()

    @_require_login
    async def set_led_brightness(self, charger_id: int, level: int) -> None:
        """
        Set the LED brightness level for a home charger.
        :param charger_id: The charger device ID
        :param level: Brightness level (0=off, 1=20%, 2=40%, 3=60%, 4=80%, 5=100%).
                      Available levels are returned by get_home_charger_config().
        """
        _LOGGER.debug("Setting LED brightness for %s to %s", charger_id, level)
        response = await self._request(
            "PUT",
            self._global_config.endpoints.hcpo_hcm_endpoint / f"api/v1/configuration/chargers/{charger_id}/led-brightness",
            json={"ledBrightnessLevel": level},
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to set LED brightness! status_code=%s err=%s",
                response.status,
                text,
            )
            raise CommunicationError(
                response=response, message="Failed to set LED brightness."
            )

        await response.release()

    @_require_login
    async def restart_home_charger(self, charger_id: int) -> None:
        _LOGGER.debug("Sending restart command for charger: %s", charger_id)
        response = await self._request(
            "POST",
            self._global_config.endpoints.hcpo_hcm_endpoint / f"api/v1/configuration/users/{self.user_id}/chargers/{charger_id}/restart",
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to restart charger! status_code=%s err=%s",
                response.status,
                text,
            )
            raise CommunicationError(
                response=response, message="Failed to restart charger."
            )

        await response.release()

    @_require_login
    async def get_home_charger_config(self, charger_id: int) -> HomeChargerConfiguration:
        _LOGGER.debug("Getting configuration for charger: %s", charger_id)
        response = await self._request(
            "GET",
            self._global_config.endpoints.hcpo_hcm_endpoint / f"api/v1/configuration/users/{self.user_id}/chargers/{charger_id}/configurations",
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to get charger configuration! status_code=%s err=%s",
                response.status,
                text,
            )
            raise CommunicationError(
                response=response, message="Failed to get charger configuration."
            )

        return HomeChargerConfiguration.model_validate(await response.json())

    @_require_login
    async def get_charging_session(self, session_id: int) -> ChargingSession:
        session = ChargingSession(session_id=session_id)
        session._client = self
        await session.async_refresh()
        return session

    @_require_login
    async def start_charging_session(self, device_id: int) -> ChargingSession:
        return await ChargingSession.start(device_id=device_id, client=self)

    @_require_login
    async def get_station(self, device_id: int) -> StationInfo:
        """Return detailed information about a charging station by device ID."""
        url = (self._global_config.endpoints.mapcache_endpoint / "v3/station/info").update_query(
            {"deviceId": str(device_id), "use_cache": "false"}
        )
        response = await self._request("GET", url)

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to get station info! status_code=%s err=%s", response.status, text
            )
            raise CommunicationError(response=response, message="Failed to get station info.")

        data = await response.json()
        return StationInfo.model_validate(data)

    @_require_login
    async def get_nearby_stations(
        self,
        bounds: ZoomBounds,
        station_filter: Optional[MapFilter] = None,
    ) -> List[MapStation]:
        """Return charging stations within the given bounding box.

        The API clusters stations into aggregate blobs when the bounding box
        covers too large an area; those blobs are not individual stations and
        are omitted from the result. If an unexpectedly empty list is returned,
        try narrowing the bounding box.
        """
        _LOGGER.debug("Fetching nearby stations within %s", bounds)
        request = {
            "user_id": self._user_id,
            "map_data": {
                "sw_lon": bounds.sw_lon,
                "ne_lat": bounds.ne_lat,
                "ne_lon": bounds.ne_lon,
                "sw_lat": bounds.sw_lat,
                "screen_width": 2048,
                "screen_height": 2048,
                "waitlist": True,
                "filter": station_filter.model_dump() if station_filter else {},
                "mfhs": {},
            },
        }
        response = await self._request(
            "POST", self._global_config.endpoints.mapcache_endpoint / "v2", json=request
        )

        if response.status != 200:
            text = await response.text()
            _LOGGER.error(
                "Failed to get nearby stations! status_code=%s err=%s", response.status, text
            )
            raise CommunicationError(response=response, message="Failed to get nearby stations.")

        data = await response.json()
        stations = data["map_data"].get("stations", [])
        return [MapStation.model_validate(s) for s in stations]
