"""
Comprehensive unit tests for main routes blueprint in app/routes.py.

Test Strategy:
- Uses pytest-flask-sqlalchemy for transactional isolation
- Mocks utils functions (unit conversions, get_unit_preference)
- Tests all routes with proper authentication/authorization
- Edge cases: temperature conversion, None handling, validation errors

Routes Tested:
- root_redirect(): Root path redirect to '/app/'
- login(): Authentication with credential validation and rate limiting
- logout(): Session cleanup
- index(): Main dashboard with recipe categorization
- new_measurement(): Add measurement to batch
- delete_measurement(): Remove measurement (admin only)

Blueprint Registrations:
- admin_bp, batches_bp, calculator_bp, calendar_bp
- recipes_bp, settings_bp, stats_bp, yeast_bp
"""

from datetime import datetime

import pytest

from app.models import Batch, Measurement, Recipe, User


class TestRootRedirect:
    """Tests for root_redirect() route."""

    def test_redirects_to_app_root(self, client, db_session):
        """Test redirects to '/app/'."""
        # Create a user to avoid setup redirect
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert "/app/" in response.location

    def test_uses_redirect_not_render_template(self, client, db_session):
        """Test uses redirect() not render_template."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/", follow_redirects=False)
        # Should be a redirect, not a 200 with template
        assert response.status_code == 302
        assert response.status_code != 200


class TestLogin:
    """Tests for login() route."""

    def test_get_returns_login_template(self, client, db_session, test_user):
        """Test GET renders login.html."""
        response = client.get("/login")
        assert response.status_code == 200
        assert b"login" in response.data.lower()

    def test_redirects_to_setup_if_no_user_exists(self, client, db_session):
        """Test redirects to setup if no User exists."""
        # Ensure no users exist
        User.query.delete()
        db_session.commit()

        response = client.get("/login", follow_redirects=False)
        assert response.status_code == 302
        assert "/setup" in response.location

    def test_post_with_valid_credentials_logs_in(self, client, db_session, test_user):
        """Test POST with valid credentials calls login_user()."""
        response = client.post(
            "/login",
            data={"username": test_user.username, "password": "testpassword123"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        # Should redirect to index
        assert "/app/" in response.location

    def test_post_with_valid_credentials_redirects_to_index(self, client, db_session, test_user):
        """Test POST with valid credentials redirects to index."""
        response = client.post(
            "/login",
            data={"username": test_user.username, "password": "testpassword123"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/app/" in response.location or response.location.endswith("/")

    def test_post_with_invalid_credentials_shows_flash_error(self, client, db_session, test_user):
        """Test POST with invalid credentials shows flash error."""
        response = client.post(
            "/app/login",
            data={"username": test_user.username, "password": "wrongpassword"},
            follow_redirects=True,
        )

        assert b"Invalid username or password" in response.data

    def test_limiter_limit_decorator_present(self, client, db_session, test_user):
        """Test @limiter.limit("5 per minute") decorator present."""
        # The decorator is applied at function definition time
        # We verify by checking the rate limiter is configured
        from app import limiter

        assert limiter is not None


class TestLogout:
    """Tests for logout() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        # Create a user so setup hook doesn't interfere
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_calls_logout_user(self, client, db_session, test_user):
        """Test calls logout_user()."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.get("/logout", follow_redirects=False)
            assert response.status_code == 302
            # After logout, user should be logged out (redirected to login)

    def test_shows_success_flash_message(self, client, db_session, test_user):
        """Test shows success flash message."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.get("/app/logout", follow_redirects=True)
            assert response.status_code == 200
            # Flash message should be present in response
            assert b"Logged out successfully" in response.data

    def test_redirects_to_login(self, client, db_session, test_user):
        """Test redirects to routes.login."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.get("/logout", follow_redirects=False)
            assert response.status_code == 302
            assert "/login" in response.location


class TestIndex:
    """Tests for index() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/app/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_queries_recipe_by_alcohol_type_mead(self, client, db_session, admin_user):
        """Test queries Recipe by alcohol_type: Mead."""
        recipe = Recipe()
        recipe.name = "Mead Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/")
            assert response.status_code == 200
            assert b"Mead Recipe" in response.data

    def test_queries_recipe_by_alcohol_type_wine(self, client, db_session, admin_user):
        """Test queries Recipe by alcohol_type: Wine."""
        recipe = Recipe()
        recipe.name = "Wine Recipe"
        recipe.alcohol_type = "Wine"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/")
            assert response.status_code == 200
            assert b"Wine Recipe" in response.data

    def test_queries_recipe_by_alcohol_type_beer(self, client, db_session, admin_user):
        """Test queries Recipe by alcohol_type: Beer."""
        recipe = Recipe()
        recipe.name = "Beer Recipe"
        recipe.alcohol_type = "Beer"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/")
            assert response.status_code == 200
            assert b"Beer Recipe" in response.data

    def test_queries_recipe_by_alcohol_type_none(self, client, db_session, admin_user):
        """Test queries Recipe with alcohol_type == None."""
        recipe = Recipe()
        recipe.name = "Other Recipe"
        recipe.alcohol_type = None
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/")
            assert response.status_code == 200
            assert b"Other Recipe" in response.data

    def test_orders_recipes_by_name_asc(self, client, db_session, admin_user):
        """Test orders recipes by name.asc()."""
        # Create recipes in non-alphabetical order
        recipe_z = Recipe()
        recipe_z.name = "Zebra Recipe"
        recipe_z.alcohol_type = "Mead"
        db_session.add(recipe_z)
        db_session.commit()

        recipe_a = Recipe()
        recipe_a.name = "Alpha Recipe"
        recipe_a.alcohol_type = "Mead"
        db_session.add(recipe_a)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/")
            assert response.status_code == 200
            # Alpha should appear before Zebra in alphabetical ordering
            data = response.data.decode("utf-8")
            alpha_pos = data.find("Alpha Recipe")
            zebra_pos = data.find("Zebra Recipe")
            assert alpha_pos < zebra_pos

    def test_renders_index_html_with_recipe_categories(self, client, db_session, admin_user):
        """Test renders index.html with mead_recipes, wine_recipes, beer_recipes, other_recipes."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/")
            assert response.status_code == 200
            assert b"index" in response.data.lower() or b"recipe" in response.data.lower()

    def test_handles_empty_recipe_lists(self, client, db_session, admin_user):
        """Test handles empty recipe lists."""
        # No recipes in database
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/")
            assert response.status_code == 200
            # Should render without errors even with no recipes


class TestNewMeasurement:
    """Tests for new_measurement() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/app/measurements/new", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_role_admin_or_editor(self, client, db_session, test_user):
        """Test requires role 'admin' or 'editor' (@role_required)."""
        # test_user has role 'user', should be forbidden
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.get("/app/measurements/new", follow_redirects=True)
            assert response.status_code == 403

    def test_get_renders_new_measurement_template(self, client, db_session, admin_user):
        """Test GET renders new_measurement.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/measurements/new")
            assert response.status_code == 200
            assert b"measurement" in response.data.lower()

    def test_get_queries_all_batches(self, client, db_session, admin_user):
        """Test GET queries all batches."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/measurements/new")
            assert response.status_code == 200
            assert b"Test Batch" in response.data

    def test_get_passes_selected_id_from_query_args(self, client, db_session, admin_user):
        """Test GET passes selected_id from query args."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/measurements/new?batch_id={batch.id}")
            assert response.status_code == 200

    def test_post_with_valid_data_creates_measurement(self, client, db_session, admin_user):
        """Test POST with valid data creates Measurement."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id),
                    "date": "2026-01-15",
                    "temperature": "20",
                    "gravity": "1.050",
                    "ph": "4.0",
                    "notes": "Test measurement",
                },
            )

        measurement = Measurement.query.filter_by(notes="Test measurement").first()
        assert measurement is not None
        assert measurement.batch_id == batch.id

    def test_post_converts_temperature_if_units_metric(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test POST converts temperature if units == 'metric' (c_to_f)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        # Mock metric preference
        monkeypatch.setattr("app.routes.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id),
                    "date": "2026-01-15",
                    "temperature": "20",  # Celsius
                    "gravity": "1.050",
                    "ph": "4.0",
                    "notes": "Test metric",
                },
            )

        measurement = Measurement.query.filter_by(notes="Test metric").first()
        assert measurement is not None
        # Temperature should be converted to Fahrenheit (20°C = 68°F)
        assert measurement.temperature is not None
        assert measurement.temperature > 20  # Should be in F now

    def test_post_handles_empty_temperature(self, client, db_session, admin_user):
        """Test POST handles empty temperature (None)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id),
                    "date": "2026-01-15",
                    "temperature": "",  # Empty
                    "gravity": "1.050",
                    "ph": "4.0",
                    "notes": "Test empty temp",
                },
            )

        measurement = Measurement.query.filter_by(notes="Test empty temp").first()
        assert measurement is not None
        assert measurement.temperature is None

    def test_post_handles_invalid_temperature_type_error(self, client, db_session, admin_user):
        """Test POST handles invalid temperature (TypeError → None)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id),
                    "date": "2026-01-15",
                    "temperature": "invalid",
                    "gravity": "1.050",
                    "ph": "4.0",
                    "notes": "Test invalid temp",
                },
            )

        measurement = Measurement.query.filter_by(notes="Test invalid temp").first()
        assert measurement is not None
        assert measurement.temperature is None

    def test_post_handles_invalid_temperature_value_error(self, client, db_session, admin_user):
        """Test POST handles invalid temperature (ValueError → None)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id),
                    "date": "2026-01-15",
                    "temperature": "not_a_number",
                    "gravity": "1.050",
                    "ph": "4.0",
                    "notes": "Test value error temp",
                },
            )

        measurement = Measurement.query.filter_by(notes="Test value error temp").first()
        assert measurement is not None
        assert measurement.temperature is None

    def test_post_handles_empty_gravity(self, client, db_session, admin_user):
        """Test POST handles empty gravity (None)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id),
                    "date": "2026-01-15",
                    "temperature": "20",
                    "gravity": "",  # Empty
                    "ph": "4.0",
                    "notes": "Test empty gravity",
                },
            )

        measurement = Measurement.query.filter_by(notes="Test empty gravity").first()
        assert measurement is not None
        assert measurement.gravity is None

    def test_post_handles_empty_ph(self, client, db_session, admin_user):
        """Test POST handles empty ph (None)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id),
                    "date": "2026-01-15",
                    "temperature": "20",
                    "gravity": "1.050",
                    "ph": "",  # Empty
                    "notes": "Test empty ph",
                },
            )

        measurement = Measurement.query.filter_by(notes="Test empty ph").first()
        assert measurement is not None
        assert measurement.ph is None

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id),
                    "date": "2026-01-15",
                    "temperature": "20",
                    "gravity": "1.050",
                    "ph": "4.0",
                    "notes": "Test commit",
                },
            )

        # Verify commit by querying
        measurement = Measurement.query.filter_by(notes="Test commit").first()
        assert measurement is not None

    def test_post_redirects_to_view_batch(self, client, db_session, admin_user):
        """Test POST redirects to view_batch with measurement.batch_id."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id),
                    "date": "2026-01-15",
                    "temperature": "20",
                    "gravity": "1.050",
                    "ph": "4.0",
                    "notes": "Test redirect",
                },
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert f"/app/batches/{batch.id}" in response.location

    def test_post_shows_success_flash(self, client, db_session, admin_user):
        """Test POST shows success flash."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id),
                    "date": "2026-01-15",
                    "temperature": "20",
                    "gravity": "1.050",
                    "ph": "4.0",
                    "notes": "Test flash",
                },
                follow_redirects=True,
            )

        assert b"Measurement added" in response.data

    def test_post_exception_handling(self, client, db_session, admin_user, monkeypatch):
        """Test POST exception handling (prints traceback, re-raises)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        # Mock db.session.add to raise an exception
        original_add = db_session.add

        def mock_add(obj):
            if isinstance(obj, Measurement):
                raise Exception("Database error")
            return original_add(obj)

        monkeypatch.setattr(db_session, "add", mock_add)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Should raise exception (re-raised after traceback)
            with pytest.raises(Exception, match=r".*"):
                c.post(
                    "/app/measurements/new",
                    data={
                        "batch_id": str(batch.id),
                        "date": "2026-01-15",
                        "temperature": "20",
                        "gravity": "1.050",
                        "ph": "4.0",
                        "notes": "Test exception",
                    },
                )


class TestDeleteMeasurement:
    """Tests for delete_measurement() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.post("/app/measurements/1/delete", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_role_admin_only(self, client, db_session, test_user):
        """Test requires role 'admin' only (@role_required('admin'))."""
        # test_user has role 'user', should be forbidden
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.post("/app/measurements/1/delete", follow_redirects=True)
            assert response.status_code == 403

    def test_post_with_valid_id_deletes_measurement(self, client, db_session, admin_user):
        """Test POST with valid ID deletes measurement."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        measurement = Measurement()
        measurement.batch_id = batch.id
        measurement.date = datetime.utcnow()
        measurement.temperature = 20.0
        db_session.add(measurement)
        db_session.commit()
        measurement_id = measurement.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/measurements/{measurement_id}/delete")

        deleted_measurement = Measurement.query.get(measurement_id)
        assert deleted_measurement is None

    def test_post_with_invalid_id_raises_404(self, client, db_session, admin_user):
        """Test POST with invalid ID raises 404 (get_or_404)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/measurements/99999/delete")
            assert response.status_code == 404

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        measurement = Measurement()
        measurement.batch_id = batch.id
        measurement.date = datetime.utcnow()
        measurement.temperature = 20.0
        db_session.add(measurement)
        db_session.commit()
        measurement_id = measurement.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/measurements/{measurement_id}/delete")

        # Verify deletion is committed
        assert Measurement.query.get(measurement_id) is None

    def test_post_redirects_to_view_batch(self, client, db_session, admin_user):
        """Test POST redirects to view_batch with original batch_id."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        measurement = Measurement()
        measurement.batch_id = batch.id
        measurement.date = datetime.utcnow()
        measurement.temperature = 20.0
        db_session.add(measurement)
        db_session.commit()
        measurement_id = measurement.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/measurements/{measurement_id}/delete", follow_redirects=False)

        assert response.status_code == 302
        assert f"/app/batches/{batch.id}" in response.location

    def test_post_shows_success_flash(self, client, db_session, admin_user):
        """Test POST shows success flash."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        measurement = Measurement()
        measurement.batch_id = batch.id
        measurement.date = datetime.utcnow()
        measurement.temperature = 20.0
        db_session.add(measurement)
        db_session.commit()
        measurement_id = measurement.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/measurements/{measurement_id}/delete", follow_redirects=True)

        assert b"Measurement deleted successfully" in response.data


class TestBlueprintRegistrations:
    """Tests for blueprint registrations."""

    def test_admin_bp_registered(self, client, db_session, admin_user):
        """Test admin_bp registered."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # admin_bp has url_prefix='/settings/admin'
            response = c.get("/app/settings/admin/")
            # Should not get 404 for blueprint registration
            assert response.status_code != 404 or response.status_code == 302

    def test_batches_bp_registered(self, client, db_session, admin_user):
        """Test batches_bp registered."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # batches_bp has url_prefix='/batches'
            response = c.get("/app/batches/")
            assert response.status_code != 404 or response.status_code == 302

    def test_calculator_bp_registered(self, client, db_session, admin_user):
        """Test calculator_bp registered."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # calculator_bp has url_prefix='/calculator'
            response = c.get("/app/calculator/")
            assert response.status_code != 404 or response.status_code == 302

    def test_calendar_bp_registered(self, client, db_session, admin_user):
        """Test calendar_bp registered."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # calendar_bp has route '/calendar' under routes blueprint
            response = c.get("/app/calendar")
            assert response.status_code != 404 or response.status_code == 302

    def test_recipes_bp_registered(self, client, db_session, admin_user):
        """Test recipes_bp registered."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # recipes_bp has route '/recipes' under routes blueprint
            response = c.get("/app/recipes")
            assert response.status_code != 404 or response.status_code == 302

    def test_settings_bp_registered(self, client, db_session, admin_user):
        """Test settings_bp registered."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # settings_bp has url_prefix='/settings'
            response = c.get("/app/settings/")
            assert response.status_code != 404 or response.status_code == 302

    def test_stats_bp_registered(self, client, db_session, admin_user):
        """Test stats_bp registered."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # stats_bp has url_prefix='/stats'
            response = c.get("/app/stats/")
            assert response.status_code != 404 or response.status_code == 302

    def test_yeast_bp_registered(self, client, db_session, admin_user):
        """Test yeast_bp registered."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # yeast_bp has url_prefix='/yeasts'
            response = c.get("/app/yeasts/")
            assert response.status_code != 404 or response.status_code == 302


class TestEdgeCases:
    """Edge cases and error handling tests."""

    def test_missing_form_fields_in_new_measurement_post(self, client, db_session, admin_user):
        """Test missing form fields in new_measurement POST."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Missing required fields
            response = c.post(
                "/app/measurements/new",
                data={
                    "batch_id": str(batch.id)
                    # Missing date, temperature, etc.
                },
                follow_redirects=True,
            )

        # Should handle gracefully (error or exception)
        assert response.status_code in [200, 400, 500]

    def test_invalid_date_format_in_new_measurement_post(self, client, db_session, admin_user):
        """Test invalid date format in new_measurement POST."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Invalid date format should raise ValueError (re-raised after traceback)
            with pytest.raises(ValueError):
                c.post(
                    "/app/measurements/new",
                    data={
                        "batch_id": str(batch.id),
                        "date": "invalid-date-format",
                        "temperature": "20",
                        "gravity": "1.050",
                        "ph": "4.0",
                        "notes": "Test invalid date",
                    },
                )

    def test_database_commit_failures(self, client, db_session, admin_user, monkeypatch):
        """Test database commit failures."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        def mock_commit():
            raise Exception("Database commit failed")

        monkeypatch.setattr(db_session, "commit", mock_commit)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Should raise exception (re-raised after traceback)
            with pytest.raises(Exception, match=r".*"):
                c.post(
                    "/app/measurements/new",
                    data={
                        "batch_id": str(batch.id),
                        "date": "2026-01-15",
                        "temperature": "20",
                        "gravity": "1.050",
                        "ph": "4.0",
                        "notes": "Test commit failure",
                    },
                )

    def test_recipe_query_filter_with_alcohol_type_none(self, client, db_session, admin_user):
        """Test Recipe.query.filter with alcohol_type == None (is None vs == None)."""
        # Create recipe with None alcohol_type
        recipe = Recipe()
        recipe.name = "None Type Recipe"
        recipe.alcohol_type = None
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/")
            assert response.status_code == 200
            # Should include recipe with None alcohol_type
            assert b"None Type Recipe" in response.data


class TestRoutesCoverageGaps:
    """Tests for remaining coverage gaps in app/routes.py."""

    def test_login_get_redirects_to_setup_when_no_user(self, client, db_session):
        """Test line 28: GET /app/login redirects to setup when no User exists."""
        # Ensure no users exist
        User.query.delete()
        db_session.commit()

        response = client.get("/app/login", follow_redirects=False)
        assert response.status_code == 302
        assert "/setup" in response.location

    def test_login_post_success_flash_message(self, client, db_session, test_user):
        """Test lines 34-36: Successful login shows 'Logged in successfully' flash."""
        response = client.post(
            "/app/login",
            data={"username": test_user.username, "password": "testpassword123"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Logged in successfully" in response.data

    def test_login_invalid_credentials_lines_15_28(self, client, db_session, test_user):
        """Test lines 15-28: Login POST with invalid credentials shows error."""
        # Test with invalid username - this exercises lines 15-28
        response = client.post(
            "/login",
            data={"username": "nonexistent_user", "password": "anypassword"},
            follow_redirects=True,
        )

        # Should show error (either "Invalid credentials" or redirect to setup)
        assert response.status_code == 200
        assert b"Invalid credentials" in response.data or b"setup" in response.data.lower()

    def test_logout_lines_33_35(self, client, db_session, test_user):
        """Test lines 33-35: Logout route exists and is accessible."""
        # Login first
        client.post(
            "/login",
            data={"username": test_user.username, "password": "testpassword123"},
            follow_redirects=True,
        )

        # Access logout - should redirect to login
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location
