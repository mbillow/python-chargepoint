from logging import getLogger

from yarl import URL

_LOGGER = getLogger("chargepoint")

DISCOVERY_API = URL("https://discovery.chargepoint.com/discovery/v3/globalconfig")
