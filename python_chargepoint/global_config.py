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
            ne_longitude=float(json["ne_lon"]),
            sw_latitude=float(json["sw_lat"]),
            ne_latitude=float(json["ne_lat"]),
            sw_longitude=float(json["sw_lon"]),
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
            id=json["id"],
            name=json["name"],
            code=json["code"],
            calling_code=json.get("callingCode", 1),
            phone_format=json["phoneFormat"],
            zoom_bounds=ChargePointZoomBounds.from_json(json["zoomBounds"]),
        )


@dataclass
class ChargePointEndpoints:
    accounts: str
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
            accounts=json["accounts_endpoint"]["value"],
            mapcache=json["mapcache_endpoint"]["value"],
            panda_websocket=json["panda_websocket_endpoint"]["value"],
            payment_java=json["payment_java_endpoint"]["value"],
            payment_php=json["payment_php_endpoint"]["value"],
            portal_domain=json["portal_domain_endpoint"]["value"],
            portal_subdomain=json["portal_subdomain"]["value"],
            sso=json["sso_endpoint"]["value"],
            webservices=json["webservices_endpoint"]["value"],
            websocket=json["websocket_endpoint"]["value"],
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
            code=json["code"],
            name=json["name"],
            card_cost=json["cardCost"],
            symbol=json["symbol"],
            initial_deposit=json["initialDeposit"],
            replenishment_threshold=json["replenishmentThreshold"],
            max_decimal_places=json["maxDecimalPlaces"],
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
        default_ctr = ChargePointCountry.from_json(json["defaultCountry"])
        supported_ctr = [
            ChargePointCountry.from_json(country)
            for country in json.get("supportedCountries", [])
        ]
        default_cur = ChargePointCurrency.from_json(json["currency"])
        supported_cur = [
            ChargePointCurrency.from_json(currency)
            for currency in json.get("supportedCurrencies", [])
        ]
        epts = ChargePointEndpoints.from_json(json["endPoints"])

        return cls(
            region=json["region"],
            default_country=default_ctr,
            supported_countries=supported_ctr,
            default_currency=default_cur,
            supported_currencies=supported_cur,
            endpoints=epts,
        )
