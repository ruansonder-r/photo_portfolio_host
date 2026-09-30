"""
Django settings for photo_portfolio.

Configuration is environment-driven. For local development, copy .env.example
to .env -- python-dotenv loads it automatically.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------

DEBUG = env_bool("DEBUG", False)

# No insecure fallback in production: a missing SECRET_KEY must fail loudly
# rather than silently signing sessions with a key that is public on GitHub.
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-local-development-only-do-not-deploy"
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable is required when DEBUG is off. "
            "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(50))'"
        )

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,.vercel.app,ruansonder-r.com,www.ruansonder-r.com",
)

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    "https://ruansonder-r.com,https://www.ruansonder-r.com,https://*.vercel.app",
)

ROOT_URLCONF = "photo_portfolio.urls"
WSGI_APPLICATION = "photo_portfolio.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "core",
    "portfolio",
    "albums",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves /static/ directly from the WSGI app. This is what fixes
    # the production 404s -- Vercel's Python runtime publishes no static dir.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_info",
            ],
        },
    },
]


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
# DATABASE_URL takes precedence (Vercel/Neon/Supabase all provide one).
# Falls back to local SQLite so a fresh clone runs with zero setup.

if os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.config(
            conn_max_age=0,  # serverless: never hold pooled connections between invocations
            conn_health_checks=False,
            ssl_require=not DEBUG,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------
# Serverless functions are short-lived, so an in-process cache almost never
# gets a hit. Pages are cheap now (pure DB reads), so we rely on HTTP caching
# via Cache-Control headers instead and keep the local cache as a no-op-ish
# backend for anything that asks for one.

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "photo-portfolio",
    }
}

# How long CDN/browsers may cache public gallery pages (seconds).
PUBLIC_PAGE_CACHE_SECONDS = int(os.environ.get("PUBLIC_PAGE_CACHE_SECONDS", "300"))


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --------------------------------------------------------------------------
# I18N
# --------------------------------------------------------------------------

LANGUAGE_CODE = "en-za"
TIME_ZONE = os.environ.get("TIME_ZONE", "Africa/Johannesburg")
USE_I18N = True
USE_TZ = True


# --------------------------------------------------------------------------
# Static files
# --------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Hashed filenames + gzip/brotli, served with immutable cache headers.
        # The manifest backend needs collectstatic to have run, so development
        # uses the plain backend and serves straight from STATICFILES_DIRS.
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# Let WhiteNoise serve files in development too, so `runserver` behaves the
# same way production does.
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

# Tolerate a template referencing a file that is missing from the manifest
# rather than 500-ing the whole page.
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_MAX_AGE = 31536000


# --------------------------------------------------------------------------
# Image hosting (Cloudinary)
# --------------------------------------------------------------------------
# Set CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>
# The SDK reads that variable directly; the pieces below are used for URL
# building and are derived from it when set individually instead.

CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

# Folder prefixes inside the Cloudinary media library.
CLOUDINARY_PUBLIC_FOLDER = os.environ.get("CLOUDINARY_PUBLIC_FOLDER", "portfolio")
CLOUDINARY_PRIVATE_FOLDER = os.environ.get("CLOUDINARY_PRIVATE_FOLDER", "albums")

# Signed private-album URLs stay valid this long. Long enough for a client to
# browse and download an album in one sitting, short enough that a leaked URL
# expires. Pages are marked no-store so the signed URLs are never cached.
PRIVATE_URL_TTL_SECONDS = int(os.environ.get("PRIVATE_URL_TTL_SECONDS", str(6 * 3600)))


# --------------------------------------------------------------------------
# Google Drive (one-time migration only -- not used to serve the site)
# --------------------------------------------------------------------------

GOOGLE_DRIVE_CREDENTIALS = os.environ.get("GOOGLE_DRIVE_CREDENTIALS", "")
GOOGLE_DRIVE_CREDENTIALS_FILE = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_FILE", "")


# --------------------------------------------------------------------------
# Security
# --------------------------------------------------------------------------
# HSTS and SSL redirects are production-only: switching them on in development
# makes the browser pin localhost to https and is painful to undo.

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
