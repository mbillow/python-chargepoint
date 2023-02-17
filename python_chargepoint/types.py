from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from .constants import _LOGGER


@dataclass
class ElectricVehicle:
    make: str
    model: str
    primary_vehicle: bool
    color: str
    image_url: str
    year: int
    charging_speed: int
    dc_charging_speed: int

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            make=json.get("make", {}).get("name", ""),
            model=json.get("model", {}).get("name", ""),
            primary_vehicle=json.get("primaryVehicle", False),
            color=json.get("modelYearColor", {}).get("colorName", ""),
            image_url=json.get("modelYearColor", {}).get("imageUrl", ""),
            year=json.get("modelYear", {}).get("year", 0),
            charging_speed=json.get("modelYear", {}).get("chargingSpeed", 0),
            dc_charging_speed=json.get("modelYear", {}).get("dcChargingSpeed", 0),
        )


@dataclass
class ChargePointUser:
    email: str
    evatar_url: str
    family_name: str
    full_name: str
    given_name: str
    phone: Optional[str]
    phone_country_id: Optional[int]
    user_id: int
    username: str

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            email=json.get("email", ""),
            evatar_url=json.get("evatarUrl", ""),
            family_name=json.get("familyName", ""),
            full_name=json.get("fullName", ""),
            given_name=json.get("givenName", ""),
            phone=json.get("phone"),
            # This seems to be some internal country code.
            # US is 40 and an account with no number doesn't
            # have this attribute.
            phone_country_id=json.get("phoneCountryId"),
            user_id=json.get("userId", 0),
            username=json.get("username", ""),
        )


@dataclass
class AccountBalance:
    account_number: str
    account_state: str
    amount: str
    currency: str

    @classmethod
    def from_json(cls, json: dict):
        balance = json.get("balance", {})
        return cls(
            account_number=json.get("accountNumber", ""),
            account_state=json.get("accountState", ""),
            amount=balance.get("amount", ""),
            currency=balance.get("currency", ""),
        )


@dataclass
class ChargePointAccount:
    user: ChargePointUser
    account_balance: AccountBalance

    @classmethod
    def from_json(cls, json: dict):
        user = ChargePointUser.from_json(json.get("user", {}))
        balance = AccountBalance.from_json(json.get("accountBalance", {}))
        return cls(user=user, account_balance=balance)


@dataclass
class HomeChargerStatus:
    charger_id: int
    brand: Optional[str]
    plugged_in: bool
    connected: bool
    charging_status: str  # "AVAILABLE", "CHARGING", "NOT_CHARGING"
    last_connected_at: datetime
    reminder_enabled: bool
    reminder_time: str
    model: str
    mac_address: str

    @classmethod
    def from_json(cls, charger_id: int, json: dict):
        return cls(
            charger_id=charger_id,
            brand=json.get("brand", ""),
            plugged_in=json.get("is_plugged_in", False),
            connected=json.get("is_connected", False),
            charging_status=json.get("charging_status", ""),
            last_connected_at=datetime.fromtimestamp(
                json.get("last_connected_at", 0) / 1000, tz=timezone.utc
            ),
            reminder_enabled=json.get("is_reminder_enabled", False),
            reminder_time=json.get("plug_in_reminder_time", ""),
            model=json.get("model", ""),
            mac_address=json.get("mac_address", "00:00:00:00:00:00"),
        )


@dataclass
class HomeChargerTechnicalInfo:
    model: str
    serial_number: str
    mac_address: str
    software_version: str
    last_ota_update: datetime
    device_ip: Optional[str]
    last_connected_at: datetime
    is_stop_charge_supported: bool

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            model=json.get("model_number", ""),
            serial_number=json.get("serial_number", ""),
            mac_address=json.get("wifi_mac", "00:00:00:00:00:00"),
            software_version=json.get("software_version", "0.0.0.0"),
            last_ota_update=datetime.fromtimestamp(
                json.get("last_ota_update", 0) / 1000, tz=timezone.utc
            ),
            device_ip=json.get("device_ip"),
            last_connected_at=datetime.fromtimestamp(
                json.get("last_connected_at", 0) / 1000, tz=timezone.utc
            ),
            is_stop_charge_supported=json.get("is_stop_charge_supported", False),
        )


@dataclass
class ChargePointStation:
    id: int
    name: str
    latitude: float
    longitude: float

    @classmethod
    def from_json(cls, json):
        return cls(
            id=json.get("deviceId", 0),
            name=json.get("name", ""),
            latitude=json.get("lat", 0.0),
            longitude=json.get("lon", 0.0),
        )


@dataclass
class UserChargingStatus:
    session_id: int
    start_time: datetime
    state: str  # "in_use", "fully_charged"
    stations: List[ChargePointStation]

    @classmethod
    def from_json(cls, json: dict):
        status = json["charging"]
        state = status.get("state", "unknown")
        if state == "unknown":
            _LOGGER.warning(
                "Charging status returned without a state. "
                + "This is normally due to the eventually consistent "
                + "nature of the session API."
            )
        return cls(
            session_id=status.get("sessionId", 0),
            start_time=datetime.fromtimestamp(
                status.get("startTimeUTC", 0), tz=timezone.utc
            ),
            state=state,
            stations=[
                ChargePointStation.from_json(station)
                for station in status.get("stations", [])
            ],
        )


@dataclass
class ChargingSessionUpdate:
    energy_kwh: float
    power_kw: float
    timestamp: datetime

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            energy_kwh=json.get("energy_kwh", 0.0),
            power_kw=json.get("power_kw", 0.0),
            timestamp=datetime.fromtimestamp(
                json.get("timestamp", 0) / 1000, tz=timezone.utc
            ),
        )


@dataclass
class PowerUtilityPlan:
    code: str
    id: int
    is_ev_plan: bool
    name: str

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            code=json.get("code", ""),
            id=json.get("id", 0),
            is_ev_plan=json.get("is_ev_plan", False),
            name=json.get("name", ""),
        )


@dataclass
class PowerUtility:
    id: int
    name: str
    plans: List[PowerUtilityPlan]

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            id=json.get("id", 0),
            name=json.get("name", ""),
            plans=[PowerUtilityPlan.from_json(plan) for plan in json.get("plans", [])],
        )
