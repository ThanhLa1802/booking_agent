"""Test settings — uses SQLite in-memory so tests run without PostgreSQL."""
from .settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Strip middleware that requires external services or is unavailable locally
MIDDLEWARE = [
    m for m in MIDDLEWARE  # noqa: F405
    if "axes" not in m and "whitenoise" not in m
]
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

# Speed up password hashing in tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
