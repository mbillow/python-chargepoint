from dataclasses import dataclass
from typing import List


@dataclass
class ChargePointZoomBounds:
    ne_longitude: float
    ne_latitude: float
    sw_longitude: float
    sw_latitude: float

    def __repr__(self) -> str:
        return (
            f"[{self.ne_latitude}, {self.ne_longitude}] to "
            f"[{self.sw_latitude}, {self.sw_longitude}]"
        )

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            ne_longitude=float(json.get("ne_lon", 0.0)),
            sw_latitude=float(json.get("sw_lat", 0.0)),
            ne_latitude=float(json.get("ne_lat", 0.0)),
            sw_longitude=float(json.get("sw_lon", 0.0)),
        )


@dataclass
class ChargePointCountry:
    id: int
    name: str
    code: str
    calling_code: int
    phone_format: str
    zoom_bounds: ChargePointZoomBounds

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            id=json.get("id", 0),
            name=json.get("name", ""),
            code=json.get("code", ""),
            calling_code=json.get("callingCode", 1),
            phone_format=json.get("phoneFormat", ""),
            zoom_bounds=ChargePointZoomBounds.from_json(json.get("zoomBounds", {})),
        )


def _safe_get_endpoint(json: dict, endpoint_key: str) -> str:
    return json.get(endpoint_key, {}).get("value", "")


@dataclass
class ChargePointEndpoints:
    accounts: str
    internal_api: str
    mapcache: str
    panda_websocket: str
    payment_java: str
    payment_php: str
    portal_domain: str
    portal_subdomain: str
    sso: str
    webservices: str
    websocket: str

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            accounts=_safe_get_endpoint(json, "accounts_endpoint"),
            internal_api=_safe_get_endpoint(json, "internal_api_gateway_endpoint"),
            mapcache=_safe_get_endpoint(json, "mapcache_endpoint"),
            panda_websocket=_safe_get_endpoint(json, "panda_websocket_endpoint"),
            payment_java=_safe_get_endpoint(json, "payment_java_endpoint"),
            payment_php=_safe_get_endpoint(json, "payment_php_endpoint"),
            portal_domain=_safe_get_endpoint(json, "portal_domain_endpoint"),
            portal_subdomain=_safe_get_endpoint(json, "portal_subdomain"),
            sso=_safe_get_endpoint(json, "sso_endpoint"),
            webservices=_safe_get_endpoint(json, "webservices_endpoint"),
            websocket=_safe_get_endpoint(json, "websocket_endpoint"),
        )


@dataclass
class ChargePointCurrency:
    code: str
    name: str
    card_cost: float
    symbol: str
    initial_deposit: float
    replenishment_threshold: float
    max_decimal_places: int

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            code=json.get("code", ""),
            name=json.get("name", ""),
            card_cost=json.get("cardCost", 0.0),
            symbol=json.get("symbol", ""),
            initial_deposit=json.get("initialDeposit", 0.0),
            replenishment_threshold=json.get("replenishmentThreshold", 0.0),
            max_decimal_places=json.get("maxDecimalPlaces", 0),
        )


@dataclass
class ChargePointGlobalConfiguration:
    region: str

    default_country: ChargePointCountry
    supported_countries: List[ChargePointCountry]

    default_currency: ChargePointCurrency
    supported_currencies: List[ChargePointCurrency]

    endpoints: ChargePointEndpoints

    @classmethod
    def from_json(cls, json: dict):
        default_ctr = ChargePointCountry.from_json(json.get("defaultCountry", {}))
        supported_ctr = [
            ChargePointCountry.from_json(country)
            for country in json.get("supportedCountries", [])
        ]
        default_cur = ChargePointCurrency.from_json(json.get("currency", {}))
        supported_cur = [
            ChargePointCurrency.from_json(currency)
            for currency in json.get("supportedCurrencies", [])
        ]
        epts = ChargePointEndpoints.from_json(json.get("endPoints", {}))

        return cls(
            region=json.get("region", ""),
            default_country=default_ctr,
            supported_countries=supported_ctr,
            default_currency=default_cur,
            supported_currencies=supported_cur,
            endpoints=epts,
        )
