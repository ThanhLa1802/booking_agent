"""Test settings — uses SQLite in-memory so tests run without PostgreSQL."""
from .settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable axes middleware in tests to avoid lockout complications
MIDDLEWARE = [m for m in MIDDLEWARE if "axes" not in m]  # noqa: F405
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

# Speed up password hashing in tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
