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
            make=json["make"]["name"],
            model=json["model"]["name"],
            primary_vehicle=json["primaryVehicle"],
            color=json["modelYearColor"]["colorName"],
            image_url=json["modelYearColor"]["imageUrl"],
            year=json["modelYear"]["year"],
            charging_speed=json["modelYear"]["chargingSpeed"],
            dc_charging_speed=json["modelYear"]["dcChargingSpeed"],
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
            email=json["email"],
            evatar_url=json["evatarUrl"],
            family_name=json["familyName"],
            full_name=json["fullName"],
            given_name=json["givenName"],
            phone=json.get("phone"),
            # This seems to be some internal country code.
            # US is 40 and an account with no number doesn't
            # have this attribute.
            phone_country_id=json.get("phoneCountryId"),
            user_id=json["userId"],
            username=json["username"],
        )


@dataclass
class AccountBalance:
    account_number: str
    account_state: str
    amount: str
    currency: str

    @classmethod
    def from_json(cls, json: dict):
        balance = json["balance"]
        return cls(
            account_number=json["accountNumber"],
            account_state=json["accountState"],
            amount=balance["amount"],
            currency=balance["currency"],
        )


@dataclass
class ChargePointAccount:
    user: ChargePointUser
    account_balance: AccountBalance

    @classmethod
    def from_json(cls, json: dict):
        user = ChargePointUser.from_json(json["user"])
        balance = AccountBalance.from_json(json["accountBalance"])
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
        device_ip = json.get("device_ip")
        if not device_ip:
            _LOGGER.debug("Panda technical information did not include device IP.")
        return cls(
            model=json["model_number"],
            serial_number=json["serial_number"],
            mac_address=json["wifi_mac"],
            software_version=json["software_version"],
            last_ota_update=datetime.fromtimestamp(
                json["last_ota_update"] / 1000, tz=timezone.utc
            ),
            device_ip=device_ip,
            last_connected_at=datetime.fromtimestamp(
                json["last_connected_at"] / 1000, tz=timezone.utc
            ),
            is_stop_charge_supported=json["is_stop_charge_supported"],
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
            id=json["deviceId"],
            name=json["name"],
            latitude=json["lat"],
            longitude=json["lon"],
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
            session_id=status["sessionId"],
            start_time=datetime.fromtimestamp(status["startTimeUTC"], tz=timezone.utc),
            state=state,
            stations=[
                ChargePointStation.from_json(station) for station in status["stations"]
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
            energy_kwh=json["energy_kwh"],
            power_kw=json["power_kw"],
            timestamp=datetime.fromtimestamp(json["timestamp"] / 1000, tz=timezone.utc),
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
            code=json["code"],
            id=json["id"],
            is_ev_plan=json["is_ev_plan"],
            name=json["name"],
        )


@dataclass
class PowerUtility:
    id: int
    name: str
    plans: List[PowerUtilityPlan]

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            id=json["id"],
            name=json["name"],
            plans=[PowerUtilityPlan.from_json(plan) for plan in json["plans"]],
        )
