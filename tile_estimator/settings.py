
"""
Django settings for tile_estimator project.
"""

from datetime import timedelta
import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-key-for-development-only')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

CSRF_TRUSTED_ORIGINS= ['https://tilnet.up.railway.app']
# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',  # Added for token authentication
    'corsheaders',
    'phonenumber_field',
    
    # # Custom apps
     #'accounts',
    # 'estimates',
    # 'subscriptions',
    # 'suppliers',
    # 'admin_api',
    # 'projects',  # Projects app
    # 'manual_estimate',
]
# your_project_name/settings.py
ROOT_URLCONF = 'tile_estimator.urls'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
]

ROOT_URLCONF = 'tile_estimator.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'tile_estimator.wsgi.application'

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True, # Good for production
    )
}

# Custom user model
AUTH_USER_MODEL = 'accounts.CustomUser'

# Password validation
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

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=1340),  # Short, so it forces refresh often
    'REFRESH_TOKEN_LIFETIME': timedelta(days=10),    # 2 days login duration
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}


if not DEBUG:
    ALLOWED_HOSTS = [
        '.railway.app',  # Allows any subdomain of railway.app
        'tilnet.up.railway.app', # Specific Railway domain # Add your custom domains if you have them
    ]
else:
    ALLOWED_HOSTS = ['*'] 
# CORS settings
CORS_ALLOW_ALL_ORIGINS = os.environ.get('CORS_ALLOW_ALL_ORIGINS', 'False').lower() == 'true'
# os.getenv('AFRICASTALKING_API_KEY')
AFRICASTALKING_USERNAME = os.getenv('AFRICASTALKING_USERNAME', 'sandbox') # Keep sandbox for local
AFRICASTALKING_API_KEY = os.getenv('AFRICASTALKING_API_KEY', '') # Empty string default is safer

PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY', '')
PAYSTACK_PUBLIC_KEY = os.getenv('PAYSTACK_PUBLIC_KEY', '')
VERIFICATION_CODE_EXPIRY_MINUTES = 10

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Whitenoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Paystack settings
# PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY', '')
# PAYSTACK_PUBLIC_KEY = os.getenv('PAYSTACK_PUBLIC_KEY', '')
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

LOGGING = {
    "version": 1,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# Subscription plan settings for freemium model
SUBSCRIPTION_PLANS = {
    'free': {
        'name': 'Free',
        'max_projects': 3,
        'max_estimates_per_month': 10,
        'features': ['quick_estimates', 'basic_project_management'],
    },
    'standard': {
        'name': 'Standard',
        'price_monthly': 1500,  # in cents
        'price_yearly': 15000,  # in cents
        'max_projects': 20,
        'max_estimates_per_month': 50,
        'features': ['quick_estimates', 'detailed_project_management', 'pdf_exports', 'supplier_access'],
    },
    'premium': {
        'name': 'Premium',
        'price_monthly': 3000,  # in cents
        'price_yearly': 30000,  # in cents
        'max_projects': -1,  # unlimited
        'max_estimates_per_month': -1,  # unlimited
        'features': ['quick_estimates', 'detailed_project_management', 'pdf_exports', 'supplier_access', 
                     'advanced_analytics', 'team_access', 'api_access', 'priority_support'],
    },
}


# settings.py (at the very bottom of the file)
import logging
logger = logging.getLogger(__name__)
logger.info("Django settings loaded successfully.") # Add this line