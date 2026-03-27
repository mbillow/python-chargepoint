from datetime import datetime, timezone
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from .constants import _LOGGER
from .global_config import ZoomBounds  # noqa: F401 — re-exported for user convenience


def _parse_ms_timestamp(v: float) -> datetime:
    return datetime.fromtimestamp(v / 1000, tz=timezone.utc)


class _BaseModel(BaseModel):
    """Base for all library models. Passes through undeclared API fields for diagnostic use."""

    model_config = ConfigDict(extra="allow")


class _CamelModel(_BaseModel):
    """Base for models whose API responses use camelCase field names."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="allow"
    )


class ElectricVehicle(_BaseModel):
    make: str = ""
    model: str = ""
    primary_vehicle: bool = False
    color: str = ""
    image_url: str = ""
    year: int = 0
    charging_speed: float = 0.0
    dc_charging_speed: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def flatten_nested(cls, data: dict) -> dict:
        return {
            "make": data.get("make", {}).get("name", ""),
            "model": data.get("model", {}).get("name", ""),
            "primary_vehicle": data.get("primaryVehicle", False),
            "color": data.get("modelYearColor", {}).get("colorName", ""),
            "image_url": data.get("modelYearColor", {}).get("imageUrl", ""),
            "year": data.get("modelYear", {}).get("year", 0),
            "charging_speed": data.get("modelYear", {}).get("chargingSpeed", 0.0),
            "dc_charging_speed": data.get("modelYear", {}).get("dcChargingSpeed", 0.0),
        }


class User(_CamelModel):

    email: str = ""
    evatar_url: str = ""
    family_name: str = ""
    full_name: str = ""
    given_name: str = ""
    phone: Optional[str] = None
    phone_country_id: Optional[int] = None
    user_id: int = 0
    username: str = ""


class AccountBalance(_BaseModel):
    account_number: str = Field("", alias="accountNumber")
    account_state: str = Field("", alias="accountState")
    amount: str = ""
    currency: str = ""

    @model_validator(mode="before")
    @classmethod
    def flatten_balance(cls, data: dict) -> dict:
        balance = data.get("balance", {})
        return {
            **data,
            "amount": balance.get("amount", ""),
            "currency": balance.get("currency", ""),
        }


class Account(_CamelModel):

    user: User
    account_balance: AccountBalance


class HomeChargerStatus(_CamelModel):

    charger_id: int = 0
    brand: Optional[str] = None
    model: str = ""
    mac_address: str = ""
    charging_status: str = ""
    is_plugged_in: bool = False
    is_connected: bool = False
    is_reminder_enabled: bool = False
    plug_in_reminder_time: str = ""
    has_utility_info: bool = False
    is_during_scheduled_time: bool = False
    amperage_limit: int = 0
    possible_amperage_limits: List[int] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def flatten_amperage_setting(cls, data: dict) -> dict:
        amperage = data.get("chargeAmperageSettings", {})
        return {
            **data,
            "amperage_limit": amperage.get("chargeLimit", 0),
            "possible_amperage_limits": amperage.get("possibleChargeLimit", []),
        }


class HomeChargerTechnicalInfo(_CamelModel):
    model_number: str = ""
    serial_number: str = ""
    wifi_mac: str = ""
    mac_address: str = ""
    software_version: str = "0.0.0.0"
    last_ota_update: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    last_connected_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    device_ip: Optional[str] = None
    stop_charge_supported: bool = False

    @field_validator("last_ota_update", "last_connected_at", mode="before")
    @classmethod
    def parse_ms_timestamp(cls, v: float) -> datetime:
        return _parse_ms_timestamp(v)


class LEDBrightness(_CamelModel):

    level: int = 5
    in_progress: bool = False
    supported_levels: List[int] = Field(default_factory=list)
    is_enabled: bool = True


class HomeChargerConfiguration(_CamelModel):

    serial_number: str = ""
    mac_address: str = ""
    station_nickname: str = ""
    street_address: str = ""
    has_utility_info: bool = False
    utility: Optional["PowerUtility"] = None
    indicator_light_eco_mode: str = ""
    flashlight_reset: bool = False
    works_with_nest: bool = False
    is_paired_with_nest: bool = False
    is_installed_by_installer: bool = False
    led_brightness: LEDBrightness = Field(default_factory=LEDBrightness)

    @model_validator(mode="before")
    @classmethod
    def unwrap_settings(cls, data: dict) -> dict:
        settings = data.get("settings", data)
        led_brightness = settings.get("led", {}).get("brightness", {})
        return {**settings, "led_brightness": led_brightness}


class ChargeScheduleWindow(_CamelModel):
    start_time: str = ""
    end_time: str = ""
    start_weekday: Optional[int] = None
    end_weekday: Optional[int] = None


class ChargeSchedule(_CamelModel):
    weekdays: ChargeScheduleWindow = Field(default_factory=ChargeScheduleWindow)
    weekends: ChargeScheduleWindow = Field(default_factory=ChargeScheduleWindow)


class HomeChargerSchedule(_CamelModel):
    has_tou_pricing: bool = False
    schedule_enabled: bool = False
    has_utility_info: bool = False
    based_on_utility: Optional["PowerUtility"] = None
    default_schedule: Optional[ChargeSchedule] = None
    user_schedule: Optional[ChargeSchedule] = None
    utility_schedule: Optional[ChargeSchedule] = None


class Station(_BaseModel):
    id: int = Field(0, alias="deviceId")
    name: str = ""
    latitude: float = Field(0.0, alias="lat")
    longitude: float = Field(0.0, alias="lon")


class UserChargingStatus(_BaseModel):
    session_id: int = Field(0, alias="sessionId")
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc), alias="startTimeUTC"
    )
    state: str = "unknown"
    stations: List[Station] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def unwrap_charging(cls, data: dict) -> dict:
        return data.get("charging", data)

    @field_validator("start_time", mode="before")
    @classmethod
    def parse_timestamp(cls, v: float) -> datetime:
        return datetime.fromtimestamp(v, tz=timezone.utc)

    @model_validator(mode="after")
    def check_state(self) -> "UserChargingStatus":
        if not self.state or self.state == "unknown":
            _LOGGER.warning(
                "Charging status returned without a state. "
                + "This is normally due to the eventually consistent "
                + "nature of the session API."
            )
        return self


class VehicleInfo(_BaseModel):
    vehicle_id: int = 0
    battery_capacity: float = 0.0
    make: str = ""
    model: str = ""
    year: int = 0
    ev_range: int = 0
    is_primary_vehicle: bool = False


class ChargingSessionUpdate(_BaseModel):
    energy_kwh: float = 0.0
    power_kw: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_ms_timestamp(cls, v: float) -> datetime:
        return _parse_ms_timestamp(v)


class PowerUtilityPlan(_BaseModel):
    code: Union[str, int] = ""
    id: int = 0
    is_ev_plan: bool = False
    name: str = ""


class PowerUtility(_BaseModel):
    id: int = 0
    name: str = ""
    plans: List[PowerUtilityPlan] = Field(default_factory=list)


class MapFilter(_BaseModel):
    disabled_parking: bool = False
    network_circuitelectric: bool = False
    connector_l2: bool = False
    network_evgo: bool = False
    network_chargepoint: bool = False
    connector_l2_tesla: bool = False
    connector_combo: bool = False
    connector_chademo: bool = False
    connector_l1: bool = False
    connector_l2_nema_1450: bool = False
    status_available: bool = False
    network_bchydro: bool = False
    network_greenlots: bool = False
    network_flo: bool = False
    network_evgateway: bool = False
    network_evconnect: bool = False
    dc_fast_charging: bool = False
    price_free: bool = False
    van_accessible: bool = False
    network_ionna: bool = False
    network_blink: bool = False
    network_mercedes: bool = False
    connector_tesla: bool = False


class StationPort(_BaseModel):
    status_v2: str = ""
    port_type: int = 0
    outlet_number: int = 0
    parking_accessibility: str = ""
    available_power: float = 0.0
    status: str = ""


class MaxPower(_BaseModel):
    unit: str = ""
    max: float = 0.0


class MapChargingInfo(_BaseModel):
    session_id: int = 0
    session_time: int = 0
    energy_kwh: float = 0.0
    energy_kwh_display: str = ""
    currency_iso_code: str = ""
    current_charging: str = ""
    miles_added: float = 0.0
    total_amount: float = 0.0
    payment_type: str = ""
    start_time: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    last_update_data_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    utility: Optional[PowerUtility] = None
    vehicle_info: Optional[VehicleInfo] = None

    @field_validator("start_time", "last_update_data_timestamp", mode="before")
    @classmethod
    def parse_ms_timestamp(cls, v: float) -> datetime:
        return _parse_ms_timestamp(v)


class StationConnector(_CamelModel):

    status: str = ""
    status_v2: str = ""
    display_plug_type: str = ""
    plug_type: str = ""


class StationPortDetail(_CamelModel):

    outlet_number: int = 0
    power_range: MaxPower = Field(default_factory=MaxPower)
    status: str = ""
    status_v2: str = ""
    display_level: str = ""
    level: str = ""
    parking_accessibility: str = ""
    connector_list: List[StationConnector] = Field(default_factory=list)


class StationPortsInfo(_CamelModel):

    ports: List[StationPortDetail] = Field(default_factory=list)
    port_count: int = 0
    dc: bool = False


class StationNetwork(_CamelModel):

    name: str = ""
    display_name: str = ""
    logo_url: str = ""
    in_network: bool = False


class StationAddress(_BaseModel):
    address1: str = ""
    city: str = ""
    state: str = ""


class StationPricingFee(_BaseModel):
    amount: float = 0.0
    unit: str = ""


class StationTouEntry(_CamelModel):

    day: str = ""
    start_time: int = 0
    end_time: int = 0
    fee: StationPricingFee = Field(default_factory=StationPricingFee)


class StationTax(_BaseModel):
    name: str = ""
    percent: float = 0.0


class StationPrice(_CamelModel):

    currency_code: str = ""
    tou_fees: List[StationTouEntry] = Field(default_factory=list)
    guest_fee: Optional[StationPricingFee] = None
    taxes: List[StationTax] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def unwrap_energy_fee(cls, data: dict) -> dict:
        tou_fees = data.get("energyFee", {}).get("touFeeList", [])
        return {**data, "tou_fees": tou_fees}


class StationInfo(_CamelModel):

    device_id: int = 0
    name: List[str] = Field(default_factory=list)
    address: StationAddress = Field(default_factory=StationAddress)
    description: str = ""
    model_number: str = ""
    network: StationNetwork = Field(default_factory=StationNetwork)
    ports_info: StationPortsInfo = Field(default_factory=StationPortsInfo)
    station_status: str = ""
    station_status_v2: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    host_name: str = ""
    open_close_status: str = ""
    max_power: Optional[MaxPower] = None
    access_restriction: str = ""
    parking_accessibility: str = ""
    stop_charge_supported: bool = False
    remote_start_charge: bool = False
    shared_power: bool = False
    reduced_power: bool = False
    station_price: Optional[StationPrice] = None
    device_software_version: str = ""
    last_charged_date: Optional[str] = None


class MapStation(_BaseModel):
    device_id: int = 0
    lat: float = 0.0
    lon: float = 0.0
    name1: str = ""
    name2: Optional[str] = None
    address1: Optional[str] = None
    city: Optional[str] = None
    network_display_name: Optional[str] = None
    network_logo_url: Optional[str] = None
    station_status: str = ""
    station_status_v2: str = ""
    payment_type: str = ""
    parking_accessibility: Optional[str] = None
    total_port_count: int = 0
    ports: List[StationPort] = Field(default_factory=list)
    has_l2: bool = False
    max_power: Optional[MaxPower] = None
    currency_iso_code: Optional[str] = None
    can_remote_start_charge: bool = False
    company_id: Optional[int] = None
    tou_status: Optional[str] = None
    display_level: Optional[str] = None
    waitlist_allowed: bool = False
    access_restriction: Optional[str] = None
    is_home: bool = False
    charging_status: Optional[str] = None
    charging_info: Optional[MapChargingInfo] = None
