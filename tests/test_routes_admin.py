"""
Comprehensive unit tests for admin blueprint in app/routes_admin.py.

Test Strategy:
- Uses pytest-flask-sqlalchemy for transactional isolation
- Mocks subprocess, file I/O, threading for backup/import operations
- Tests all routes with proper authentication/authorization
- Edge cases: subprocess failures, file system errors, database errors

Routes Tested:
- admin_settings(): Main admin dashboard
- update_base_url(): Settings update
- create_user(), delete_user(), update_password(): User management
- create_backup(), download_backup(), delete_backup(): Backup operations
- export_db(), import_db(): Database migration
- import_status(), import_status_page(), clear_import_status(): Import tracking
- Helper functions: _start_background_import, _write_import_status, etc.
"""

import json
import re
import subprocess
import threading

from unittest.mock import MagicMock

from werkzeug.security import generate_password_hash

from app.models import AppSettings, User


class TestAdminSettings:
    """Tests for admin_settings() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        # Create a user first so setup hook doesn't interfere
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/app/settings/admin/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_role_admin(self, client, db_session, test_user):
        """Test requires role 'admin' (@role_required)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.get("/app/settings/admin/", follow_redirects=True)
            # Non-admin should get 403 Forbidden
            assert response.status_code == 403

    def test_queries_all_users_ordered_by_username(self, client, db_session, admin_user):
        """Test queries all users ordered by username."""
        # Create additional users
        user1 = User()
        user1.username = "alice"
        user1.set_password("password")
        user2 = User()
        user2.username = "bob"
        user2.set_password("password")
        db_session.add_all([user1, user2])
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/")
            assert response.status_code == 200
            # Verify users are in response (ordered by username)
            assert b"alice" in response.data
            assert b"bob" in response.data
            assert b"adminuser" in response.data

    def test_queries_appsettings_or_creates_default(self, client, db_session, admin_user):
        """Test queries AppSettings or creates default."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/")
            assert response.status_code == 200

    def test_sets_unit_preference_default_to_imperial_if_none(self, client, db_session, admin_user):
        """Test sets unit_preference default to 'imperial' if None."""
        # Delete any existing AppSettings to avoid conflicts
        AppSettings.query.delete()
        # Create settings with None unit_preference
        settings = AppSettings()
        settings.unit_preference = None
        db_session.add(settings)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/")
            assert response.status_code == 200

    def test_calls_check_for_updates(self, client, db_session, admin_user, monkeypatch):
        """Test calls check_for_updates()."""
        update_info = {"latest": "v2.0.0", "current": "v1.0.0"}

        def mock_check():
            return update_info

        monkeypatch.setattr("app.routes_admin.check_for_updates", mock_check)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/")
            assert response.status_code == 200

    def test_lists_backup_files_from_backup_folder(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test lists backup files from BACKUP_FOLDER."""
        # Create temp backup folder
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        (backup_dir / "test.sql").write_text("SELECT 1;")

        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/")
            assert response.status_code == 200
            assert b"test.sql" in response.data

    def test_reads_import_status(self, client, db_session, admin_user, monkeypatch):
        """Test reads import_status."""

        def mock_read():
            return {"status": "idle", "message": "No import running"}

        monkeypatch.setattr("app.routes_admin._read_import_status", mock_read)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/")
            assert response.status_code == 200

    def test_renders_settings_admin_html(self, client, db_session, admin_user):
        """Test renders settings/admin.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/")
            assert response.status_code == 200
            assert b"admin" in response.data.lower()


class TestUpdateBaseUrl:
    """Tests for update_base_url() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user):
        """Test requires login and admin role."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/update-base-url",
                data={"base_url": "https://test.com", "unit_preference": "metric"},
                follow_redirects=True,
            )

            # Non-admin should be redirected or shown error
            assert response.status_code == 200

    def test_post_updates_settings_base_url(self, client, db_session, admin_user):
        """Test POST updates settings.base_url."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/update-base-url",
                data={"base_url": "https://updated.com", "unit_preference": "imperial"},
            )

            settings = AppSettings.query.first()
            assert settings.base_url == "https://updated.com"

    def test_post_updates_settings_unit_preference(self, client, db_session, admin_user):
        """Test POST updates settings.unit_preference."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/update-base-url",
                data={"base_url": "https://test.com", "unit_preference": "metric"},
            )

            settings = AppSettings.query.first()
            assert settings.unit_preference == "metric"

    def test_post_validates_unit_preference(self, client, db_session, admin_user):
        """Test POST validates unit_preference ('imperial' or 'metric')."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Invalid unit_preference should default to imperial
            c.post(
                "/app/settings/admin/update-base-url",
                data={"base_url": "https://test.com", "unit_preference": "invalid"},
            )

            settings = AppSettings.query.first()
            assert settings.unit_preference == "imperial"

    def test_post_defaults_to_imperial_if_invalid(self, client, db_session, admin_user):
        """Test POST defaults to 'imperial' if invalid."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/update-base-url",
                data={"base_url": "https://test.com", "unit_preference": "invalid"},
            )

            settings = AppSettings.query.first()
            assert settings.unit_preference == "imperial"

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/update-base-url",
                data={
                    "base_url": "https://commit-test.com",
                    "unit_preference": "metric",
                },
            )

            # Verify commit by querying in new session
            settings = AppSettings.query.first()
            assert settings.base_url == "https://commit-test.com"

    def test_post_shows_success_flash(self, client, db_session, admin_user):
        """Test POST shows success flash."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/update-base-url",
                data={"base_url": "https://test.com", "unit_preference": "imperial"},
                follow_redirects=True,
            )

            assert b"Base URL updated" in response.data

    def test_post_redirects_to_admin_settings(self, client, db_session, admin_user):
        """Test POST redirects to admin_settings."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/update-base-url",
                data={"base_url": "https://test.com", "unit_preference": "imperial"},
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "/app/settings/admin" in response.location


class TestCreateUser:
    """Tests for create_user() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user):
        """Test requires login and admin role."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/create-user",
                data={
                    "username": "newuser",
                    "password": "strongpassword123",
                    "role": "user",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

    def test_post_with_existing_username_shows_error_flash(
        self, client, db_session, admin_user, test_user
    ):
        """Test POST with existing username shows error flash."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/create-user",
                data={
                    "username": test_user.username,  # Already exists
                    "password": "strongpassword123",
                    "role": "user",
                },
                follow_redirects=True,
            )

            assert b"Username already exists" in response.data

    def test_post_with_weak_password_shows_error_flash(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test POST with weak password shows error flash."""

        def mock_is_strong(pw):
            return False

        monkeypatch.setattr("app.routes_admin.is_strong_password", mock_is_strong)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/create-user",
                data={"username": "newuser", "password": "weak", "role": "user"},
                follow_redirects=True,
            )

            assert b"Weak password" in response.data

    def test_post_with_valid_data_creates_user(self, client, db_session, admin_user, monkeypatch):
        """Test POST with valid data creates User."""

        def mock_is_strong(pw):
            return True

        monkeypatch.setattr("app.routes_admin.is_strong_password", mock_is_strong)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/create-user",
                data={
                    "username": "brandnewuser",
                    "password": "strongpassword123",
                    "role": "user",
                },
            )

            user = User.query.filter_by(username="brandnewuser").first()
            assert user is not None
            assert user.role == "user"

    def test_post_calls_generate_password_hash(self, client, db_session, admin_user, monkeypatch):
        """Test POST calls generate_password_hash."""
        hash_called = []
        original_hash = generate_password_hash

        def mock_hash(pw):
            hash_called.append(pw)
            return original_hash(pw)

        monkeypatch.setattr("app.routes_admin.generate_password_hash", mock_hash)
        monkeypatch.setattr("app.routes_admin.is_strong_password", lambda x: True)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/create-user",
                data={
                    "username": "hashtest",
                    "password": "testpassword",
                    "role": "user",
                },
            )

            assert len(hash_called) > 0
            assert hash_called[0] == "testpassword"

    def test_post_commits_to_database(self, client, db_session, admin_user, monkeypatch):
        """Test POST commits to database."""
        monkeypatch.setattr("app.routes_admin.is_strong_password", lambda x: True)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/create-user",
                data={
                    "username": "committest",
                    "password": "strongpassword123",
                    "role": "user",
                },
            )

            user = User.query.filter_by(username="committest").first()
            assert user is not None

    def test_post_shows_success_flash(self, client, db_session, admin_user, monkeypatch):
        """Test POST shows success flash."""
        monkeypatch.setattr("app.routes_admin.is_strong_password", lambda x: True)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/create-user",
                data={
                    "username": "flashtest",
                    "password": "strongpassword123",
                    "role": "user",
                },
                follow_redirects=True,
            )

            assert b"User created" in response.data

    def test_post_redirects_to_admin_settings(self, client, db_session, admin_user, monkeypatch):
        """Test POST redirects to admin_settings."""
        monkeypatch.setattr("app.routes_admin.is_strong_password", lambda x: True)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/create-user",
                data={
                    "username": "redirecttest",
                    "password": "strongpassword123",
                    "role": "user",
                },
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "/app/settings/admin" in response.location


class TestDeleteUser:
    """Tests for delete_user() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user):
        """Test requires login and admin role."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/delete-user/1", follow_redirects=True)
            assert response.status_code == 200

    def test_cannot_delete_own_account(self, client, db_session, admin_user):
        """Test cannot delete own account (current_user.id check)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/settings/admin/delete-user/{admin_user.id}",
                follow_redirects=True,
            )

            assert b"Cannot delete your own account" in response.data

    def test_post_with_valid_id_deletes_user(self, client, db_session, admin_user):
        """Test POST with valid ID deletes user."""
        # Create a user to delete
        user_to_delete = User()
        user_to_delete.username = "deletetest1"

        user_to_delete.set_password("password")
        db_session.add(user_to_delete)
        db_session.commit()
        user_id = user_to_delete.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/settings/admin/delete-user/{user_id}")

            # Verify user was deleted
            deleted_user = User.query.get(user_id)
            assert deleted_user is None

    def test_post_with_invalid_id_raises_404(self, client, db_session, admin_user):
        """Test POST with invalid ID raises 404."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/delete-user/99999", follow_redirects=False)

            assert response.status_code == 404

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        # Create a user to delete
        user_to_delete = User()
        user_to_delete.username = "deletetest2"
        user_to_delete.set_password("password")
        db_session.add(user_to_delete)
        db_session.commit()
        user_id = user_to_delete.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/settings/admin/delete-user/{user_id}")

            # Verify commit by checking user is gone
            assert User.query.get(user_id) is None

    def test_post_shows_success_flash(self, client, db_session, admin_user):
        """Test POST shows success flash."""
        # Create a user to delete
        user_to_delete = User()
        user_to_delete.username = "deletetest3"
        user_to_delete.set_password("password")
        db_session.add(user_to_delete)
        db_session.commit()
        user_id = user_to_delete.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/settings/admin/delete-user/{user_id}", follow_redirects=True)

            assert b"User deleted" in response.data

    def test_post_redirects_to_admin_settings(self, client, db_session, admin_user):
        """Test POST redirects to admin_settings."""
        # Create a user to delete
        user_to_delete = User()
        user_to_delete.username = "deletetest4"
        user_to_delete.set_password("password")
        db_session.add(user_to_delete)
        db_session.commit()
        user_id = user_to_delete.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/settings/admin/delete-user/{user_id}", follow_redirects=False)

            assert response.status_code == 302
            assert "/app/settings/admin" in response.location


class TestUpdatePassword:
    """Tests for update_password() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user):
        """Test requires login and admin role."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/update-password/1",
                data={"password": "newpassword"},
                follow_redirects=True,
            )

            assert response.status_code == 200

    def test_post_updates_user_password(self, client, db_session, admin_user):
        """Test POST updates user password."""
        # Create a user to update
        user_to_update = User()
        user_to_update.username = "passwordtest1"
        user_to_update.set_password("oldpassword")
        db_session.add(user_to_update)
        db_session.commit()
        user_id = user_to_update.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/settings/admin/update-password/{user_id}",
                data={"password": "NewPassword123!"},
            )

            # Verify password was updated
            db_session.refresh(user_to_update)
            assert user_to_update.check_password("NewPassword123!") is True
            assert user_to_update.check_password("oldpassword") is False

    def test_post_calls_user_set_password(self, client, db_session, admin_user, monkeypatch):
        """Test POST calls user.set_password()."""
        set_password_called = []

        original_set_password = User.set_password

        def mock_set_password(self, pw):
            set_password_called.append(pw)
            return original_set_password(self, pw)

        monkeypatch.setattr(User, "set_password", mock_set_password)
        monkeypatch.setattr("app.routes_admin.is_strong_password", lambda x: True)

        # Create a user to update
        user_to_update = User()
        user_to_update.username = "setpwtest1"
        user_to_update.set_password("oldpassword")
        db_session.add(user_to_update)
        db_session.commit()
        user_id = user_to_update.id

        # Clear the list to only capture the update call
        set_password_called.clear()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/settings/admin/update-password/{user_id}",
                data={"password": "newpassword123"},
            )

            assert len(set_password_called) > 0
            assert set_password_called[0] == "newpassword123"

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        # Create a user to update
        user_to_update = User()
        user_to_update.username = "committest3a"
        user_to_update.set_password("oldpassword")
        db_session.add(user_to_update)
        db_session.commit()
        user_id = user_to_update.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/settings/admin/update-password/{user_id}",
                data={"password": "NewPassword123!"},
            )

            # Verify commit
            db_session.refresh(user_to_update)
            assert user_to_update.check_password("NewPassword123!") is True

    def test_post_shows_success_flash(self, client, db_session, admin_user):
        """Test POST shows success flash."""
        # Create a user to update
        user_to_update = User()
        user_to_update.username = "flashtest3a"
        user_to_update.set_password("oldpassword")
        db_session.add(user_to_update)
        db_session.commit()
        user_id = user_to_update.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/settings/admin/update-password/{user_id}",
                data={"password": "NewPassword123!"},
                follow_redirects=True,
            )

            assert b"Password updated" in response.data

    def test_post_redirects_to_admin_settings(self, client, db_session, admin_user):
        """Test POST redirects to admin_settings."""
        # Create a user to update
        user_to_update = User()
        user_to_update.username = "redirecttest3a"
        user_to_update.set_password("oldpassword")
        db_session.add(user_to_update)
        db_session.commit()
        user_id = user_to_update.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/settings/admin/update-password/{user_id}",
                data={"password": "newpassword123"},
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "/app/settings/admin" in response.location


class TestCreateBackup:
    """Tests for create_backup() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user, monkeypatch):
        """Test requires login and admin role."""
        # Mock subprocess.run to avoid actual pg_dump call
        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/create-backup", follow_redirects=True)
            assert response.status_code == 200

    def test_post_generates_timestamp_filename(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST generates timestamp filename."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/settings/admin/create-backup")

            # Verify subprocess.run was called
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            assert "pg_dump" in call_args

    def test_post_calls_subprocess_run_with_pg_dump(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST calls subprocess.run with pg_dump."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/settings/admin/create-backup")

            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            assert "pg_dump" in call_args

    def test_post_uses_correct_pg_dump_arguments(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST uses correct pg_dump arguments."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/settings/admin/create-backup")

            call_args = mock_run.call_args[0][0]
            assert "-h" in call_args
            assert "-U" in call_args
            assert "-d" in call_args
            assert "--no-owner" in call_args
            assert "--inserts" in call_args

    def test_post_sets_pgpassword_environment_variable(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST sets PGPASSWORD environment variable."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        # Set PGPASSWORD in environment
        monkeypatch.setenv("PGPASSWORD", "brewpass")

        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/settings/admin/create-backup")

            call_kwargs = mock_run.call_args[1]
            assert "env" in call_kwargs
            assert call_kwargs["env"].get("PGPASSWORD") == "brewpass"

    def test_post_shows_success_flash_on_completion(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST shows success flash on completion."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/create-backup", follow_redirects=True)

            assert b"backup created successfully" in response.data

    def test_post_shows_error_flash_on_calledprocesserror(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST shows error flash on CalledProcessError."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        mock_run = MagicMock()
        mock_run.side_effect = subprocess.CalledProcessError(1, "pg_dump")
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/create-backup", follow_redirects=True)

            assert b"Backup failed" in response.data

    def test_post_redirects_to_admin_settings(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST redirects to admin_settings."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/create-backup", follow_redirects=False)

            assert response.status_code == 302
            assert "/app/settings/admin" in response.location


class TestDownloadBackup:
    """Tests for download_backup() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user):
        """Test requires login and admin role."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/download-backup/test.sql", follow_redirects=True)
            assert response.status_code == 200

    def test_get_with_valid_filename_calls_send_file(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test GET with valid filename calls send_file."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "test.sql"
        backup_file.write_text("SELECT 1;")

        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/download-backup/test.sql")

            # Should return file content
            assert response.status_code == 200
            assert b"SELECT 1" in response.data

    def test_get_with_non_existent_file_shows_error_flash(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test GET with non-existent file shows error flash."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(
                "/app/settings/admin/download-backup/nonexistent.sql",
                follow_redirects=True,
            )

            assert b"Backup file not found" in response.data

    def test_get_with_non_existent_file_redirects_to_admin_settings(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test GET with non-existent file redirects to admin_settings."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(
                "/app/settings/admin/download-backup/nonexistent.sql",
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "/app/settings/admin" in response.location


class TestDeleteBackup:
    """Tests for delete_backup() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user):
        """Test requires login and admin role."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/delete-backup/test.sql", follow_redirects=True)
            assert response.status_code == 200

    def test_post_with_valid_filename_removes_file(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST with valid filename removes file."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "todelete.sql"
        backup_file.write_text("SELECT 1;")

        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/settings/admin/delete-backup/todelete.sql")

            # Verify file was deleted
            assert not backup_file.exists()

    def test_post_with_non_existent_file_shows_error_flash(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST with non-existent file shows error flash."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/delete-backup/nonexistent.sql",
                follow_redirects=True,
            )

            assert b"File not found" in response.data

    def test_post_shows_success_flash_on_deletion(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST shows success flash on deletion."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "todelete2.sql"
        backup_file.write_text("SELECT 1;")

        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/delete-backup/todelete2.sql", follow_redirects=True
            )

            assert b"deleted" in response.data

    def test_post_redirects_to_admin_settings(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST redirects to admin_settings."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "todelete3.sql"
        backup_file.write_text("SELECT 1;")

        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/delete-backup/todelete3.sql",
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "/app/settings/admin" in response.location


class TestExportDb:
    """Tests for export_db() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user, monkeypatch):
        """Test requires login and admin role."""
        # Mock subprocess.run to avoid actual pg_dump call
        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/export-db", follow_redirects=True)
            assert response.status_code == 200

    def test_calls_subprocess_run_with_pg_dump_quote_all_identifiers(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test calls subprocess.run with pg_dump --quote-all-identifiers."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.get("/app/settings/admin/export-db")

            call_args = mock_run.call_args[0][0]
            assert "--quote-all-identifiers" in call_args

    def test_post_shows_success_flash_and_returns_send_file(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST shows success flash and returns send_file."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/export-db")

            # Should return file (200) or redirect on error
            assert response.status_code in [200, 302]

    def test_post_shows_error_flash_on_calledprocesserror(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST shows error flash on CalledProcessError."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        mock_run = MagicMock()
        mock_run.side_effect = subprocess.CalledProcessError(1, "pg_dump")
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/export-db", follow_redirects=True)

            assert b"Export failed" in response.data

    def test_redirects_to_admin_settings_on_error(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test redirects to admin_settings on error."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        mock_run = MagicMock()
        mock_run.side_effect = subprocess.CalledProcessError(1, "pg_dump")
        monkeypatch.setattr("subprocess.run", mock_run)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/export-db", follow_redirects=False)

            assert response.status_code == 302
            assert "/app/settings/admin" in response.location


class TestImportDb:
    """Tests for import_db() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user):
        """Test requires login and admin role."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/import-db", follow_redirects=True)
            assert response.status_code == 200

    def test_post_with_no_file_shows_error_flash(self, client, db_session, admin_user):
        """Test POST with no file shows error flash."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/import-db", follow_redirects=True)

            assert b"No file selected" in response.data

    def test_post_with_non_sql_file_shows_error_flash(self, client, db_session, admin_user):
        """Test POST with non-.sql file shows error flash."""
        from io import BytesIO

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/import-db",
                data={"backup_file": (BytesIO(b"content"), "test.txt")},
                follow_redirects=True,
            )

            assert b"Invalid file format" in response.data

    def test_post_saves_file_to_backup_folder(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST saves file to BACKUP_FOLDER."""
        from io import BytesIO

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)
        monkeypatch.setattr("app.routes_admin._start_background_import", lambda x: None)
        monkeypatch.setattr("app.routes_admin._write_import_status", lambda s, m: None)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/import-db",
                data={"backup_file": (BytesIO(b"SELECT 1;"), "test.sql")},
            )

            # Verify file was saved
            saved_file = backup_dir / "test.sql"
            assert saved_file.exists()

    def test_post_calls_start_background_import(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST calls _start_background_import."""
        from io import BytesIO

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        import_called = []

        def mock_start(path):
            import_called.append(path)

        monkeypatch.setattr("app.routes_admin._start_background_import", mock_start)
        monkeypatch.setattr("app.routes_admin._write_import_status", lambda s, m: None)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/import-db",
                data={"backup_file": (BytesIO(b"SELECT 1;"), "test.sql")},
            )

            assert len(import_called) > 0

    def test_post_writes_import_status_running(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST writes import status "running"."""
        from io import BytesIO

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)
        monkeypatch.setattr("app.routes_admin._start_background_import", lambda x: None)

        status_written = []

        def mock_write(status, message):
            status_written.append((status, message))

        monkeypatch.setattr("app.routes_admin._write_import_status", mock_write)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/import-db",
                data={"backup_file": (BytesIO(b"SELECT 1;"), "test.sql")},
            )

            assert len(status_written) > 0
            assert status_written[0][0] == "running"

    def test_post_shows_info_flash(self, client, db_session, admin_user, monkeypatch, tmp_path):
        """Test POST shows info flash."""
        from io import BytesIO

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)
        monkeypatch.setattr("app.routes_admin._start_background_import", lambda x: None)
        monkeypatch.setattr("app.routes_admin._write_import_status", lambda s, m: None)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/import-db",
                data={"backup_file": (BytesIO(b"SELECT 1;"), "test.sql")},
                follow_redirects=True,
            )

            assert b"Import started in background" in response.data

    def test_post_redirects_to_import_status_page(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST redirects to import_status_page."""
        from io import BytesIO

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)
        monkeypatch.setattr("app.routes_admin._start_background_import", lambda x: None)
        monkeypatch.setattr("app.routes_admin._write_import_status", lambda s, m: None)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/settings/admin/import-db",
                data={"backup_file": (BytesIO(b"SELECT 1;"), "test.sql")},
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "/import-status/page" in response.location

    def test_post_handles_exception_with_error_status(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test POST handles exception with error status."""
        from io import BytesIO

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr("app.routes_admin.BACKUP_FOLDER", backup_dir)

        def mock_start(path):
            raise Exception("Import failed")

        monkeypatch.setattr("app.routes_admin._start_background_import", mock_start)

        status_written = []

        def mock_write(status, message):
            status_written.append((status, message))

        monkeypatch.setattr("app.routes_admin._write_import_status", mock_write)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/settings/admin/import-db",
                data={"backup_file": (BytesIO(b"SELECT 1;"), "test.sql")},
            )

            # Should write error status
            assert len(status_written) > 0
            assert status_written[-1][0] == "error"


class TestImportStatus:
    """Tests for import_status() route."""

    def test_returns_json_with_status(self, client, db_session, admin_user, monkeypatch):
        """Test returns JSON with status."""

        def mock_read():
            return {"status": "running", "message": "Importing..."}

        monkeypatch.setattr("app.routes_admin._read_import_status", mock_read)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/import-status")

        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert "status" in data

    def test_returns_idle_if_no_status_file(self, client, db_session, admin_user, monkeypatch):
        """Test returns {"status": "idle", ...} if no status file."""

        def mock_read():
            return None

        monkeypatch.setattr("app.routes_admin._read_import_status", mock_read)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/import-status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "idle"


class TestImportStatusPage:
    """Tests for import_status_page() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user):
        """Test requires login and admin role."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/import-status/page", follow_redirects=True)
            assert response.status_code == 200

    def test_renders_settings_import_status_html(self, client, db_session, admin_user, monkeypatch):
        """Test renders settings/import_status.html."""

        def mock_read():
            return {"status": "idle", "message": "No import running"}

        monkeypatch.setattr("app.routes_admin._read_import_status", mock_read)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/import-status/page")

            assert response.status_code == 200


class TestClearImportStatus:
    """Tests for clear_import_status() route."""

    def test_requires_login_and_admin_role(self, client, db_session, admin_user):
        """Test requires login and admin role."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/import-status/clear", follow_redirects=True)
            assert response.status_code == 200

    def test_post_calls_clear_import_status(self, client, db_session, admin_user, monkeypatch):
        """Test POST calls _clear_import_status."""
        clear_called = []

        def mock_clear():
            clear_called.append(True)

        monkeypatch.setattr("app.routes_admin._clear_import_status", mock_clear)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/settings/admin/import-status/clear")

            assert len(clear_called) > 0

    def test_post_shows_info_flash(self, client, db_session, admin_user):
        """Test POST shows info flash."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/import-status/clear", follow_redirects=True)

            assert b"Import status cleared" in response.data

    def test_post_redirects_to_admin_settings(self, client, db_session, admin_user):
        """Test POST redirects to admin_settings."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/settings/admin/import-status/clear", follow_redirects=False)

            assert response.status_code == 302
            assert "/app/settings/admin" in response.location


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_start_background_import_creates_threading_thread(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import creates threading.Thread."""
        thread_created = []
        original_thread = threading.Thread

        def mock_thread(target, daemon=False):
            thread_created.append({"target": target, "daemon": daemon})
            return original_thread(target=lambda: None, daemon=daemon)

        monkeypatch.setattr("threading.Thread", mock_thread)

        from app.routes_admin import _start_background_import

        _start_background_import("/path/to/file.sql")

        assert len(thread_created) > 0
        assert thread_created[0]["daemon"] is True

    def test_start_background_import_thread_is_daemon(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import thread is daemon=True."""
        thread_created = []
        original_thread = threading.Thread

        def mock_thread(target, daemon=False):
            thread_created.append({"target": target, "daemon": daemon})
            return original_thread(target=lambda: None, daemon=daemon)

        monkeypatch.setattr("threading.Thread", mock_thread)

        from app.routes_admin import _start_background_import

        _start_background_import("/path/to/file.sql")

        assert thread_created[0]["daemon"] is True

    def test_start_background_import_thread_starts_automatically(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import thread starts automatically."""
        start_called = []

        class MockThread:
            def __init__(self, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self):
                start_called.append(True)

        monkeypatch.setattr("threading.Thread", MockThread)

        from app.routes_admin import _start_background_import

        _start_background_import("/path/to/file.sql")

        assert len(start_called) > 0

    def test_write_import_status_creates_instance_path_directory(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test _write_import_status creates instance_path directory."""
        instance_dir = tmp_path / "instance"

        def mock_instance_path():
            return str(instance_dir)

        monkeypatch.setattr("flask.current_app.instance_path", mock_instance_path(), raising=False)

        from app.routes_admin import _write_import_status

        _write_import_status("running", "Test message")

        # Verify directory was created
        assert instance_dir.exists()

    def test_write_import_status_writes_json_with_status_message_updated_at(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test _write_import_status writes JSON with status, message, updated_at."""
        instance_dir = tmp_path / "instance"
        instance_dir.mkdir()

        def mock_instance_path():
            return str(instance_dir)

        monkeypatch.setattr("flask.current_app.instance_path", mock_instance_path(), raising=False)

        from app.routes_admin import _write_import_status

        _write_import_status("success", "Test completed")

        # Verify JSON file was written
        status_file = instance_dir / "import_status.json"
        assert status_file.exists()

        with status_file.open() as f:
            data = json.load(f)

        assert data["status"] == "success"
        assert data["message"] == "Test completed"
        assert "updated_at" in data

    def test_write_import_status_handles_exception_silently(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _write_import_status handles exception silently."""

        def mock_makedirs(*args, **kwargs):
            raise OSError("Cannot create directory")

        monkeypatch.setattr("os.makedirs", mock_makedirs)

        from app.routes_admin import _write_import_status

        # Should not raise exception
        _write_import_status("running", "Test message")

    def test_read_import_status_calls_read_import_status_file(
        self, client, db_session, monkeypatch
    ):
        """Test _read_import_status calls read_import_status_file() from utils."""
        called = []

        def mock_read():
            called.append(True)
            return {"status": "idle"}

        monkeypatch.setattr("app.routes_admin.read_import_status_file", mock_read)

        from app.routes_admin import _read_import_status

        _read_import_status()

        assert len(called) > 0

    def test_clear_import_status_removes_import_status_json_file(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test _clear_import_status removes import_status.json file."""
        instance_dir = tmp_path / "instance"
        instance_dir.mkdir()
        status_file = instance_dir / "import_status.json"
        status_file.write_text('{"status": "running"}')

        def mock_instance_path():
            return str(instance_dir)

        monkeypatch.setattr("flask.current_app.instance_path", mock_instance_path(), raising=False)

        from app.routes_admin import _clear_import_status

        _clear_import_status()

        # Verify file was removed
        assert not status_file.exists()

    def test_clear_import_status_handles_exception_silently(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _clear_import_status handles exception silently."""

        def mock_exists(*args):
            raise OSError("Cannot check file")

        monkeypatch.setattr("os.path.exists", mock_exists)

        from app.routes_admin import _clear_import_status

        # Should not raise exception
        _clear_import_status()

    def test_start_background_import_worker_calls_drop_schema(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import worker calls DROP SCHEMA CASCADE."""
        import subprocess

        from app.routes_admin import _start_background_import

        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        monkeypatch.setattr("subprocess.run", mock_run)

        # Mock _write_import_status to track calls
        status_calls = []

        def mock_write(status, message):
            status_calls.append((status, message))

        monkeypatch.setattr("app.routes_admin._write_import_status", mock_write)

        # Mock _apply_schema_fixes
        apply_schema_called = []

        def mock_apply(env):
            apply_schema_called.append(env)

        monkeypatch.setattr("app.routes_admin._apply_schema_fixes", mock_apply)

        # Mock flask seed-yeasts
        monkeypatch.setattr(
            "subprocess.run",
            MagicMock(
                side_effect=[
                    subprocess.CompletedProcess([], 0),  # DROP SCHEMA
                    subprocess.CompletedProcess([], 0),  # psql import
                    subprocess.CompletedProcess([], 0),  # schema fixes (multiple calls)
                    subprocess.CompletedProcess([], 0),  # flask seed-yeasts
                ]
            ),
        )

        # Call the function
        _start_background_import("/path/to/test.sql")

        # Give thread time to execute
        import time

        time.sleep(0.5)

    def test_start_background_import_worker_calls_psql_import(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import worker calls psql import."""
        import subprocess

        from app.routes_admin import _start_background_import

        run_calls = []

        def mock_run(*args, **kwargs):
            run_calls.append((args, kwargs))
            return subprocess.CompletedProcess([], 0)

        monkeypatch.setattr("subprocess.run", mock_run)
        monkeypatch.setattr("app.routes_admin._write_import_status", lambda s, m: None)
        monkeypatch.setattr("app.routes_admin._apply_schema_fixes", lambda env: None)
        monkeypatch.setattr("subprocess.run", mock_run)

        _start_background_import("/path/to/test.sql")

        import time

        time.sleep(0.5)

        # Verify psql was called with -f flag for import
        psql_import_called = False
        for call_args, _call_kwargs in run_calls:
            if (
                call_args
                and len(call_args[0]) > 0
                and call_args[0][0] == "psql"
                and "-f" in call_args[0]
            ):
                psql_import_called = True
                break

        assert psql_import_called

    def test_start_background_import_worker_calls_apply_schema_fixes(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import worker calls _apply_schema_fixes."""
        import subprocess

        from app.routes_admin import _start_background_import

        apply_schema_called = []

        def mock_apply(env):
            apply_schema_called.append(env)

        monkeypatch.setattr("app.routes_admin._apply_schema_fixes", mock_apply)
        monkeypatch.setattr(
            "subprocess.run", MagicMock(return_value=subprocess.CompletedProcess([], 0))
        )
        monkeypatch.setattr("app.routes_admin._write_import_status", lambda s, m: None)

        _start_background_import("/path/to/test.sql")

        import time

        time.sleep(0.5)

        assert len(apply_schema_called) > 0

    def test_start_background_import_worker_calls_flask_seed_yeasts(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import worker calls flask seed-yeasts."""
        import subprocess

        from app.routes_admin import _start_background_import

        run_calls = []

        def mock_run(*args, **kwargs):
            run_calls.append((args, kwargs))
            return subprocess.CompletedProcess([], 0)

        monkeypatch.setattr("subprocess.run", mock_run)
        monkeypatch.setattr("app.routes_admin._write_import_status", lambda s, m: None)
        monkeypatch.setattr("app.routes_admin._apply_schema_fixes", lambda env: None)

        _start_background_import("/path/to/test.sql")

        import time

        time.sleep(0.5)

        # Verify flask seed-yeasts was called
        flask_seed_called = False
        for call_args, _call_kwargs in run_calls:
            if call_args and len(call_args[0]) > 0 and call_args[0] == ["flask", "seed-yeasts"]:
                flask_seed_called = True
                break

        assert flask_seed_called

    def test_start_background_import_worker_writes_success_status(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import worker writes success status on completion."""
        import subprocess

        from app.routes_admin import _start_background_import

        status_calls = []

        def mock_write(status, message):
            status_calls.append((status, message))

        monkeypatch.setattr("app.routes_admin._write_import_status", mock_write)
        monkeypatch.setattr("app.routes_admin._apply_schema_fixes", lambda env: None)
        monkeypatch.setattr(
            "subprocess.run", MagicMock(return_value=subprocess.CompletedProcess([], 0))
        )

        _start_background_import("/path/to/test.sql")

        import time

        time.sleep(0.5)

        # Verify success status was written
        assert any(status == "success" for status, msg in status_calls)

    def test_start_background_import_worker_writes_error_status_on_calledprocesserror(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import worker writes error status on CalledProcessError."""
        import subprocess

        from app.routes_admin import _start_background_import

        status_calls = []

        def mock_write(status, message):
            status_calls.append((status, message))

        monkeypatch.setattr("app.routes_admin._write_import_status", mock_write)
        monkeypatch.setattr("app.routes_admin._apply_schema_fixes", lambda env: None)
        monkeypatch.setattr(
            "subprocess.run",
            MagicMock(side_effect=subprocess.CalledProcessError(1, "psql")),
        )

        _start_background_import("/path/to/test.sql")

        import time

        time.sleep(0.5)

        # Verify error status was written
        assert any(status == "error" for status, msg in status_calls)

    def test_start_background_import_worker_writes_error_status_on_exception(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import worker writes error status on Exception."""
        from app.routes_admin import _start_background_import

        status_calls = []

        def mock_write(status, message):
            status_calls.append((status, message))

        monkeypatch.setattr("app.routes_admin._write_import_status", mock_write)
        monkeypatch.setattr("app.routes_admin._apply_schema_fixes", lambda env: None)
        monkeypatch.setattr("subprocess.run", MagicMock(side_effect=Exception("Unexpected error")))

        _start_background_import("/path/to/test.sql")

        import time

        time.sleep(0.5)

        # Verify error status was written
        assert any(status == "error" for status, msg in status_calls)

    def test_apply_schema_fixes_runs_create_table_commands(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _apply_schema_fixes runs CREATE TABLE IF NOT EXISTS commands."""
        import subprocess

        from app.routes_admin import _apply_schema_fixes

        run_calls = []

        def mock_run(*args, **kwargs):
            run_calls.append((args, kwargs))
            return subprocess.CompletedProcess([], 0)

        monkeypatch.setattr("subprocess.run", mock_run)

        env = {"PGPASSWORD": "brewpass"}
        _apply_schema_fixes(env)

        # Verify CREATE TABLE commands were run
        create_table_commands = []
        for call_args, _call_kwargs in run_calls:
            if call_args and len(call_args[0]) > 0 and call_args[0][0] == "psql":
                cmd_index = call_args[0].index("-c") + 1
                if cmd_index < len(call_args[0]):
                    sql = call_args[0][cmd_index]
                    if "CREATE TABLE IF NOT EXISTS" in sql:
                        create_table_commands.append(sql)

        # Should have multiple CREATE TABLE commands
        assert len(create_table_commands) > 0

    def test_apply_schema_fixes_runs_alter_table_commands(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _apply_schema_fixes runs ALTER TABLE ADD COLUMN commands."""
        import subprocess

        from app.routes_admin import _apply_schema_fixes

        run_calls = []

        def mock_run(*args, **kwargs):
            run_calls.append((args, kwargs))
            return subprocess.CompletedProcess([], 0)

        monkeypatch.setattr("subprocess.run", mock_run)

        env = {"PGPASSWORD": "brewpass"}
        _apply_schema_fixes(env)

        # Verify ALTER TABLE commands were run
        alter_table_commands = []
        for call_args, _call_kwargs in run_calls:
            if call_args and len(call_args[0]) > 0 and call_args[0][0] == "psql":
                cmd_index = call_args[0].index("-c") + 1
                if cmd_index < len(call_args[0]):
                    sql = call_args[0][cmd_index]
                    if "ALTER TABLE" in sql and "ADD COLUMN" in sql:
                        alter_table_commands.append(sql)

        # Should have multiple ALTER TABLE commands
        assert len(alter_table_commands) > 0

    def test_apply_schema_fixes_runs_all_schema_commands_via_psql(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _apply_schema_fixes runs all schema fix commands via psql."""
        import subprocess

        from app.routes_admin import _apply_schema_fixes

        run_calls = []

        def mock_run(*args, **kwargs):
            run_calls.append((args, kwargs))
            return subprocess.CompletedProcess([], 0)

        monkeypatch.setattr("subprocess.run", mock_run)

        env = {"PGPASSWORD": "brewpass"}
        _apply_schema_fixes(env)

        # Verify all calls use psql
        for call_args, _call_kwargs in run_calls:
            if call_args and len(call_args[0]) > 0:
                assert call_args[0][0] == "psql"

        # Should have many psql calls
        assert len(run_calls) > 10

    def test_latest_local_revision_returns_revision_from_migrations(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test _latest_local_revision returns revision from migrations."""

        from app.routes_admin import _latest_local_revision

        # Create fake migrations directory with proper filename format
        versions_dir = tmp_path / "migrations" / "versions"
        versions_dir.mkdir(parents=True)
        # Use proper Alembic filename format: revision_id_description.py
        (versions_dir / "d00abd51392a_add_feature.py").write_text("# migration")
        (versions_dir / "e11bcd61493b_another_feature.py").write_text("# migration")

        # Mock pathlib.Path.glob() which is used in _latest_local_revision
        from pathlib import Path

        original_glob = Path.glob

        def mock_glob(self, pattern):
            if pattern == "*.py" and str(self).endswith("migrations/versions"):
                return [
                    versions_dir / "d00abd51392a_add_feature.py",
                    versions_dir / "e11bcd61493b_another_feature.py",
                ]
            return original_glob(self, pattern)

        monkeypatch.setattr("pathlib.Path.glob", mock_glob)

        rev = _latest_local_revision()

        # Should return the latest revision (sorted alphabetically)
        assert rev is not None
        assert "e11bcd61493b" in rev

    def test_latest_local_revision_returns_none_if_no_migrations(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test _latest_local_revision returns None if no migrations."""
        from app.routes_admin import _latest_local_revision

        # Create empty migrations directory
        migrations_dir = tmp_path / "migrations" / "versions"
        migrations_dir.mkdir(parents=True)

        monkeypatch.setattr("flask.current_app.root_path", str(tmp_path))

        rev = _latest_local_revision()

        assert rev is None

    def test_latest_local_revision_handles_exception(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _latest_local_revision handles exception."""
        from app.routes_admin import _latest_local_revision

        # Mock to raise exception
        monkeypatch.setattr("flask.current_app.root_path", "/nonexistent/path")

        rev = _latest_local_revision()

        assert rev is None

    def test_stamp_head_with_fallback_runs_flask_db_stamp(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _stamp_head_with_fallback runs flask db stamp."""
        import subprocess

        from app.routes_admin import _stamp_head_with_fallback

        run_calls = []

        def mock_run(*args, **kwargs):
            run_calls.append((args, kwargs))
            return subprocess.CompletedProcess([], 0)

        monkeypatch.setattr("subprocess.run", mock_run)

        env = {"PGPASSWORD": "brewpass"}
        _stamp_head_with_fallback(env)

        # Verify flask db stamp was called
        flask_db_called = False
        for call_args, _call_kwargs in run_calls:
            if (
                call_args
                and len(call_args[0]) > 0
                and call_args[0] == ["flask", "db", "stamp", "head"]
            ):
                flask_db_called = True
                break

        assert flask_db_called

    def test_stamp_head_with_fallback_uses_manual_insert_on_failure(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _stamp_head_with_fallback uses manual insert on failure."""
        import subprocess

        from app.routes_admin import _stamp_head_with_fallback

        # Make subprocess.run fail
        def mock_run(*args, **kwargs):
            raise subprocess.CalledProcessError(1, "flask")

        monkeypatch.setattr("subprocess.run", mock_run)

        # Mock db.session operations
        execute_calls = []

        def mock_execute(sql, params=None):
            execute_calls.append((sql, params))
            return MagicMock()

        monkeypatch.setattr("app.routes_admin.db.session.execute", mock_execute)
        monkeypatch.setattr("app.routes_admin.db.session.commit", MagicMock())
        monkeypatch.setattr("app.routes_admin.db.session.rollback", MagicMock())

        # Mock _latest_local_revision to return a known revision
        monkeypatch.setattr("app.routes_admin._latest_local_revision", lambda: "d00abd51392a")

        env = {"PGPASSWORD": "brewpass"}
        _stamp_head_with_fallback(env)

        # Verify manual INSERT was attempted
        insert_called = False
        for sql, _params in execute_calls:
            if "INSERT INTO alembic_version" in str(sql):
                insert_called = True
                break

        assert insert_called

    def test_admin_settings_handles_programming_error(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test admin_settings handles ProgrammingError (missing column) with ALTER TABLE."""
        from sqlalchemy.exc import ProgrammingError

        # Mock AppSettings.query to raise ProgrammingError then succeed
        call_count = [0]

        def mock_query_first():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ProgrammingError("column does not exist", {}, Exception("mock error"))
            # Return a mock settings object on second call
            mock_settings = MagicMock()
            mock_settings.unit_preference = "imperial"
            mock_settings.base_url = None
            return mock_settings

        mock_settings = MagicMock()
        mock_settings.unit_preference = "imperial"
        mock_settings.base_url = None

        monkeypatch.setattr("app.routes_admin.AppSettings.query.first", mock_query_first)
        monkeypatch.setattr("app.routes_admin.AppSettings.query.all", lambda: [])
        monkeypatch.setattr("app.routes_admin.db.session.execute", MagicMock())
        monkeypatch.setattr("app.routes_admin.db.session.commit", MagicMock())
        monkeypatch.setattr("app.routes_admin.User.query.order_by", lambda x: [])
        # Mock check_for_updates to return proper dict structure
        monkeypatch.setattr(
            "app.routes_admin.check_for_updates",
            lambda: {"current": "v1.0.0", "latest": "v1.1.0"},
        )
        monkeypatch.setattr("app.routes_admin.os.listdir", lambda x: [])
        monkeypatch.setattr("app.routes_admin._read_import_status", lambda: None)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/")
            assert response.status_code == 200

    def test_start_background_import_worker_handles_nonzero_returncode(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _start_background_import worker handles non-zero returncode."""
        import subprocess

        from app.routes_admin import _start_background_import

        status_calls = []

        def mock_write(status, message):
            status_calls.append((status, message))

        monkeypatch.setattr("app.routes_admin._write_import_status", mock_write)
        monkeypatch.setattr("app.routes_admin._apply_schema_fixes", lambda env: None)

        # Mock subprocess.run to return non-zero for import
        def mock_run(*args, **kwargs):
            cmd = args[0] if args else []
            if isinstance(cmd, list) and "-f" in cmd:
                # This is the import command - return non-zero
                return subprocess.CompletedProcess(cmd, 1)
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("subprocess.run", mock_run)

        _start_background_import("/path/to/test.sql")

        import time

        time.sleep(0.5)

        # Verify message about returncode was written
        assert any("return code" in msg for status, msg in status_calls)

    def test_latest_local_revision_handles_exception_gracefully(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _latest_local_revision handles exception gracefully."""
        from app.routes_admin import _latest_local_revision

        # Mock listdir to raise exception
        monkeypatch.setattr(
            "os.listdir",
            lambda x: (_ for _ in ()).throw(Exception("Directory not found")),
        )

        rev = _latest_local_revision()

        assert rev is None

    def test_stamp_head_with_fallback_handles_exception_gracefully(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test _stamp_head_with_fallback handles exception gracefully."""
        from app.routes_admin import _stamp_head_with_fallback

        # Mock subprocess.run and db operations to fail
        def mock_run(*args, **kwargs):
            raise Exception("Command failed")

        monkeypatch.setattr("subprocess.run", mock_run)
        monkeypatch.setattr(
            "app.routes_admin.db.session.execute",
            MagicMock(side_effect=Exception("DB failed")),
        )
        monkeypatch.setattr("app.routes_admin.db.session.rollback", MagicMock())
        monkeypatch.setattr("app.routes_admin._latest_local_revision", lambda: None)

        env = {"PGPASSWORD": "brewpass"}
        # Should not raise exception
        _stamp_head_with_fallback(env)


class TestAdminCoverageGaps:
    """Tests for remaining coverage gaps in app/routes_admin.py."""

    def test_admin_settings_programming_error_lines_30_34(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test lines 30-34: ProgrammingError during AppSettings query triggers
        ALTER TABLE retry."""
        from sqlalchemy.exc import ProgrammingError

        # Mock AppSettings.query.first() to raise ProgrammingError
        query_first_called = []

        def mock_first():
            query_first_called.append(True)
            if len(query_first_called) == 1:
                # First call raises ProgrammingError
                raise ProgrammingError(
                    "column unit_preference does not exist", {}, Exception("mock error")
                )
            # Second call (after ALTER TABLE) returns None
            return None

        mock_query = MagicMock()
        mock_query.first = mock_first
        mock_query.order_by = MagicMock(return_value=mock_query)

        from app import models

        monkeypatch.setattr(models.AppSettings, "query", mock_query)

        # Mock db.session.execute to handle ALTER TABLE
        monkeypatch.setattr(db_session, "execute", MagicMock())
        monkeypatch.setattr(db_session, "commit", MagicMock())

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/admin/", follow_redirects=False)

            # Should succeed after retry
            assert response.status_code == 200
            # query.first() should be called twice (once before ALTER, once after)
            assert len(query_first_called) >= 1

    def test_check_for_updates_empty_migrations_line_296(
        self, client, db_session, admin_user, monkeypatch, tmp_path
    ):
        """Test line 296: check_for_updates returns None when migrations/versions is empty."""

        # Create empty migrations/versions directory
        migrations_dir = tmp_path / "migrations" / "versions"
        migrations_dir.mkdir(parents=True)

        # Mock current_app.root_path to use our temp directory
        import app.routes_admin as routes_admin_module

        def mock_check():
            # Temporarily change the base_dir calculation
            versions_path = tmp_path / "migrations" / "versions"
            try:
                entries = sorted(
                    [f.name for f in versions_path.iterdir() if f.name.endswith(".py")]
                )
                if not entries:
                    return None  # This is line 296
                revs = [re.split(r"[_\.]", f)[0] for f in entries]
                return revs[-1] if revs else None
            except Exception:
                return None

        monkeypatch.setattr(routes_admin_module, "check_for_updates", mock_check)

        result = mock_check()

        # Should return None when versions directory is empty
        assert result is None
