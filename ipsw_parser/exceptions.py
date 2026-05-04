class IpswException(Exception):
    """Base exception for IPSW parser failures."""

    pass


class NoSuchBuildIdentityError(IpswException):
    """Raised when a matching build identity cannot be found."""

    pass
