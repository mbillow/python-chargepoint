from chargepoint.types import ElectricVehicle


def test_electric_vehicle_from_json():
    json = {
        "id": 0,
        "make": {
            "id": 0,
            "name": "Pytest"
        },
        "model": {
            "defaultSelect": False,
            "id": 1,
            "name": "Test"
        },
        "modelYear": {
            "chargingSpeed": 11.0,
            "dcChargingSpeed": 150.0,
            "year": 2021
        },
        "modelYearColor": {
            "colorId": 0,
            "colorName": "Green",
            "defaultSelect": False,
            "imageUrl": "https://pytest.com"
        },
        "primaryVehicle": True
    }
    ev = ElectricVehicle.from_json(json)
    assert ev.year == 2021
    assert ev.color == "Green"
    assert ev.make == "Pytest"
    assert ev.model == "Test"
    assert ev.charging_speed == 11.0
    assert ev.dc_charging_speed == 150.0
    assert ev.image_url == "https://pytest.com"
    assert ev.primary_vehicle is True
