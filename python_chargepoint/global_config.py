from typing import Annotated, List

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from yarl import URL

EndpointURL = Annotated[
    URL, BeforeValidator(lambda v: URL(v) if isinstance(v, str) else v)
]


class ZoomBounds(BaseModel):
    ne_lon: float = 0.0
    ne_lat: float = 0.0
    sw_lon: float = 0.0
    sw_lat: float = 0.0

    def __repr__(self) -> str:
        return f"[{self.ne_lat}, {self.ne_lon}] to " f"[{self.sw_lat}, {self.sw_lon}]"


class Country(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: int = 0
    name: str = ""
    code: str = ""
    calling_code: int = 1
    phone_format: str = ""
    zoom_bounds: ZoomBounds = Field(default_factory=ZoomBounds)


class APIEndpoints(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    accounts_endpoint: EndpointURL = URL("")
    internal_api_gateway_endpoint: EndpointURL = URL("")
    mapcache_endpoint: EndpointURL = URL("")
    panda_websocket_endpoint: EndpointURL = URL("")
    payment_java_endpoint: EndpointURL = URL("")
    payment_php_endpoint: EndpointURL = URL("")
    portal_domain_endpoint: EndpointURL = URL("")
    portal_subdomain: str = ""
    sso_endpoint: EndpointURL = URL("")
    webservices_endpoint: EndpointURL = URL("")
    websocket_endpoint: EndpointURL = URL("")
    hcpo_hcm_endpoint: EndpointURL = URL("")

    @model_validator(mode="before")
    @classmethod
    def extract_endpoint_values(cls, data: dict) -> dict:
        return {
            k: v.get("value", "") if isinstance(v, dict) else v for k, v in data.items()
        }


class Currency(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    code: str = ""
    name: str = ""
    card_cost: float = 0.0
    symbol: str = ""
    initial_deposit: float = 0.0
    replenishment_threshold: float = 0.0
    max_decimal_places: int = 0


class GlobalConfiguration(BaseModel):
    region: str = ""
    default_country: Country = Field(default_factory=Country, alias="defaultCountry")
    supported_countries: List[Country] = Field(
        default_factory=list, alias="supportedCountries"
    )
    default_currency: Currency = Field(default_factory=Currency, alias="currency")
    supported_currencies: List[Currency] = Field(
        default_factory=list, alias="supportedCurrencies"
    )
    endpoints: APIEndpoints = Field(default_factory=APIEndpoints, alias="endPoints")
