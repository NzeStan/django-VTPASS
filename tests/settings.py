SECRET_KEY = "tests-only-secret-key"
DEBUG = False
ALLOWED_HOSTS = ["*"]
USE_TZ = True
TIME_ZONE = "Africa/Lagos"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "vtpass",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@example.com"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
}

VTPASS = {
    "API_KEY": "test-api-key",
    "PUBLIC_KEY": "PK_test",
    "SECRET_KEY": "SK_test",
    "SANDBOX": True,
    "MAX_RETRIES": 0,
    "RETRY_BACKOFF": 0,
    "WALLET_BACKEND": "vtpass.wallets.ModelWalletBackend",
    "MESSAGING": {"PUBLIC_KEY": "VT_PK_test", "SECRET_KEY": "VT_SK_test", "DEFAULT_SENDER": "TestCo"},
    "WEBHOOK": {"TOKEN": "hook-secret"},
    "API": {"PURCHASE_THROTTLE_RATE": None, "VERIFY_THROTTLE_RATE": None},
}
