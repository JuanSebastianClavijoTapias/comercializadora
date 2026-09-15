"""Settings para ejecutar la suite de tests sin depender de Postgres.

Uso:
    ./env/bin/python manage.py test --settings=fruta_system.settings_test
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
