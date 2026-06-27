"""
Django settings for the Sova project.

Customized from `django-admin startproject` defaults:
- Secrets loaded from .env (never hardcoded)
- Postgres via DATABASE_URL (replaces SQLite)
- Redis cache via django-redis
- Celery broker/backend + DatabaseScheduler for beat
- DRF defaults (pagination)
- CORS open for dev
- Sentry init when DSN is configured
- LangSmith env vars normalized

For details on individual settings: https://docs.djangoproject.com/en/5.0/ref/settings/
"""

import logging
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from celery.schedules import crontab
from dotenv import load_dotenv


# ---------- Paths & env loading ----------
# BASE_DIR points to the project root (the folder containing manage.py).
# Anything we reference by path should use this so the project is location-independent.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from .env into os.environ.
# In Docker, env vars are already injected via docker-compose's `env_file: .env`,
# but this also covers running manage.py outside Docker (e.g. local scripts, tests).
load_dotenv(BASE_DIR / '.env')


# ---------- Core security ----------
# SECRET_KEY signs cookies, CSRF tokens, password reset tokens.
# Must come from .env. The fallback exists only to avoid crashes during local
# setup before .env is created — it is NOT safe for production.
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-fallback-change-me')

# DEBUG=True shows full stack traces in the browser. Useful in dev, dangerous in prod.
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

# ALLOWED_HOSTS controls which Host headers Django will respond to.
# Comma-separated in .env, e.g. "localhost,127.0.0.1,api.sova.example.com"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if h.strip()
]


# ---------- Installed apps ----------
INSTALLED_APPS = [
    # Django built-ins
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',          # DRF — API serializers, viewsets, browsable API
    'corsheaders',             # CORS headers middleware
    'drf_yasg',                # Swagger / OpenAPI docs
    'django_celery_beat',      # Stores Celery beat schedule in Postgres (editable via admin)

    # Sova apps
    'core',
    'collectors',
    'tools',
    'orchestrator',
    'chatbot',
    'knowledge',
]


# ---------- Middleware ----------
# Runs in order on every request. Order matters — CORS must come BEFORE CommonMiddleware
# so cross-origin preflight requests are answered before Django's URL routing intercepts them.
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'sova.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sova.wsgi.application'


# ---------- Database (Postgres) ----------
# We parse DATABASE_URL manually (e.g. postgresql://user:password@host:port/dbname).
# A library called dj-database-url does this for us, but parsing it manually here
# avoids an extra dependency and makes the mapping explicit for learning.
_db_url = os.getenv(
    'DATABASE_URL',
    'postgresql://sova:changeme_in_production@db:5432/sova',
)
_parsed_db = urlparse(_db_url)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': _parsed_db.path.lstrip('/'),
        'USER': _parsed_db.username,
        'PASSWORD': _parsed_db.password,
        'HOST': _parsed_db.hostname,
        'PORT': str(_parsed_db.port or 5432),
        'CONN_MAX_AGE': 60,  # Reuse DB connections for 60s instead of opening one per request.
    }
}


# ---------- Cache (Redis) ----------
# django-redis lets us use Django's cache framework (cache.get/cache.set/cache.add)
# backed by Redis. We use cache.add() for distributed locks across Celery workers.
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}


# ---------- Celery ----------
# Celery is configured here using Django settings prefixed with CELERY_.
# The Celery app in sova/celery.py reads these via `config_from_object('django.conf:settings', namespace='CELERY')`.
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
# DatabaseScheduler stores the beat schedule in Postgres (via django_celery_beat tables).
# This lets us add/edit periodic tasks through the Django admin without restarting workers.
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Periodic tasks. DatabaseScheduler will mirror these into the django_celery_beat
# DB tables on first run, after which they're editable via the Django admin.
CELERY_BEAT_SCHEDULE = {
    'health-check-hourly': {
        'task': 'orchestrator.tasks.check_collector_health',
        'schedule': timedelta(hours=1),
    },
    'lead-score-daily': {
        'task': 'orchestrator.tasks.recompute_all_lead_scores',
        'schedule': crontab(hour=2, minute=0),
    },
    'google-places-daily': {
        'task': 'collectors.tasks.practice_data.google_places_batch',
        'schedule': crontab(hour=3, minute=0),
    },
}


# ---------- API key authentication ----------
# Shared-secret API key. Clients send X-API-Key header.
SOVA_API_KEY = os.getenv('SOVA_API_KEY', '')


# ---------- External data-source API keys ----------
# Collectors read these from Django settings. Missing keys cause the relevant
# collector to log a warning and return 0 records (no crash).
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')


# ---------- REST framework ----------
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',  # The HTML interface at /api/*
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.SovaAPIKeyAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


# ---------- CORS ----------
# Dev-only: allow any origin. Tighten before production (use CORS_ALLOWED_ORIGINS=[...]).
CORS_ALLOW_ALL_ORIGINS = True


# ---------- Sentry (optional) ----------
# Only initializes when SENTRY_DSN is set in .env. Safe to leave empty in dev.
SENTRY_DSN = os.getenv('SENTRY_DSN', '').strip()
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )


# ---------- Log scrubbing for noisy clients ----------
# httpx logs the full request URL at INFO level. Some providers (Google Maps,
# RapidAPI, etc.) put API keys in query strings — those keys would land in
# stdout, Sentry, and any log aggregator. Silence INFO-and-below for httpx
# and httpcore; WARNING-and-above still surfaces real problems.
#
# Trade-off: you lose the "this URL was called" debug breadcrumb in dev. If
# you genuinely need it for a one-off investigation, set the level back to
# logging.INFO temporarily (and rotate the key after you're done).
for _noisy_logger in ('httpx', 'httpcore'):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)


# ---------- LangSmith (LangChain observability) ----------
# Exposed as Django settings (so SovaConfig.is_langsmith_enabled() can read them
# via django.conf.settings) AND as os.environ (so the langsmith client picks
# them up directly — it reads env vars, not Django settings).
LANGSMITH_API_KEY = os.getenv('LANGSMITH_API_KEY', '')
LANGSMITH_TRACING = os.getenv('LANGSMITH_TRACING', 'false').lower() in ('true', '1', 'yes')
LANGSMITH_PROJECT = os.getenv('LANGSMITH_PROJECT', 'sova')

os.environ['LANGSMITH_API_KEY'] = LANGSMITH_API_KEY
os.environ['LANGSMITH_TRACING'] = 'true' if LANGSMITH_TRACING else 'false'
os.environ['LANGSMITH_PROJECT'] = LANGSMITH_PROJECT


# ---------- Django defaults (kept as-is) ----------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True  # Store all datetimes as timezone-aware UTC.

STATIC_URL = 'static/'

# BigAutoField (64-bit) is the safe default for primary keys. We'll have tables
# with millions of rows; 32-bit AutoField would eventually overflow.
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
