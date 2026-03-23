from typing import Optional

from aiohttp import ClientResponse


class APIError(Exception):
    """
    Root exception for all module raised errors.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class CommunicationError(APIError):
    """
    Parent class for exceptions that involve communication
    with the ChargePoint API.
    """

    def __init__(
        self, response: ClientResponse, message: str, body: Optional[dict] = None
    ):
        self.response = response
        self.message = message
        self.body = body
        super().__init__(self.message)


class LoginError(CommunicationError):
    """
    Login failed.
    """


class InvalidSession(CommunicationError):
    """
    Login expired.
    """


class DatadomeCaptcha(APIError):
    """
    Hit datadome captcha.
    """

    def __init__(self, captcha: str, message: str):
        self.captcha = captcha
        self.message = message
        super().__init__(self.message)
