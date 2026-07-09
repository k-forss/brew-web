import requests
from functools import wraps
from flask import abort, current_app
from flask_login import current_user
from config import Config
import re
import json
import os


def normalize_role(role):
    if role is None:
        return None
    return str(role).strip().lower()


def role_label(role):
    normalized = normalize_role(role)
    return Config.RBAC_ROLE_LABELS.get(normalized, normalized.title() if normalized else '')


def local_user_role_options():
    return [(role, role_label(role)) for role in Config.LOCAL_USER_ROLES]


def current_user_has_role(*roles):
    if not getattr(current_user, 'is_authenticated', False):
        return False
    allowed_roles = {normalize_role(role) for role in roles}
    return normalize_role(current_user.role) in allowed_roles


def current_user_is_admin():
    return current_user_has_role(Config.RBAC_ADMIN_ROLE)


def current_user_can_edit():
    return current_user_has_role(Config.RBAC_ADMIN_ROLE, Config.RBAC_EDITOR_ROLE)

def is_strong_password(password):
    return (
        len(password) >= 8 and
        re.search(r'[A-Z]', password) and
        re.search(r'[a-z]', password) and
        re.search(r'[\W_]', password)  # requires a symbol
    )

def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            allowed_roles = {normalize_role(role) for role in roles}
            if normalize_role(current_user.role) not in allowed_roles:
                abort(403)
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper


def oidc_enabled():
    return current_app.config.get('OIDC_CONFIGURED', False)


def local_login_enabled():
    return not current_app.config.get('DISABLE_LOCAL_LOGIN', False)

def check_for_updates():
    # Prevent redirects and limit response size
    MAX_VERSION_SIZE = 1024  # 1KB max for version file
    try:
        latest_url = "https://raw.githubusercontent.com/anndrox/brew-web/main/VERSION"
        resp = requests.get(latest_url, timeout=5, allow_redirects=False)
        
        # Security: Reject redirects to prevent SSRF
        if resp.is_redirect:
            return {
                "update_available": False,
                "error": "Redirect not allowed",
                "current": Config.VERSION,
                "latest": "unknown"
            }

        if resp.status_code == 200:
            # Security: Limit response size to prevent DoS
            if len(resp.content) > MAX_VERSION_SIZE:
                return {
                    "update_available": False,
                    "error": "Response too large",
                    "current": Config.VERSION,
                    "latest": "unknown"
                }
            latest_version = resp.text.strip()
            return {
                "update_available": latest_version != Config.VERSION,
                "current": Config.VERSION,
                "latest": latest_version
            }
    except Exception as e:
        return {
            "update_available": False,
            "error": str(e),
            "current": Config.VERSION,
            "latest": "unknown"
        }

    return {
        "update_available": False,
        "current": Config.VERSION,
        "latest": "unknown"
    }

def get_unit_preference():
    """Return 'imperial' or 'metric' based on AppSettings; defaults to imperial on errors."""
    try:
        from app.models import AppSettings  # local import to avoid circular dependency
        settings = AppSettings.query.first()
        if settings and settings.unit_preference in ('imperial', 'metric'):
            return settings.unit_preference
    except Exception:
        pass
    return 'imperial'

def is_metric():
    return get_unit_preference() == 'metric'

def read_import_status_file():
    try:
        path = os.path.join(current_app.instance_path, "import_status.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
# --- Unit helpers ---
def gallons_to_liters(gallons):
    return gallons * 3.78541 if gallons is not None else None

def liters_to_gallons(liters):
    return liters / 3.78541 if liters is not None else None

def f_to_c(fahrenheit):
    return (fahrenheit - 32) * 5 / 9 if fahrenheit is not None else None

def c_to_f(celsius):
    return (celsius * 9 / 5) + 32 if celsius is not None else None
