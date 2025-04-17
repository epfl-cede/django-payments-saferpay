INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "payments",
    "tests.test_app",
]

SECRET_KEY = "django-insecure-secret-key"

ROOT_URLCONF = "tests.django_urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "ATOMIC_REQUESTS": False,
    }
}

USE_TZ = True

PAYMENT_HOST = "example.com"
PAYMENT_MODEL = "test_app.BaseTestPayment"
PAYMENT_VARIANTS = {
    "saferpay": (
        "django_payments_saferpay.provider.SaferpayProvider",
        {
            "customer_id": "customer_id",
            "terminal_id": "terminal_id",
            "auth_username": "api_username",
            "auth_password": "api_password",
        },
    )
}
