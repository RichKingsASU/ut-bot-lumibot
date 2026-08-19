import os
from urllib.parse import urlparse
from django.core.exceptions import ImproperlyConfigured
from .base import *  # noqa: F403
if SECRET_KEY == "unsafe-development-key-do-not-deploy" or len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be unique and at least 50 characters")
database_url = os.environ.get("DATABASE_URL")
if not database_url: raise ImproperlyConfigured("DATABASE_URL is required")
db = urlparse(database_url)
if db.scheme not in {"postgres", "postgresql"}: raise ImproperlyConfigured("Production DATABASE_URL must use PostgreSQL")
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": db.path.lstrip("/"), "USER": db.username, "PASSWORD": db.password, "HOST": db.hostname, "PORT": db.port or 5432, "CONN_MAX_AGE": 60, "CONN_HEALTH_CHECKS": True, "OPTIONS": {"sslmode": os.environ.get("DATABASE_SSLMODE", "require")}}}
DEBUG = False; SECURE_SSL_REDIRECT = True; SESSION_COOKIE_SECURE = True; SESSION_COOKIE_HTTPONLY = True; SESSION_COOKIE_SAMESITE = "Strict"; CSRF_COOKIE_SECURE = True; CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if x]
SECURE_HSTS_SECONDS = 31536000; SECURE_HSTS_INCLUDE_SUBDOMAINS = True; SECURE_HSTS_PRELOAD = True; SECURE_CONTENT_TYPE_NOSNIFF = True; SECURE_REFERRER_POLICY = "same-origin"; X_FRAME_OPTIONS = "DENY"; SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
