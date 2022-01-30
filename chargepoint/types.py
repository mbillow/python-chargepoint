from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Callable


@dataclass
class ElectricVehicle:
    make: str
    model: str
    primary_vehicle: bool
    color: str
    imageUrl: str
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
            imageUrl=json["modelYearColor"]["imageUrl"],
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
    def from_json(cls, json: dict):
        return cls(
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
        return cls(
            session_id=status["sessionId"],
            start_time=datetime.fromtimestamp(status["startTimeUTC"]),
            state=status["state"],
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


@dataclass
class ChargingSession:
    session_id: int
    start_time: datetime

    # Device Information
    device_id: int
    device_name: str
    charging_state: str
    charging_time: int
    energy_kwh: float
    miles_added: float
    miles_added_per_hour: float
    outlet_number: int
    port_level: int
    power_kw: float
    purpose: str

    # Payment
    currency_iso_code: str
    payment_completed: bool
    payment_type: str
    pricing_spec_id: int
    total_amount: float

    # API / Misc.
    api_flag: bool
    enable_stop_charging: bool
    has_charging_receipt: bool
    has_utility_info: bool
    is_home_charger: bool
    is_purpose_finalized: bool
    last_update_data_timestamp: datetime
    stop_charge_supported: bool

    # Owner / Location
    company_id: int
    company_name: str
    latitude: float
    longitude: float
    address: str
    city: str
    state_name: str
    country: str
    zipcode: str

    # Session Update History
    update_data: List[ChargingSessionUpdate]
    update_period: int

    utility: Optional[PowerUtility]

    def __init__(self, mod_func: Callable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mod_func = mod_func

    @classmethod
    def from_json(cls, json: dict, mod_func: Callable):
        return cls(
            session_id=json["session_id"],
            start_time=datetime.fromtimestamp(json["start_time"] / 1000),
            device_id=json["device_id"],
            device_name=json["device_name"],
            charging_state=json["current_charging"],
            charging_time=json["charging_time"],
            energy_kwh=json["energy_kwh"],
            miles_added=json["miles_added"],
            miles_added_per_hour=json["miles_added_per_hour"],
            outlet_number=json["outlet_number"],
            port_level=json["port_level"],
            power_kw=json["power_kw"],
            purpose=json["purpose"],
            currency_iso_code=json["currency_iso_code"],
            payment_completed=json["payment_completed"],
            payment_type=json["payment_type"],
            pricing_spec_id=json["pricing_spec_id"],
            total_amount=json["total_amount"],
            api_flag=json["api_flag"],
            enable_stop_charging=json["enable_stop_charging"],
            has_charging_receipt=json["has_charging_receipt"],
            has_utility_info=json["has_utility_info"],
            is_home_charger=json["is_home_charger"],
            is_purpose_finalized=json["is_purpose_finalized"],
            last_update_data_timestamp=datetime.fromtimestamp(
                json["last_update_data_timestamp"] / 1000
            ),
            stop_charge_supported=json["stop_charge_supported"],
            company_id=json["company_id"],
            company_name=json["company_name"],
            latitude=json["lat"],
            longitude=json["lon"],
            address=json["address1"],
            city=json["city"],
            state_name=json["state_name"],
            country=json["country"],
            zipcode=json["zipcode"],
            update_data=[
                ChargingSessionUpdate.from_json(update)
                for update in json["update_data"]
            ],
            update_period=json["update_period"],
            utility=PowerUtility.from_json(json["utility"]),
            mod_func=mod_func,
        )

    def start(self, max_retry: int = 10):
        if not self._mod_func:
            raise RuntimeError("No modification function set")
        self._mod_func(action="start", device_id=self.device_id, max_retry=max_retry)

    def stop(self, max_retry: int = 10):
        if not self._mod_func:
            raise RuntimeError("No modification function set")
        self._mod_func(
            action="stop",
            device_id=self.device_id,
            port_number=self.outlet_number,
            session_id=self.session_id,
            max_retry=max_retry,
        )
