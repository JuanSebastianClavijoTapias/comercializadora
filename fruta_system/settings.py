from pathlib import Path
import os
import sys
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent


# -- helpers ------------------------------------------------------------------

def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ('true', '1', 'yes')


def _env_list(name, default=''):
    raw = os.environ.get(name, default)
    return [h.strip() for h in raw.split(',') if h.strip()]


def _env_required(name):
    value = os.environ.get(name, '')
    if not value:
        raise ImproperlyConfigured(
            f'Variable de entorno requerida no está definida: {name}. '
            f'Agrégala en .env o en el entorno del sistema.'
        )
    return value


# -- SECRET_KEY ---------------------------------------------------------------

SECRET_KEY = os.environ.get('SECRET_KEY', '')
_IS_DEFAULT_KEY = not SECRET_KEY or 'CHANGE-ME' in SECRET_KEY or 'insecure' in SECRET_KEY
if _IS_DEFAULT_KEY:
    raise ImproperlyConfigured(
        'SECRET_KEY no configurada o usa un valor inseguro. Genera una con:\n'
        '  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"\n'
        'y guárdala en .env como SECRET_KEY=<clave>'
    )


# -- DEBUG --------------------------------------------------------------------

DEBUG = _env_bool('DEBUG', False)

# Forzar ALLOWED_HOSTS válido en producción
ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS')
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1'] if DEBUG else []
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        'ALLOWED_HOSTS no configurado. En .env define:\n'
        '  ALLOWED_HOSTS=tudominio.com,www.tudominio.com'
    )

# Detrás de proxy (Nginx / Caddy) — necesario para HTTPS y CSRF
BEHIND_PROXY = not DEBUG and _env_bool('BEHIND_PROXY', True)

# -- apps + middleware --------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'axes',
    'core',
]

MIDDLEWARE = [
    'axes.middleware.AxesMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',
    'django.contrib.auth.backends.ModelBackend',
]

ROOT_URLCONF = 'fruta_system.urls'
TEMPLATES = [{
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
        'builtins': ['core.templatetags.cop_filters'],
    },
}]
WSGI_APPLICATION = 'fruta_system.wsgi.application'


# -- base de datos ------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': _env_required('DB_NAME'),
        'USER': _env_required('DB_USER'),
        'PASSWORD': _env_required('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        # Conexiones persistentes → ahorra handshake SSL/TCP por request
        'CONN_MAX_AGE': int(os.environ.get('CONN_MAX_AGE', 0 if DEBUG else 300)),
        'OPTIONS': {},
    }
}

# SSL para PostgreSQL en producción
if not DEBUG and _env_bool('DB_USE_SSL', False):
    DATABASES['default']['OPTIONS']['sslmode'] = 'require'

# -- cookies / sesión ---------------------------------------------------------

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
SESSION_COOKIE_AGE = 1209600           # 2 semanas
SESSION_EXPIRE_AT_BROWSER_CLOSE = False


# -- contraseñas --------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# -- django-axes: anti brute-force en /login/ y /admin/ -----------------------

AXES_FAILURE_LIMIT = int(os.environ.get('AXES_FAILURE_LIMIT', 5))
AXES_COOLOFF_TIME = int(os.environ.get('AXES_COOLOFF_TIME', 1))     # horas
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]              # bloquea por user + ip
AXES_LOCK_OUT_BY_CONSECUTIVE_FAILURES = True
AXES_RESET_ON_SUCCESS = True
AXES_CACHE_AUTHENTICATED_FAILURES = False

if BEHIND_PROXY:
    AXES_CLIENT_IP_CALLABLE = lambda r: (
        r.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or r.META.get('REMOTE_ADDR', '')
    )


# -- hardening producción -----------------------------------------------------

if not DEBUG:
    # HTTPS
    SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', True)
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', 31536000))  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Proxy (Nginx → Gunicorn)
    if BEHIND_PROXY:
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # Cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
    # Headers de defensa
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'
    # CSRF con HTTPS y proxy
    CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS')
    if not CSRF_TRUSTED_ORIGINS:
        raise ImproperlyConfigured(
            'CSRF_TRUSTED_ORIGINS no configurado. En .env define:\n'
            '  CSRF_TRUSTED_ORIGINS=https://tudominio.com,https://www.tudominio.com'
        )


# -- admin URL configurable ---------------------------------------------------

ADMIN_URL = os.environ.get('ADMIN_URL', 'admin/')
if not ADMIN_URL.endswith('/'):
    ADMIN_URL += '/'


# -- límites de upload (defensa en profundidad) -------------------------------

DATA_UPLOAD_MAX_MEMORY_SIZE = 5_242_880       # 5 MB
FILE_UPLOAD_MAX_MEMORY_SIZE  = 5_242_880       # 5 MB


# -- django-debug-toolbar (solo en DEBUG) -------------------------------------

if DEBUG:
    try:
        import debug_toolbar  # noqa: F401
        INSTALLED_APPS.append('debug_toolbar')
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        INTERNAL_IPS = ['127.0.0.1']
    except ImportError:
        pass


# -- logging ------------------------------------------------------------------

LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_DIR / 'fruta.log'),
            'maxBytes': 5_000_000,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {'handlers': ['file', 'console'], 'level': 'WARNING'},
    'loggers': {
        'django.security':  {'handlers': ['file', 'console'], 'level': 'INFO',     'propagate': False},
        'django.request':   {'handlers': ['file', 'console'], 'level': 'WARNING',  'propagate': False},
        'axes':             {'handlers': ['file', 'console'], 'level': 'INFO',     'propagate': False},
        'core':             {'handlers': ['file', 'console'], 'level': 'INFO',     'propagate': False},
    },
}


# -- checks de validación al inicio -------------------------------------------

_production_checks = []
if not DEBUG:
    if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
        _production_checks.append(
            'ALLOWED_HOSTS contiene "*" o está vacío — debes listar solo tus dominios reales.'
        )
    if 'django-insecure' in SECRET_KEY.lower() or 'CHANGE-ME' in SECRET_KEY:
        _production_checks.append('SECRET_KEY es inseguro.')

if _production_checks:
    msg = '\n  - '.join(_production_checks)
    sys.stderr.write(f'\n[WARN] Configuración de producción:\n  - {msg}\n\n')
