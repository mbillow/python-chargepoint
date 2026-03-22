from yarl import URL

from python_chargepoint.global_config import GlobalConfiguration


def test_global_configuration(global_config_json: dict):
    cfg = GlobalConfiguration.model_validate(global_config_json)

    assert cfg.region == "NA-US"

    assert cfg.default_country.name == "United States"
    bounds = cfg.default_country.zoom_bounds
    assert bounds.sw_lat == 11.463275
    assert bounds.__repr__() == "[72.912376, -56.222767] to [11.463275, -165.993456]"
    assert len(cfg.supported_countries) == 21

    assert cfg.default_currency.name == "U.S. Dollars"
    assert len(cfg.supported_currencies) == 17

    assert cfg.endpoints.accounts_endpoint == URL("https://account.chargepoint.com/account/")
    assert cfg.endpoints.internal_api_gateway_endpoint == URL("https://internal-api-us.chargepoint.com")
