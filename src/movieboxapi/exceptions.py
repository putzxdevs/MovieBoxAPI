"""
Custom exceptions for MovieBoxAPI.
"""


class MovieBoxError(Exception):
    """Base exception for all MovieBoxAPI errors."""


class APIError(MovieBoxError):
    """Raised when the MovieBox API returns an error response."""

    def __init__(self, message: str, status_code: int = 0, url: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class RateLimitError(APIError):
    """Raised when the API returns 429 Too Many Requests."""


class GeoBlockError(APIError):
    """Raised when the API returns 403 (geo-blocked or IP blocked)."""


class StreamError(MovieBoxError):
    """Raised when no playable stream URL can be obtained."""


class TokenError(MovieBoxError):
    """Raised when the client cannot acquire an auth token."""