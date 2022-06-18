from python_chargepoint.global_config import ChargePointGlobalConfiguration


def test_global_configuration(global_config_json: dict):
    cfg = ChargePointGlobalConfiguration.from_json(global_config_json)

    assert cfg.region == "NA-US"

    assert cfg.default_country.name == "United States"
    bounds = cfg.default_country.zoom_bounds
    assert bounds.sw_latitude == 11.463275
    assert bounds.__repr__() == "[72.912376, -56.222767] to [11.463275, -165.993456]"
    assert len(cfg.supported_countries) == 20

    assert cfg.default_currency.name == "U.S. Dollars"
    assert len(cfg.supported_currencies) == 11

    assert cfg.endpoints.accounts == "https://account.chargepoint.com/account/"
