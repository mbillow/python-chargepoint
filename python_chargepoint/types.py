from dataclasses import dataclass
from datetime import datetime
from typing import List

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
    evatarUrl: str
    familyName: str
    fullName: str
    givenName: str
    phone: str
    phoneCountryId: int
    userId: int
    username: str

    @classmethod
    def from_json(cls, json: dict):
        return cls(
            email=json["email"],
            evatarUrl=json["evatarUrl"],
            familyName=json["familyName"],
            fullName=json["fullName"],
            givenName=json["givenName"],
            phone=json["phone"],
            phoneCountryId=json["phoneCountryId"],
            userId=json["userId"],
            username=json["username"],
        )


@dataclass
class AccountBalance:
    accountNumber: str
    accountState: str
    amount: str
    currency: str

    @classmethod
    def from_json(cls, json: dict):
        balance = json["balance"]
        return cls(
            accountNumber=json["accountNumber"],
            accountState=json["accountState"],
            amount=balance["amount"],
            currency=balance["currency"],
        )


@dataclass
class ChargePointAccount:
    user: ChargePointUser
    accountBalance: AccountBalance

    @classmethod
    def from_json(cls, json: dict):
        user = ChargePointUser.from_json(json["user"])
        balance = AccountBalance.from_json(json["accountBalance"])
        return cls(user=user, accountBalance=balance)


@dataclass
class HomeChargerStatus:
    charger_id: int
    brand: str
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
            brand=json["brand"],
            plugged_in=json["is_plugged_in"],
            connected=json["is_connected"],
            charging_status=json["charging_status"],
            last_connected_at=datetime.fromtimestamp(json["last_connected_at"] / 1000),
            reminder_enabled=json["is_reminder_enabled"],
            reminder_time=json["plug_in_reminder_time"],
            model=json["model"],
            mac_address=json["mac_address"],
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
                "Charging status returned without a state. " +
                "This is normally due to the eventually consistent " +
                "nature of the session API."
            )
        return cls(
            session_id=status["sessionId"],
            start_time=datetime.fromtimestamp(status["startTimeUTC"]),
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
            timestamp=datetime.fromtimestamp(json["timestamp"] / 1000),
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
