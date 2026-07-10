import json
import logging
import re
import time

from functools import wraps
from pathlib import Path

import requests

from flask import abort
from flask_login import current_user
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from config import Config


# Module-level cache for check_for_updates()
_update_cache = None
_update_cache_time = 0.0
_UPDATE_CACHE_TTL = 3600  # 1 hour


def is_strong_password(password):
    return (
        len(password) >= 8
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"[\W_]", password)  # requires a symbol
    )


def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)

        return decorated_view

    return wrapper


def check_for_updates(force_refresh=False):
    global _update_cache, _update_cache_time

    current_time = time.time()
    if (
        not force_refresh
        and _update_cache is not None
        and (current_time - _update_cache_time) < _UPDATE_CACHE_TTL
    ):
        return _update_cache

    try:
        latest_url = "https://raw.githubusercontent.com/anndrox/brew-web/main/VERSION"
        resp = requests.get(latest_url, timeout=5)

        if resp.status_code == 200:
            latest_version = resp.text.strip()
            result = {
                "update_available": latest_version != Config.VERSION,
                "current": Config.VERSION,
                "latest": latest_version,
            }
        else:
            result = {"update_available": False, "current": Config.VERSION, "latest": "unknown"}
    except Exception as e:
        result = {
            "update_available": False,
            "error": str(e),
            "current": Config.VERSION,
            "latest": "unknown",
        }

    # Cache the result
    _update_cache = result
    _update_cache_time = current_time
    return result


def get_unit_preference():
    """Return 'imperial' or 'metric' based on AppSettings; defaults to imperial on errors."""
    try:
        from app.models import AppSettings  # local import to avoid circular dependency

        settings = AppSettings.query.first()
        if settings and settings.unit_preference in ("imperial", "metric"):
            return settings.unit_preference
    except ProgrammingError:
        try:
            from app import db

            db.session.execute(
                text(
                    "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS "
                    "unit_preference VARCHAR(10) DEFAULT 'imperial';"
                )
            )
            db.session.commit()
            settings = AppSettings.query.first()
            if settings and settings.unit_preference in ("imperial", "metric"):
                return settings.unit_preference
        except Exception:
            # Log exception before returning default (nosec B110: intentional fallback to default)
            logging.debug(
                "get_unit_preference: exception in nested try, returning default 'imperial'"
            )
            return "imperial"
    except Exception:  # nosec B110
        # Log exception before swallowing (nosec B110: intentional silent fallback to default)
        logging.debug("get_unit_preference: exception occurred, returning default 'imperial'")
        pass
    return "imperial"


def is_metric():
    return get_unit_preference() == "metric"


def read_import_status_file():
    """Read import status from instance path; returns None on any error."""
    try:
        from flask import current_app

        path = Path(current_app.instance_path) / "import_status.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, Exception):
        # Log exception before suppressing
        # nosec B110: intentional silent failure for optional file
        logging.debug("read_import_status_file: exception occurred, returning None")
        return None


# --- Unit helpers ---
def gallons_to_liters(gallons):
    return gallons * 3.78541 if gallons is not None else None


def liters_to_gallons(liters):
    return liters / 3.78541 if liters is not None else None


def f_to_c(fahrenheit):
    return (fahrenheit - 32) * 5 / 9 if fahrenheit is not None else None


def reset_update_cache():
    """Reset the update check cache (useful for testing)."""
    global _update_cache, _update_cache_time
    _update_cache = None
    _update_cache_time = 0


def c_to_f(celsius):
    return (celsius * 9 / 5) + 32 if celsius is not None else None
