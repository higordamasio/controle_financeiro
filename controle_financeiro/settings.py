"""
Django settings for controle_financeiro project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url

# ===== .env =====
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ===== Segurança / Debug =====
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# ===== Apps =====
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # seu app principal (crie com: python manage.py startapp core)
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'controle_financeiro.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # habilita pasta templates/
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'controle_financeiro.wsgi.application'

# ===== Banco de dados (PostgreSQL via DATABASE_URL do .env) =====
DATABASES = {
    "default": dj_database_url.parse(os.getenv("DATABASE_URL"), conn_max_age=600)
}

# ===== Senhas =====
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ===== Internacionalização =====
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = os.getenv("TIME_ZONE", "America/Sao_Paulo")
USE_I18N = True
USE_TZ = True

# ===== Arquivos estáticos =====
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / "static"]

# ===== Outros =====
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = "/admin/login/"
