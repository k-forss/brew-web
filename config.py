import os
from urllib.parse import quote_plus, unquote, urlparse


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name):
    raw = os.environ.get(name, '')
    return [item.strip() for item in raw.split(',') if item.strip()]


def env_scope_set(name, default=''):
    raw = os.environ.get(name, default)
    return {item.strip() for item in raw.split() if item.strip()}


class Config:
    VERSION = "1.4.0"
    RBAC_ADMIN_ROLE = 'admin'
    RBAC_EDITOR_ROLE = 'editor'
    RBAC_USER_ROLE = 'user'
    RBAC_ROLE_LABELS = {
        RBAC_ADMIN_ROLE: 'Admin',
        RBAC_EDITOR_ROLE: 'Editor',
        RBAC_USER_ROLE: 'User',
    }
    # 🔐 REQUIRED: Change this to a secure random string before deployment
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY or SECRET_KEY == 'changeme-in-production':
        raise RuntimeError("SECRET_KEY must be set in environment (see .env.example).")

    DATABASE_URL = os.environ.get('DATABASE_URL')

    if DATABASE_URL:
        parsed_database_url = urlparse(DATABASE_URL)
        BREW_DB_HOST = parsed_database_url.hostname or 'db'
        BREW_DB_PORT = str(parsed_database_url.port or 5432)
        BREW_DB_NAME = (parsed_database_url.path or '/brewweb').lstrip('/') or 'brewweb'
        BREW_DB_USER = unquote(parsed_database_url.username or 'brewuser')
        BREW_DB_PASSWORD = unquote(parsed_database_url.password or 'brewpass')
    else:
        BREW_DB_HOST = os.environ.get('BREW_DB_HOST', 'db')
        BREW_DB_PORT = os.environ.get('BREW_DB_PORT', '5432')
        BREW_DB_NAME = os.environ.get('BREW_DB_NAME', 'brewweb')
        BREW_DB_USER = os.environ.get('BREW_DB_USER', 'brewuser')
        BREW_DB_PASSWORD = os.environ.get('BREW_DB_PASSWORD', 'brewpass')

    # 🛢️ PostgreSQL connection string for Docker Compose environment
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or (
        f'postgresql://{quote_plus(BREW_DB_USER)}:{quote_plus(BREW_DB_PASSWORD)}'
        f'@{BREW_DB_HOST}:{BREW_DB_PORT}/{BREW_DB_NAME}'
    )

    # 🚫 Disable SQLAlchemy event system overhead
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Enable CSRF protection for forms
    WTF_CSRF_ENABLED = True

    OIDC_ENABLED = env_bool('OIDC_ENABLED', False)
    OIDC_CLIENT_NAME = os.environ.get('OIDC_CLIENT_NAME', 'oidc')
    OIDC_DISCOVERY_URL = os.environ.get('OIDC_DISCOVERY_URL')
    OIDC_CLIENT_ID = os.environ.get('OIDC_CLIENT_ID')
    OIDC_CLIENT_SECRET = os.environ.get('OIDC_CLIENT_SECRET')
    OIDC_SCOPES = os.environ.get('OIDC_SCOPES', 'openid profile email groups')
    OIDC_SCOPE_SET = env_scope_set('OIDC_SCOPES', OIDC_SCOPES)
    OIDC_USERNAME_CLAIM = os.environ.get('OIDC_USERNAME_CLAIM', 'preferred_username')
    OIDC_EMAIL_CLAIM = os.environ.get('OIDC_EMAIL_CLAIM', 'email')
    OIDC_EMAIL_VERIFIED_CLAIM = os.environ.get('OIDC_EMAIL_VERIFIED_CLAIM', 'email_verified')
    OIDC_NAME_CLAIM = os.environ.get('OIDC_NAME_CLAIM', 'name')
    OIDC_GROUPS_CLAIM = os.environ.get('OIDC_GROUPS_CLAIM', 'groups')
    OIDC_ROLE_CLAIM = os.environ.get('OIDC_ROLE_CLAIM', OIDC_GROUPS_CLAIM)
    OIDC_ADMIN_GROUPS = env_list('OIDC_ADMIN_GROUPS')
    OIDC_EDITOR_GROUPS = env_list('OIDC_EDITOR_GROUPS')
    OIDC_USER_GROUPS = env_list('OIDC_USER_GROUPS')
    OIDC_DEFAULT_ROLE = os.environ.get('OIDC_DEFAULT_ROLE', RBAC_USER_ROLE).strip().lower() or RBAC_USER_ROLE
    OIDC_ALLOW_UNMAPPED_USERS = env_bool('OIDC_ALLOW_UNMAPPED_USERS', True)
    LOCAL_USER_ROLES = [role.strip().lower() for role in env_list('LOCAL_USER_ROLES')] or [
        RBAC_ADMIN_ROLE,
        RBAC_EDITOR_ROLE,
        RBAC_USER_ROLE,
    ]
    OIDC_CONFIGURED = all([
        OIDC_ENABLED,
        OIDC_DISCOVERY_URL,
        OIDC_CLIENT_ID,
        OIDC_CLIENT_SECRET,
    ])
    DISABLE_LOCAL_LOGIN = env_bool('DISABLE_LOCAL_LOGIN', OIDC_CONFIGURED)

    if OIDC_CONFIGURED and 'groups' not in OIDC_SCOPE_SET:
        raise RuntimeError("OIDC_SCOPES must include 'groups' for group-based authorization.")

    if OIDC_CONFIGURED and not OIDC_ADMIN_GROUPS:
        raise RuntimeError('OIDC_ADMIN_GROUPS must be set for OIDC authorization.')

    if OIDC_DEFAULT_ROLE not in {RBAC_ADMIN_ROLE, RBAC_EDITOR_ROLE, RBAC_USER_ROLE}:
        raise RuntimeError('OIDC_DEFAULT_ROLE must be one of admin, editor, or user.')

    if not set(LOCAL_USER_ROLES).issubset({RBAC_ADMIN_ROLE, RBAC_EDITOR_ROLE, RBAC_USER_ROLE}):
        raise RuntimeError('LOCAL_USER_ROLES must only contain admin, editor, or user.')

    if DISABLE_LOCAL_LOGIN and not OIDC_CONFIGURED:
        raise RuntimeError('DISABLE_LOCAL_LOGIN requires a complete OIDC configuration.')
