from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:8080", "http://localhost:3000"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "axes",
    "django_celery_beat",
    # Local
    "accounts",
    "catalog",
    "centers",
    "bookings",
    "notifications",
    "auditing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "core_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core_service.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── DRF ──────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
}

# ── SimpleJWT ─────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000"],
)

# ── django-axes (brute force) ─────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_CALLABLE = "accounts.views.axes_lockout_response"

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

# ── Bookings: payment / holds / policy (MOCK) ─────────────────────────────────
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", default="MOCK")
# How long an unpaid booking keeps its seat reserved before auto-release.
BOOKING_HOLD_TTL_SECONDS = env.int("BOOKING_HOLD_TTL_SECONDS", default=900)
# Policy values are placeholders pending the real Trinity VN policy.
CANCEL_FULL_REFUND_DAYS = env.int("CANCEL_FULL_REFUND_DAYS", default=30)
CANCEL_PARTIAL_REFUND_DAYS = env.int("CANCEL_PARTIAL_REFUND_DAYS", default=7)
CANCEL_PARTIAL_REFUND_PCT = env.int("CANCEL_PARTIAL_REFUND_PCT", default=50)
RESCHEDULE_DEADLINE_DAYS = env.int("RESCHEDULE_DEADLINE_DAYS", default=7)
MAX_RESCHEDULES = env.int("MAX_RESCHEDULES", default=2)
# When False, cancellation/reschedule windows are not enforced (tests/dev).
BOOKING_POLICY_ENFORCED = env.bool("BOOKING_POLICY_ENFORCED", default=True)

# ── Notifications (MOCK) ──────────────────────────────────────────────────────
NOTIFICATIONS_ENABLED = env.bool("NOTIFICATIONS_ENABLED", default=True)
NOTIFICATIONS_DISPATCH_ENABLED = env.bool("NOTIFICATIONS_DISPATCH_ENABLED", default=True)

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
# Publish to the "default" queue so it matches the worker's `-Q default`.
# Without this, Celery publishes to the queue named "celery" while the worker
# (and the docs' run commands) listen on "default" — tasks would never run.
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TIMEZONE = TIME_ZONE

# ── Celery beat schedule ──────────────────────────────────────────────────────
CELERY_BEAT_SCHEDULE = {
    "expire-unpaid-hold": {
        "task": "bookings.tasks.expire_unpaid_holds",
        "schedule": timedelta(minutes=5),
    },
    "send-exam-reminders": {
        "task": "notifications.tasks.send_exam_reminders",
        "schedule": timedelta(hours=24),
        "kwargs": {"days_ahead": 3},
    },
    "dispatch-queued-notifications": {
        "task": "notifications.tasks.dispatch_queued",
        "schedule": timedelta(minutes=10),
    },
}
