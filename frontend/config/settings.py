"""Configuração do frontend Django. Valores sensíveis vêm do .env da raiz."""
import os
from pathlib import Path

from django.utils.csp import CSP
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / '.env')


def lista(nome, padrao=''):
    return [item.strip() for item in os.environ.get(nome, padrao).split(',') if item.strip()]


def booleano(nome, padrao):
    return os.environ.get(nome, str(padrao)).strip().lower() in {'1', 'true', 'sim', 'yes'}


# --- Essencial ---------------------------------------------------------------
DEBUG = booleano('DJANGO_DEBUG', False)
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or ('dev-inseguro-troque-em-producao' if DEBUG else '')
if not SECRET_KEY:
    raise RuntimeError('Defina DJANGO_SECRET_KEY no .env quando DJANGO_DEBUG=false.')
ALLOWED_HOSTS = lista('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')
CSRF_TRUSTED_ORIGINS = lista('DJANGO_CSRF_TRUSTED_ORIGINS')

BACKEND_URL = os.environ.get('BACKEND_URL', 'http://127.0.0.1:8001')

# --- Aplicação ---------------------------------------------------------------
INSTALLED_APPS = ['whitenoise.runserver_nostatic', 'django.contrib.staticfiles', 'chat']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.csp.ContentSecurityPolicyMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.request']},
}]

DATABASES = {}  # o frontend não guarda dados; o estado fica no backend

# --- Idioma e fuso -----------------------------------------------------------
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# --- Arquivos estáticos (servidos pelo WhiteNoise também em produção) --------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': ('django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
                    else 'whitenoise.storage.CompressedManifestStaticFilesStorage'),
    },
}

# --- Segurança ---------------------------------------------------------------
# A página não tem scripts nem estilos inline, então tudo pode vir só da própria origem.
SECURE_CSP = {
    'default-src': [CSP.SELF],
    'script-src': [CSP.SELF],
    'style-src': [CSP.SELF],
    'img-src': [CSP.SELF, 'data:'],
    'connect-src': [CSP.SELF],
    'frame-ancestors': [CSP.NONE],
    'base-uri': [CSP.SELF],
    'form-action': [CSP.SELF],
}
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
CSRF_COOKIE_HTTPONLY = False  # o token é lido do <meta>, mas o cookie precisa existir

if not DEBUG:
    # Atrás de um proxy com HTTPS (nginx, Render, Railway...).
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = booleano('DJANGO_SSL_REDIRECT', True)
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', 60 * 60 * 24 * 30))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False  # só ative depois de confirmar o HTTPS em todos os subdomínios
    SILENCED_SYSTEM_CHECKS = ['security.W021']  # o aviso acima é intencional

# --- Logs --------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'simples': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'simples'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')},
    'loggers': {'httpx': {'level': 'WARNING'}},
}
