from datetime import datetime, timezone
from typing import List, Optional

from typing import Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from .constants import _LOGGER


class ElectricVehicle(BaseModel):
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


class User(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    email: str = ""
    evatar_url: str = ""
    family_name: str = ""
    full_name: str = ""
    given_name: str = ""
    phone: Optional[str] = None
    phone_country_id: Optional[int] = None
    user_id: int = 0
    username: str = ""


class AccountBalance(BaseModel):
    account_number: str = Field("", alias="accountNumber")
    account_state: str = Field("", alias="accountState")
    amount: str = ""
    currency: str = ""

    @model_validator(mode="before")
    @classmethod
    def flatten_balance(cls, data: dict) -> dict:
        balance = data.get("balance", {})
        return {**data, "amount": balance.get("amount", ""), "currency": balance.get("currency", "")}


class Account(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    user: User
    account_balance: AccountBalance


class HomeChargerStatus(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

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


class HomeChargerTechnicalInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    model_number: str = ""
    serial_number: str = ""
    wifi_mac: str = ""
    mac_address: str = ""
    software_version: str = "0.0.0.0"
    last_ota_update: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    last_connected_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    device_ip: Optional[str] = None
    stop_charge_supported: bool = False

    @field_validator("last_ota_update", "last_connected_at", mode="before")
    @classmethod
    def parse_ms_timestamp(cls, v: float) -> datetime:
        return datetime.fromtimestamp(v / 1000, tz=timezone.utc)


class LEDBrightness(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    level: int = 5
    in_progress: bool = False
    supported_levels: List[int] = Field(default_factory=list)
    is_enabled: bool = True


class HomeChargerConfiguration(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

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


class Station(BaseModel):
    id: int = Field(0, alias="deviceId")
    name: str = ""
    latitude: float = Field(0.0, alias="lat")
    longitude: float = Field(0.0, alias="lon")


class UserChargingStatus(BaseModel):
    session_id: int = Field(0, alias="sessionId")
    start_time: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), alias="startTimeUTC")
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


class VehicleInfo(BaseModel):
    vehicle_id: int = 0
    battery_capacity: float = 0.0
    make: str = ""
    model: str = ""
    year: int = 0
    ev_range: int = 0
    is_primary_vehicle: bool = False


class ChargingSessionUpdate(BaseModel):
    energy_kwh: float = 0.0
    power_kw: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_ms_timestamp(cls, v: float) -> datetime:
        return datetime.fromtimestamp(v / 1000, tz=timezone.utc)


class PowerUtilityPlan(BaseModel):
    code: Union[str, int] = ""
    id: int = 0
    is_ev_plan: bool = False
    name: str = ""


class PowerUtility(BaseModel):
    id: int = 0
    name: str = ""
    plans: List[PowerUtilityPlan] = Field(default_factory=list)
