import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-change-this-in-production")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "contexts.identity",
    "contexts.compliance",
    "contexts.transfer",
    "contexts.blockchain",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "krypt"),
        "USER": os.getenv("DB_USER", "krypt"),
        "PASSWORD": os.getenv("DB_PASSWORD", "krypt_secret"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "identity.UserModel"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")
CORS_ALLOW_CREDENTIALS = True

# MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "krypt_minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "krypt_minio_secret")
MINIO_BUCKET_KYC = os.getenv("MINIO_BUCKET_KYC", "kyc-documents")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False") == "True"

# Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# AML — architecture de décision 4 couches (KRYP-22, seuils_production.md)
# AML_SCORER_MODE : "mock" (défaut, mock déterministe) ou "tag_ml" (modèle réel shadow)
AML_SCORER_MODE = os.getenv("AML_SCORER_MODE", "mock")
# Couche 4 — taux d'échantillonnage d'audit a posteriori sur les AUTO_APPROVED (1-2%)
AML_AUDIT_SAMPLE_RATE = float(os.getenv("AML_AUDIT_SAMPLE_RATE", "0.02"))

# Blockchain — on-chain transparency/audit layer (KRYP-24, Polygon Amoy).
# Phase 1/2: no real value custody on-chain. Credentials only used by the
# Web3BlockchainService adapter; empty by default so local/CI runs never hit a
# real network. Names mirror the Hardhat side (AMOY_RPC_URL / PRIVATE_KEY).
BLOCKCHAIN_RPC_URL = os.getenv("AMOY_RPC_URL", "")
BLOCKCHAIN_PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
BLOCKCHAIN_CHAIN_ID = int(os.getenv("BLOCKCHAIN_CHAIN_ID", "80002"))

# Celery
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Europe/Paris"

# KRYP-25 — AuditTrail is batched via Merkle tree every 15 minutes, never
# per-transaction (mémoire ch.1 Phase 2: 0.9-1% fee target, comparable TapTap
# Send — one on-chain event per transfer would erode the batching cost savings).
# Static in-settings schedule (no django-celery-beat dependency), consistent
# with the minimal Celery setup.
CELERY_BEAT_SCHEDULE = {
    "submit-audit-batch-every-15-min": {
        "task": "blockchain.submit_audit_batch",
        "schedule": crontab(minute="*/15"),
    },
}

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
