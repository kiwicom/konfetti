class KiwiConfigError(Exception):
    """Common error for all errors in `kwonfig`."""


class MissingError(AttributeError, KiwiConfigError):
    """Config option is missing in the given settings module."""

    # Should be inherited from AttributeError because tools like Celery rely
    # on this behavior


class SettingsNotSpecified(KiwiConfigError):
    """Environment variable, that points to a setting module is not set."""


class SettingsNotLoadable(KiwiConfigError):
    """Settings module is not found or can't be imported."""


class VaultBackendMissing(KiwiConfigError):
    """A secret variable is accessed, but vault backend is not configured."""


class SecretKeyMissing(MissingError):
    """Path exists in Vault, but doesn't contain specified value."""


class ForbiddenOverrideError(KiwiConfigError):
    """An attempt to override configuration with a key that doesn't exist in the configuration."""


class InvalidSecretOverrideError(KiwiConfigError):
    """Environment variable for secret override contains invalid or non-JSON data."""
