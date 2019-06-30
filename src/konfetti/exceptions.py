class KonfettiError(Exception):
    """Common error for all errors in `konfetti`."""


class MissingError(AttributeError, KonfettiError):
    """Config option is missing in the given settings module."""

    # Should be inherited from AttributeError because tools like Celery rely
    # on this behavior


class SettingsNotSpecified(KonfettiError):
    """Environment variable, that points to a setting module is not set."""


class SettingsNotLoadable(KonfettiError):
    """Settings module is not found or can't be imported."""


class VaultBackendMissing(KonfettiError):
    """A secret variable is accessed, but vault backend is not configured."""


class SecretKeyMissing(MissingError):
    """Path exists in Vault, but doesn't contain specified value."""


class ForbiddenOverrideError(KonfettiError):
    """An attempt to override configuration with a key that doesn't exist in the configuration."""


class InvalidSecretOverrideError(KonfettiError):
    """Environment variable for secret override contains invalid or non-JSON data."""
