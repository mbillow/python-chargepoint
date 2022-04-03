from requests import Response


class ChargePointBaseException(Exception):
    """
    Root exception for all module raised errors.
    """


class ChargePointCommunicationException(ChargePointBaseException):
    """
    Parent class for exceptions that involve communication
    with the ChargePoint API.
    """

    def __init__(self, response: Response, message: str):
        self.response = response
        self.message = message
        super().__init__(self.message)


class ChargePointLoginError(ChargePointCommunicationException):
    """
    Login failed.
    """


class ChargePointInvalidSession(ChargePointCommunicationException):
    """
    Login expired.
    """
