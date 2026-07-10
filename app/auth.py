import contextlib

from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from app import limiter

from . import db
from .models import User


auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.before_app_request
def require_setup_or_reset():
    from flask import request

    # Skip static assets
    if request.endpoint in ("static",):
        return

    # If no user exists yet, redirect to setup
    if not User.query.first() and request.endpoint != "auth_bp.setup":
        return redirect(url_for("auth_bp.setup"))

    # If a force_reset flag is present, require reset
    flag_path = Path(current_app.instance_path) / "force_reset.flag"
    if flag_path.exists():
        allowed_endpoints = [
            "auth_bp.reset_password",
            "auth_bp.login",
            "auth_bp.setup",
            "static",
        ]
        if request.endpoint not in allowed_endpoints:
            return redirect(url_for("auth_bp.reset_password"))


@auth_bp.route("/force-reset", methods=["POST"])
@login_required
def trigger_force_reset():
    if not current_user.is_admin:  # adjust this check if needed
        flash("You are not authorized to do this.", "danger")
        return redirect(url_for("routes.index"))

    flag_path = Path(current_app.instance_path) / "force_reset.flag"
    try:
        Path(current_app.instance_path).mkdir(parents=True, exist_ok=True)
        flag_path.write_text("1")
    except OSError as e:
        flash(f"Failed to create force reset flag: {e}", "danger")
        return redirect(url_for("routes.index"))

    flash("Forced password reset activated.", "success")
    return redirect(url_for("routes.index"))


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    if User.query.first():
        return redirect(url_for("auth_bp.login"))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]  # ✅ new field

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth_bp.setup"))

        user = User()
        user.username = username
        user.is_admin = True
        user.role = "admin"
        user.set_password(password)
        db.session.add(user)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to create user: {e}", "danger")
            return redirect(url_for("auth_bp.setup"))

        # Ensure a force reset is NOT pending for fresh setups
        flag_path = Path(current_app.instance_path) / "force_reset.flag"
        if flag_path.exists():
            with contextlib.suppress(OSError):
                flag_path.unlink()

        login_user(user)
        flash("Admin account created and logged in.", "success")
        return redirect(url_for("routes.index"))

    return render_template("setup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    # Primary login endpoint at /login
    # Legacy endpoint also exists at /app/login (routes.py) for backward compatibility
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("routes.index"))
        else:
            flash("Invalid credentials", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth_bp.login"))


@auth_bp.route("/reset", methods=["GET", "POST"])
def reset_password():
    # Reset password even if not logged in (as long as a user exists)
    if not User.query.first():
        return redirect(url_for("auth_bp.setup"))

    user = current_user if current_user.is_authenticated else User.query.first()
    if not user:
        return redirect(url_for("auth_bp.setup"))

    flag_path = Path(current_app.instance_path) / "force_reset.flag"

    if request.method == "POST":
        new = request.form["new_password"]
        confirm = request.form["confirm_password"]

        if new != confirm:
            flash("Passwords do not match.", "error")
        elif len(new) < 8:
            flash("Password too short (minimum 8 characters).", "error")
        else:
            user.set_password(new)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f"Failed to update password: {e}", "error")
                return redirect(url_for("auth_bp.reset_password"))
            # Removing the flag unlocks normal access
            if flag_path.exists():
                with contextlib.suppress(OSError):
                    flag_path.unlink()
            flash("Password changed successfully. Please log in.", "success")
            return redirect(url_for("auth_bp.login"))

    return render_template("auth/reset_password.html")
