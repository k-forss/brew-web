import json
import os
import re
import subprocess  # nosec B404
import threading

from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from app.decorators import role_required
from app.utils import check_for_updates, is_strong_password, read_import_status_file

from .models import AppSettings, User, db


BACKUP_FOLDER = Path.cwd() / "backups"
BACKUP_FOLDER.mkdir(exist_ok=True)
IMPORT_STATUS_PATH = None

admin_bp = Blueprint("admin_bp", __name__, url_prefix="/settings/admin")


@admin_bp.route("/")
@login_required
@role_required("admin")
def admin_settings():
    users = User.query.order_by(User.username).all()
    try:
        settings = AppSettings.query.first() or AppSettings()
    except ProgrammingError:
        # Likely missing new columns on restored backup; patch and retry once
        db.session.execute(
            text(
                "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS "
                "unit_preference VARCHAR(10) DEFAULT 'imperial';"
            )
        )
        db.session.commit()
        settings = AppSettings.query.first() or AppSettings()
    if not settings.unit_preference:
        settings.unit_preference = "imperial"
    update_info = check_for_updates()
    backups = sorted([f.name for f in BACKUP_FOLDER.glob("*.sql")], reverse=True)
    import_status = _read_import_status()
    return render_template(
        "settings/admin.html",
        users=users,
        settings=settings,
        update_info=update_info,
        backups=backups,
        import_status=import_status,
    )


@admin_bp.route("/update-base-url", methods=["POST"])
@login_required
@role_required("admin")
def update_base_url():
    settings = AppSettings.query.first() or AppSettings()
    settings.base_url = request.form.get("base_url")
    unit_pref = request.form.get("unit_preference") or settings.unit_preference or "imperial"
    settings.unit_preference = unit_pref if unit_pref in ("imperial", "metric") else "imperial"
    db.session.add(settings)
    db.session.commit()
    flash("Base URL updated.", "success")
    return redirect(url_for("routes.admin_bp.admin_settings"))


@admin_bp.route("/create-user", methods=["POST"])
@login_required
@role_required("admin")
def create_user():
    username = request.form.get("username")
    password = request.form.get("password")
    role = request.form.get("role")

    if User.query.filter_by(username=username).first():
        flash("Username already exists.", "danger")
        return redirect(url_for("routes.admin_bp.admin_settings"))

    if not is_strong_password(password or ""):
        flash("Weak password.", "danger")
        return redirect(url_for("routes.admin_bp.admin_settings"))

    hashed = generate_password_hash(password or "")
    user = User(username=username, password_hash=hashed, role=role)
    db.session.add(user)
    db.session.commit()
    flash("User created.", "success")
    return redirect(url_for("routes.admin_bp.admin_settings"))


@admin_bp.route("/delete-user/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_user(user_id):
    if user_id == current_user.id:
        flash("Cannot delete your own account.", "danger")
        return redirect(url_for("routes.admin_bp.admin_settings"))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted.", "success")
    return redirect(url_for("routes.admin_bp.admin_settings"))


@admin_bp.route("/update-password/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def update_password(user_id):
    user = User.query.get_or_404(user_id)
    new_pw = request.form.get("password")
    if not is_strong_password(new_pw or ""):
        flash(
            "Weak password. Must be 8+ chars with uppercase, lowercase, and special char.", "danger"
        )
        return redirect(url_for("routes.admin_bp.admin_settings"))
    user.set_password(new_pw)
    db.session.commit()
    flash("Password updated.", "success")
    return redirect(url_for("routes.admin_bp.admin_settings"))


@admin_bp.route("/create-backup", methods=["POST"])
@login_required
@role_required("admin")
def create_backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"brewweb_backup_{timestamp}.sql"
    backup_path = BACKUP_FOLDER / filename

    try:
        with backup_path.open("w") as f:
            subprocess.run(  # nosec B603, B607
                [
                    "pg_dump",
                    "-h",
                    "db",
                    "-U",
                    "brewuser",
                    "-d",
                    "brewweb",
                    "--no-owner",
                    "--no-privileges",
                    "--inserts",
                ],
                check=True,
                env={"PGPASSWORD": os.environ.get("PGPASSWORD", "")},
                stdout=f,
            )

        flash("New backup created successfully.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Backup failed: {e}", "danger")

    return redirect(url_for("routes.admin_bp.admin_settings"))


@admin_bp.route("/download-backup/<filename>")
@login_required
@role_required("admin")
def download_backup(filename):
    path = BACKUP_FOLDER / filename
    if not path.resolve().is_relative_to(BACKUP_FOLDER.resolve()):
        flash("Invalid backup filename.", "danger")
        return redirect(url_for("routes.admin_bp.admin_settings"))
    if not path.exists():
        flash("Backup file not found.", "danger")
        return redirect(url_for("routes.admin_bp.admin_settings"))
    return send_file(path, as_attachment=True)


@admin_bp.route("/delete-backup/<filename>", methods=["POST"])
@login_required
@role_required("admin")
def delete_backup(filename):
    path = BACKUP_FOLDER / filename
    if not path.resolve().is_relative_to(BACKUP_FOLDER.resolve()):
        flash("Invalid backup filename.", "danger")
        return redirect(url_for("routes.admin_bp.admin_settings"))
    if path.exists():
        path.unlink()
        flash(f"{filename} deleted.", "success")
    else:
        flash("File not found.", "danger")
    return redirect(url_for("routes.admin_bp.admin_settings"))


@admin_bp.route("/export-db")
@login_required
@role_required("admin")
def export_db():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"brewweb_backup_{timestamp}.sql"
    backup_path = BACKUP_FOLDER / filename

    try:
        with backup_path.open("w") as f_out:
            subprocess.run(  # nosec B603, B607
                [
                    "pg_dump",
                    "-h",
                    "db",
                    "-U",
                    "brewuser",
                    "-d",
                    "brewweb",
                    "--no-owner",
                    "--no-privileges",
                    "--inserts",
                    "--quote-all-identifiers",  # 👈 ensures "User" is preserved
                ],
                check=True,
                env={"PGPASSWORD": os.environ.get("PGPASSWORD", "")},
                stdout=f_out,
            )

        flash("Export completed successfully.", "success")
        return send_file(backup_path, as_attachment=True)

    except subprocess.CalledProcessError as e:
        flash(f"Export failed: {e}", "danger")
        return redirect(url_for("routes.admin_bp.admin_settings"))


@admin_bp.route("/import-db", methods=["POST"])
@login_required
@role_required("admin")
def import_db():
    file = request.files.get("backup_file")
    if not file:
        flash("No file selected.", "danger")
        return redirect(url_for("routes.admin_bp.admin_settings"))

    filename = secure_filename(file.filename or "")
    if not filename.endswith(".sql"):
        flash("Invalid file format. Expected .sql", "danger")
        return redirect(url_for("routes.admin_bp.admin_settings"))

    temp_path = BACKUP_FOLDER / filename
    file.save(temp_path)

    try:
        _write_import_status("running", "Import started; this may take ~30s.")
        _start_background_import(temp_path)
        flash("Import started in background. You will be redirected to status.", "info")
    except Exception as e:
        _write_import_status("error", f"Failed to start import: {e}")
        flash(f"Import failed: {e}", "danger")

    return redirect(url_for("routes.admin_bp.import_status_page"))


@admin_bp.route("/import-status")
def import_status():
    status = _read_import_status()
    return jsonify(status or {"status": "idle", "message": "No import running"})


@admin_bp.route("/import-status/page")
@login_required
@role_required("admin")
def import_status_page():
    status = _read_import_status() or {"status": "idle", "message": "No import running"}
    return render_template("settings/import_status.html", import_status=status)


@admin_bp.route("/import-status/clear", methods=["POST"])
@login_required
@role_required("admin")
def clear_import_status():
    _clear_import_status()
    flash("Import status cleared.", "info")
    return redirect(url_for("routes.admin_bp.admin_settings"))


# ---- import helpers ----
def _start_background_import(sql_path):
    app = current_app._get_current_object()  # type: ignore

    def worker():
        with app.app_context():
            env = os.environ.copy()
            env["PGPASSWORD"] = os.environ.get("PGPASSWORD", "")
            try:
                _write_import_status("running", "Dropping schema…")
                subprocess.run(  # nosec B603, B607
                    [
                        "psql",
                        "-h",
                        "db",
                        "-U",
                        "brewuser",
                        "-d",
                        "brewweb",
                        "-c",
                        "DROP SCHEMA public CASCADE; CREATE SCHEMA public;",
                    ],
                    check=True,
                    env=env,
                )
                _write_import_status("running", "Importing SQL…")
                import_run = subprocess.run(  # nosec B603, B607
                    [
                        "psql",
                        "-h",
                        "db",
                        "-U",
                        "brewuser",
                        "-d",
                        "brewweb",
                        "-f",
                        sql_path,
                    ],
                    check=False,
                    env=env,
                )
                if import_run.returncode != 0:
                    _write_import_status(
                        "running",
                        f"Import completed with return code {import_run.returncode}; continuing…",
                    )
                _write_import_status("running", "Applying schema fixes…")
                _apply_schema_fixes(env)
                _write_import_status("running", "Seeding yeast data…")
                subprocess.run(["flask", "seed-yeasts"], check=False, env=env, cwd=Path.cwd())  # nosec B603, B607
                _write_import_status("success", "Import completed and schema fixed.")
            except subprocess.CalledProcessError as e:
                _write_import_status("error", f"Import failed: {e}")
            except Exception as e:
                _write_import_status("error", f"Unexpected error: {e}")

    threading.Thread(target=worker, daemon=True).start()


def _write_import_status(status, message):
    try:
        instance_path = Path(current_app.instance_path)
        instance_path.mkdir(parents=True, exist_ok=True)
        path = instance_path / "import_status.json"
        path.write_text(
            json.dumps(
                {
                    "status": status,
                    "message": message,
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                },
            ),
            encoding="utf-8",
        )
    except Exception:  # nosec B110
        pass


def _read_import_status():
    return read_import_status_file()


def _clear_import_status():
    try:
        path = Path(current_app.instance_path) / "import_status.json"
        if path.exists():
            path.unlink()
    except Exception:  # nosec B110
        pass


def _latest_local_revision():
    # Look for migrations in /app/migrations/versions
    base_dir = Path(current_app.root_path).parent
    versions_path = base_dir / "migrations" / "versions"
    try:
        entries = sorted([f.name for f in versions_path.glob("*.py")])
        if not entries:
            return None
        revs = [re.split(r"[_\.]", f)[0] for f in entries]
        return revs[-1] if revs else None
    except Exception:
        return None


def _stamp_head_with_fallback(env):
    try:
        subprocess.run(["flask", "db", "stamp", "head"], check=True, env=env, cwd=Path.cwd())  # nosec B603, B607
        return
    except Exception:  # nosec B110
        pass
    # Fallback: manually set alembic_version to local latest revision or known revision id
    rev = _latest_local_revision() or "d00abd51392a"
    try:
        db.session.execute(
            text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL);")
        )
        db.session.execute(text("DELETE FROM alembic_version;"))
        db.session.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:rev)"), {"rev": rev}
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


def _apply_schema_fixes(env):
    commands = []
    # Create tables if missing
    commands.extend(
        [
            """
        CREATE TABLE IF NOT EXISTS yeast (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            alcohol_type VARCHAR(20) NOT NULL,
            tolerance VARCHAR(50),
            strength VARCHAR(50),
            sweetness_retention VARCHAR(50),
            notes TEXT,
            flocculation VARCHAR(50),
            attenuation VARCHAR(10),
            is_default BOOLEAN DEFAULT FALSE
        );
        """,
            """
        CREATE TABLE IF NOT EXISTS recipe (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            alcohol_type VARCHAR(20),
            content TEXT,
            created_date TIMESTAMP,
            instructions TEXT,
            notes TEXT,
            water_type VARCHAR(50),
            yeast_id INTEGER REFERENCES yeast(id)
        );
        """,
            """
        CREATE TABLE IF NOT EXISTS batch (
            id SERIAL PRIMARY KEY,
            recipe_id INTEGER REFERENCES recipe(id),
            name VARCHAR(100) NOT NULL,
            start_date TIMESTAMP,
            end_date TIMESTAMP
        );
        """,
            """
        CREATE TABLE IF NOT EXISTS "user" (
            id SERIAL PRIMARY KEY,
            username VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(512) NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            role VARCHAR(50) DEFAULT 'user',
            theme VARCHAR(20) DEFAULT 'dark',
            font_size VARCHAR(10) DEFAULT '16px'
        );
        """,
            """
        CREATE TABLE IF NOT EXISTS ingredient (
            id SERIAL PRIMARY KEY,
            recipe_id INTEGER REFERENCES recipe(id),
            name VARCHAR(100) NOT NULL,
            amount_per_gallon FLOAT,
            unit VARCHAR(20),
            note VARCHAR(200)
        );
        """,
            """
        CREATE TABLE IF NOT EXISTS measurement (
            id SERIAL PRIMARY KEY,
            batch_id INTEGER REFERENCES batch(id),
            date TIMESTAMP,
            gravity FLOAT,
            ph FLOAT,
            temperature FLOAT,
            notes TEXT
        );
        """,
            """
        CREATE TABLE IF NOT EXISTS calendar_event (
            id SERIAL PRIMARY KEY,
            batch_id INTEGER REFERENCES batch(id),
            title VARCHAR(100) NOT NULL,
            start DATE NOT NULL,
            "end" DATE,
            description TEXT,
            all_day BOOLEAN DEFAULT TRUE,
            created_by INTEGER REFERENCES "user"(id),
            note TEXT
        );
        """,
            """
        CREATE TABLE IF NOT EXISTS app_settings (
            id SERIAL PRIMARY KEY,
            base_url VARCHAR(255),
            unit_preference VARCHAR(10) DEFAULT 'imperial'
        );
        """,
        ]
    )
    # Add/patch columns to match current models
    commands.extend(
        [
            "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS "
            "unit_preference VARCHAR(10) DEFAULT 'imperial';",
            "ALTER TABLE recipe ADD COLUMN IF NOT EXISTS yeast_id INTEGER;",
            "ALTER TABLE recipe ADD CONSTRAINT IF NOT EXISTS "
            "recipe_yeast_id_fkey FOREIGN KEY (yeast_id) REFERENCES yeast(id);",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS batch_size FLOAT;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS fermentation_temp VARCHAR(50);",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS initial_gravity FLOAT;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS final_gravity FLOAT;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS abv FLOAT;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS yeast_type VARCHAR(100);",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS backsweetened BOOLEAN;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS flavor_additions TEXT;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS pectic_used BOOLEAN;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS notes TEXT;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS water_type VARCHAR(50);",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS alcohol_type VARCHAR(20);",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS tosna_total FLOAT;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS tosna_per_day FLOAT;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS tosna_enabled BOOLEAN;",
            "ALTER TABLE batch ADD COLUMN IF NOT EXISTS yeast_id INTEGER;",
            "ALTER TABLE batch ADD CONSTRAINT IF NOT EXISTS "
            "batch_yeast_id_fkey FOREIGN KEY (yeast_id) REFERENCES yeast(id);",
            "ALTER TABLE ingredient ADD COLUMN IF NOT EXISTS amount_per_gallon FLOAT;",
            "ALTER TABLE ingredient ADD COLUMN IF NOT EXISTS unit VARCHAR(20);",
            "ALTER TABLE ingredient ADD COLUMN IF NOT EXISTS note VARCHAR(200);",
            "ALTER TABLE measurement ADD COLUMN IF NOT EXISTS ph FLOAT;",
            "ALTER TABLE measurement ADD COLUMN IF NOT EXISTS temperature FLOAT;",
        ]
    )

    for cmd in commands:
        subprocess.run(  # nosec B603, B607
            ["psql", "-h", "db", "-U", "brewuser", "-d", "brewweb", "-c", cmd],
            check=False,
            env=env,
        )
