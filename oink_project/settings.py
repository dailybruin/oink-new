import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')

DEBUG = os.getenv('DJANGO_DEBUG', '0') == '1'

ALLOWED_HOSTS = ['*'] if DEBUG else []

CSRF_TRUSTED_ORIGINS = [
    'https://oink.dailybruin.com',
]


# Optional: base URL for asset links when not using S3 (e.g. https://assets3.dailybruin.com).
ASSETS_BASE_URL = os.getenv('ASSETS_BASE_URL', '').strip() or None

# S3 upload – reuse Kerckhoff-style env so you can use the same bucket (no new bucket needed).
# Use real IAM access keys (not placeholders like "key"); in Docker, ensure .env or environment
# passes AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY into the container.
# With S3_ASSETS_UPLOAD_BUCKET=assets.dailybruin.com + AWS keys, Oink uploads images to that
# bucket and the link under each image is https://assets.dailybruin.com/images/{slug}/{stem}-{hash}.jpg
# (same key format as Kerckhoff). Download-on-click is controlled by your CDN/S3 (Content-Disposition).
# S3_SITE_UPLOAD_BUCKET is not used by Oink; only assets bucket is used for image uploads.
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '').strip() or None
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '').strip() or None
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1').strip()
# Bucket to upload images to. Default: S3_ASSETS_UPLOAD_BUCKET so one var = same bucket as Kerckhoff.
AWS_STORAGE_BUCKET_NAME = (
    os.getenv('AWS_STORAGE_BUCKET_NAME', '').strip() or
    os.getenv('S3_BUCKET', '').strip() or
    os.getenv('S3_ASSETS_UPLOAD_BUCKET', '').strip() or
    None
)
# Public URL for image links. Default: https:// + S3_ASSETS_UPLOAD_BUCKET (e.g. https://assets.dailybruin.com).
_s3_domain = (os.getenv('S3_DOMAIN_OF_UPLOADED_IMAGES', '').strip() or
              os.getenv('S3_ASSETS_UPLOAD_BUCKET', '').strip() or None)
if _s3_domain and not _s3_domain.startswith(('http://', 'https://')):
    _s3_domain = f'https://{_s3_domain}'
S3_DOMAIN_OF_UPLOADED_IMAGES = _s3_domain or None

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'packages',  
]

MIDDLEWARE = [
    'oink_project.cors_middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'oink_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'oink_project.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication settings
LOGIN_URL = '/google/login/'
LOGIN_REDIRECT_URL = '/'

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
EMAIL_DOMAIN = os.getenv('EMAIL_DOMAIN', 'media.ucla.edu')

GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', '')
GOOGLE_IMPERSONATE_USER = os.getenv('GOOGLE_IMPERSONATE_USER', '')
GOOGLE_SHARE_PUBLIC = os.getenv('GOOGLE_SHARE_PUBLIC', '0') == '1'
GOOGLE_SHARE_DOMAIN = os.getenv('GOOGLE_SHARE_DOMAIN', '')
REPOSITORY_FOLDER_ID = os.getenv('REPOSITORY_FOLDER_ID', '')
GOOGLE_DRIVE_ROOT = os.getenv('GOOGLE_DRIVE_ROOT', 'https://drive.google.com/drive/folders')

# MongoDB / GridFS configuration (for file storage).
# When MONGODB_FILESTORE_ENABLED=1, fetched images are stored in GridFS and the link under each
# image is your app URL (e.g. https://yoursite.com/files/<id>/); opening it serves the image (no S3).
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'oink')
MONGODB_BUCKET = os.getenv('MONGODB_BUCKET', 'files')
MONGODB_FILESTORE_ENABLED = os.getenv('MONGODB_FILESTORE_ENABLED', '0') == '1'
MONGODB_ASSET_COLLECTION = os.getenv('MONGODB_ASSET_COLLECTION', 'package_assets')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
