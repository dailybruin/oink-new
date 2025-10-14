import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret')

DEBUG = os.getenv('DJANGO_DEBUG', '0') in ('1', 'True', 'true')

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
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

ROOT_URLCONF = 'src.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
                BASE_DIR / 'src' / 'templates',
                BASE_DIR / 'templates',
            ],
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

WSGI_APPLICATION = 'src.wsgi.application'

DATABASES = {}

MONGODB_URI = os.getenv('MONGODB_URI')

if MONGODB_URI:
    import importlib

    if importlib.util.find_spec('djongo'):
        DATABASES['default'] = {
            'ENGINE': 'djongo',
            'CLIENT': {
                'host': MONGODB_URI,
            }
        }
    else:
        import warnings

        warnings.warn('MONGODB_URI is set but djongo is not installed. Falling back to SQLite.')
        DATABASES['default'] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
else:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'src' / 'static',
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_DOMAIN = os.getenv('EMAIL_DOMAIN', 'media.ucla.edu')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

GOOGLE_DRIVE_ROOT = os.getenv('GOOGLE_DRIVE_ROOT', 'https://drive.google.com/drive/folders')

GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
GOOGLE_IMPERSONATE_USER = os.getenv('GOOGLE_IMPERSONATE_USER')
GOOGLE_SHARE_PUBLIC = os.getenv('GOOGLE_SHARE_PUBLIC', '0') in ('1', 'true', 'True')
GOOGLE_SHARE_DOMAIN = os.getenv('GOOGLE_SHARE_DOMAIN')

MONGODB_URI = os.getenv('MONGODB_URI')
NEXTAUTH_SECRET = os.getenv('NEXTAUTH_SECRET')
NEXTAUTH_URL = os.getenv('NEXTAUTH_URL')
