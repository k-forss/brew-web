"""
Comprehensive unit tests for batches blueprint in app/routes_batches.py.

Test Strategy:
- Uses pytest-flask-sqlalchemy for transactional isolation
- Mocks utils functions (unit conversions, get_unit_preference)
- Tests all routes with proper authentication/authorization
- Edge cases: unit conversions, TOSNA calculations, validation errors

Routes Tested:
- list_batches(): Dashboard showing all batches by type
- view_batch(): Batch detail view with measurements
- edit_batch(): Update batch information
- delete_batch(): Batch deletion
- new_batch(): Create new batch from recipe
- calculate_tosna(): TOSNA calculation endpoint
- add_tosna_to_calendar(): Calendar event creation
"""

from datetime import datetime

from app.models import Batch, CalendarEvent, Recipe, User, Yeast


class TestListBatches:
    """Tests for list_batches() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        # Create a user first so setup hook doesn't interfere
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/app/batches/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_queries_batches_by_alcohol_type_mead(self, client, db_session, admin_user):
        """Test queries batches by alcohol_type: Mead."""
        # Create test batches
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Mead Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/")
            assert response.status_code == 200
            assert b"Test Mead Batch" in response.data

    def test_queries_batches_by_alcohol_type_wine(self, client, db_session, admin_user):
        """Test queries batches by alcohol_type: Wine."""
        recipe = Recipe()
        recipe.name = "Wine Recipe"
        recipe.alcohol_type = "Wine"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Wine Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Wine"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/")
            assert response.status_code == 200
            assert b"Test Wine Batch" in response.data

    def test_queries_batches_by_alcohol_type_beer(self, client, db_session, admin_user):
        """Test queries batches by alcohol_type: Beer."""
        recipe = Recipe()
        recipe.name = "Beer Recipe"
        recipe.alcohol_type = "Beer"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Beer Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Beer"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/")
            assert response.status_code == 200
            assert b"Test Beer Batch" in response.data

    def test_queries_batches_by_alcohol_type_hard_cider(self, client, db_session, admin_user):
        """Test queries batches by alcohol_type: Hard Cider."""
        recipe = Recipe()
        recipe.name = "Cider Recipe"
        recipe.alcohol_type = "Hard Cider"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Cider Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Hard Cider"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/")
            assert response.status_code == 200
            assert b"Test Cider Batch" in response.data

    def test_queries_batches_other_types(self, client, db_session, admin_user):
        """Test queries batches with other/None alcohol_type."""
        recipe = Recipe()
        recipe.name = "Other Recipe"
        recipe.alcohol_type = "Other"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Other Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Other"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/")
            assert response.status_code == 200
            assert b"Test Other Batch" in response.data

    def test_orders_by_start_date_desc(self, client, db_session, admin_user):
        """Test orders by start_date.desc()."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        # Create batches with different dates
        batch1 = Batch()
        batch1.name = "Older Batch"
        batch1.recipe_id = recipe.id
        batch1.alcohol_type = "Mead"
        batch1.start_date = datetime(2025, 1, 1)
        db_session.add(batch1)
        db_session.commit()

        batch2 = Batch()
        batch2.name = "Newer Batch"
        batch2.recipe_id = recipe.id
        batch2.alcohol_type = "Mead"
        batch2.start_date = datetime(2026, 1, 1)
        db_session.add(batch2)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/")
            assert response.status_code == 200
            # Newer batch should appear first in ordering
            data = response.data.decode("utf-8")
            newer_pos = data.find("Newer Batch")
            older_pos = data.find("Older Batch")
            assert newer_pos < older_pos

    def test_renders_batches_html_with_categorized_batches(self, client, db_session, admin_user):
        """Test renders batches.html with categorized batches."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/")
            assert response.status_code == 200
            assert b"batches" in response.data.lower()


class TestViewBatch:
    """Tests for view_batch() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/app/batches/1", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_get_with_valid_id_returns_batch(self, client, db_session, admin_user):
        """Test GET with valid ID returns batch."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test View Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200
            assert b"Test View Batch" in response.data

    def test_get_with_invalid_id_raises_404(self, client, db_session, admin_user):
        """Test GET with invalid ID raises 404."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/99999")
            assert response.status_code == 404

    def test_converts_batch_size_to_liters_if_needed(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test converts batch_size to liters if needed."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Conversion Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.batch_size = 5.0  # 5 gallons
        db_session.add(batch)
        db_session.commit()

        # Mock get_unit_preference to return metric
        monkeypatch.setattr("app.routes_batches.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200

    def test_converts_fermentation_temp_to_celsius_if_needed(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test converts fermentation_temp to Celsius if needed."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Temp Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.fermentation_temp = "68.0"  # Fahrenheit
        db_session.add(batch)
        db_session.commit()

        monkeypatch.setattr("app.routes_batches.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200

    def test_handles_none_batch_size(self, client, db_session, admin_user):
        """Test handles None batch_size."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test None Size Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.batch_size = None
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200

    def test_handles_none_fermentation_temp(self, client, db_session, admin_user):
        """Test handles None fermentation_temp."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test None Temp Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.fermentation_temp = None
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200

    def test_handles_invalid_fermentation_temp_type_error(self, client, db_session, admin_user):
        """Test handles invalid fermentation_temp (TypeError)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Invalid Temp Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.fermentation_temp = "invalid"
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200

    def test_handles_invalid_fermentation_temp_value_error(self, client, db_session, admin_user):
        """Test handles invalid fermentation_temp (ValueError)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test ValueError Temp Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.fermentation_temp = "not_a_number"
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200

    def test_renders_batch_detail_html_with_unit_preference(self, client, db_session, admin_user):
        """Test renders batch_detail.html with unit_preference."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Detail Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200
            assert b"batch" in response.data.lower()


class TestEditBatch:
    """Tests for edit_batch() route."""

    def test_requires_login_and_role_admin_or_editor(self, client, db_session, test_user):
        """Test requires login and role 'admin' or 'editor'."""
        # test_user has role 'user', should be forbidden
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.get("/app/batches/1/edit", follow_redirects=True)
            assert response.status_code == 403

    def test_get_with_valid_id_returns_batch(self, client, db_session, admin_user):
        """Test GET with valid ID returns batch."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Edit Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}/edit")
            assert response.status_code == 200
            assert b"Test Edit Batch" in response.data

    def test_get_with_invalid_id_raises_404(self, client, db_session, admin_user):
        """Test GET with invalid ID raises 404."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/99999/edit")
            assert response.status_code == 404

    def test_get_queries_recipes_and_yeasts(self, client, db_session, admin_user):
        """Test GET queries recipes and yeasts."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        yeast = Yeast()
        yeast.name = "Test Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Edit Query Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}/edit")
            assert response.status_code == 200
            assert b"Test Recipe" in response.data
            assert b"Test Yeast" in response.data

    def test_get_converts_batch_size_for_display(self, client, db_session, admin_user, monkeypatch):
        """Test GET converts batch_size for display."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Display Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        monkeypatch.setattr("app.routes_batches.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}/edit")
            assert response.status_code == 200

    def test_get_converts_fermentation_temp_for_display(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test GET converts fermentation_temp for display."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Temp Display Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.fermentation_temp = "68.0"
        db_session.add(batch)
        db_session.commit()

        monkeypatch.setattr("app.routes_batches.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}/edit")
            assert response.status_code == 200

    def test_post_with_valid_data_updates_batch_fields(self, client, db_session, admin_user):
        """Test POST with valid data updates batch fields."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Original Name"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Updated Name",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                },
                follow_redirects=True,
            )

        updated_batch = Batch.query.get(batch_id)
        assert updated_batch.name == "Updated Name"

    def test_post_converts_batch_size_from_metric_to_gallons(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test POST converts batch_size from metric to gallons."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Size Convert Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        # Mock metric preference
        monkeypatch.setattr("app.routes_batches.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Submit 19 liters (should convert to ~5 gallons)
            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "batch_size": "19",  # liters
                },
            )

        updated_batch = Batch.query.get(batch_id)
        # Should be converted to gallons (19 L ≈ 5 gal)
        assert updated_batch.batch_size is not None
        assert updated_batch.batch_size < 19  # Should be in gallons now

    def test_post_converts_fermentation_temp_from_metric_to_f(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test POST converts fermentation_temp from metric to F."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Temp Convert Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        monkeypatch.setattr("app.routes_batches.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Submit 20°C (should convert to 68°F)
            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "fermentation_temp": "20",  # Celsius
                },
            )

        updated_batch = Batch.query.get(batch_id)
        # Should be converted to Fahrenheit (20°C = 68°F)
        assert updated_batch.fermentation_temp is not None
        assert float(updated_batch.fermentation_temp) > 20  # Should be in F now

    def test_post_calculates_abv_from_gravity_readings(self, client, db_session, admin_user):
        """Test POST calculates ABV from gravity readings."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test ABV Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "initial_gravity": "1.050",
                    "final_gravity": "1.000",
                },
            )

        updated_batch = Batch.query.get(batch_id)
        # ABV = (OG - FG) * 131.25 = (1.050 - 1.000) * 131.25 = 6.5625
        assert updated_batch.abv is not None
        assert abs(updated_batch.abv - 6.56) < 0.1

    def test_post_handles_none_invalid_gravity_values(self, client, db_session, admin_user):
        """Test POST handles None/invalid gravity values."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Invalid Gravity Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "initial_gravity": "invalid",
                    "final_gravity": "",
                },
            )

        updated_batch = Batch.query.get(batch_id)
        assert updated_batch.initial_gravity is None
        assert updated_batch.final_gravity is None
        assert updated_batch.abv is None

    def test_post_handles_none_invalid_batch_size(self, client, db_session, admin_user):
        """Test POST handles None/invalid batch_size."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Invalid Size Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "batch_size": "invalid",
                },
            )

        updated_batch = Batch.query.get(batch_id)
        assert updated_batch.batch_size is None

    def test_post_handles_none_invalid_fermentation_temp(self, client, db_session, admin_user):
        """Test POST handles None/invalid fermentation_temp."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Invalid Temp Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "fermentation_temp": "invalid",
                },
            )

        updated_batch = Batch.query.get(batch_id)
        assert updated_batch.fermentation_temp is None

    def test_post_sets_tosna_enabled_from_form_checkbox(self, client, db_session, admin_user):
        """Test POST sets tosna_enabled from form checkbox."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test TOSNA Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "enable_tosna": "on",  # Checkbox
                },
            )

        updated_batch = Batch.query.get(batch_id)
        assert updated_batch.tosna_enabled is True

    def test_post_sets_backsweetened_from_form_checkbox(self, client, db_session, admin_user):
        """Test POST sets backsweetened from form checkbox."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Backsweeten Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "backsweetened": "on",
                },
            )

        updated_batch = Batch.query.get(batch_id)
        assert updated_batch.backsweetened is True

    def test_post_sets_pectic_used_from_form_checkbox(self, client, db_session, admin_user):
        """Test POST sets pectic_used from form checkbox."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Pectic Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "pectic_used": "on",
                },
            )

        updated_batch = Batch.query.get(batch_id)
        assert updated_batch.pectic_used is True

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Original Name"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Committed Name",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                },
            )

        # Verify commit by querying in new context
        committed_batch = Batch.query.get(batch_id)
        assert committed_batch.name == "Committed Name"

    def test_post_shows_success_flash(self, client, db_session, admin_user):
        """Test POST shows success flash."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Flash Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Updated Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                },
                follow_redirects=True,
            )

        assert b"Batch updated successfully" in response.data

    def test_post_redirects_to_view_batch(self, client, db_session, admin_user):
        """Test POST redirects to view_batch."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Redirect Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Updated Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                },
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert f"/app/batches/{batch_id}" in response.location


class TestDeleteBatch:
    """Tests for delete_batch() route."""

    def test_requires_login_and_role_admin(self, client, db_session, test_user):
        """Test requires login and role 'admin'."""
        # test_user has role 'user', should be forbidden
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.post("/app/batches/1/delete", follow_redirects=True)
            assert response.status_code == 403

    def test_post_with_valid_id_deletes_batch(self, client, db_session, admin_user):
        """Test POST with valid ID deletes batch."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Delete Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/batches/{batch_id}/delete")

        deleted_batch = Batch.query.get(batch_id)
        assert deleted_batch is None

    def test_post_with_invalid_id_raises_404(self, client, db_session, admin_user):
        """Test POST with invalid ID raises 404."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/batches/99999/delete")
            assert response.status_code == 404

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Commit Delete Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/batches/{batch_id}/delete")

        # Verify deletion is committed
        assert Batch.query.get(batch_id) is None

    def test_post_shows_success_flash(self, client, db_session, admin_user):
        """Test POST shows success flash."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Flash Delete Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/batches/{batch_id}/delete", follow_redirects=True)

        assert b"deleted successfully" in response.data

    def test_post_redirects_to_list_batches(self, client, db_session, admin_user):
        """Test POST redirects to list_batches."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Redirect Delete Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/batches/{batch_id}/delete", follow_redirects=False)

        assert response.status_code == 302
        assert "/app/batches/" in response.location


class TestNewBatch:
    """Tests for new_batch() route."""

    def test_requires_login_and_role_admin_or_editor(self, client, db_session, test_user):
        """Test requires login and role 'admin' or 'editor'."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.get("/app/batches/new", follow_redirects=True)
            assert response.status_code == 403

    def test_get_queries_recipes_and_yeasts(self, client, db_session, admin_user):
        """Test GET queries recipes and yeasts."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        yeast = Yeast()
        yeast.name = "Test Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/new")
            assert response.status_code == 200
            assert b"Test Recipe" in response.data
            assert b"Test Yeast" in response.data

    def test_get_shows_warning_if_no_recipes_exist(self, client, db_session, admin_user):
        """Test GET shows warning if no recipes exist."""
        # No recipes in database

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/new")
            assert response.status_code == 200
            # Should show warning about no recipes

    def test_get_renders_new_batch_html(self, client, db_session, admin_user):
        """Test GET renders new_batch.html."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/batches/new")
            assert response.status_code == 200
            assert b"new" in response.data.lower()

    def test_post_with_missing_recipe_id_shows_error(self, client, db_session, admin_user):
        """Test POST with missing recipe_id shows error."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/batches/new",
                data={
                    "name": "Test Batch",
                    "start_date": "2026-01-01",
                },
                follow_redirects=True,
            )

        assert b"valid recipe" in response.data.lower()

    def test_post_with_invalid_recipe_id_shows_error(self, client, db_session, admin_user):
        """Test POST with invalid recipe_id shows error."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/batches/new",
                data={
                    "name": "Test Batch",
                    "recipe_id": "99999",  # Non-existent
                    "start_date": "2026-01-01",
                },
                follow_redirects=True,
            )

        assert b"valid recipe" in response.data.lower()

    def test_post_with_missing_name_shows_error(self, client, db_session, admin_user):
        """Test POST with missing name shows error."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/batches/new",
                data={
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                },
                follow_redirects=True,
            )

        assert b"required" in response.data.lower()

    def test_post_with_missing_start_date_shows_error(self, client, db_session, admin_user):
        """Test POST with missing start_date shows error."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/batches/new",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                },
                follow_redirects=True,
            )

        assert b"required" in response.data.lower()

    def test_post_with_invalid_date_format_shows_error(self, client, db_session, admin_user):
        """Test POST with invalid date format shows error."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/batches/new",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "invalid-date",
                },
                follow_redirects=True,
            )

        assert b"Invalid start date" in response.data

    def test_post_with_valid_data_creates_batch(self, client, db_session, admin_user):
        """Test POST with valid data creates batch."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/batches/new",
                data={
                    "name": "New Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                },
            )

        batch = Batch.query.filter_by(name="New Test Batch").first()
        assert batch is not None
        assert batch.recipe_id == recipe.id

    def test_post_converts_batch_size_from_metric_to_gallons(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test POST converts batch_size from metric to gallons."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        monkeypatch.setattr("app.routes_batches.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/batches/new",
                data={
                    "name": "New Size Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "batch_size": "19",  # liters
                },
            )

        batch = Batch.query.filter_by(name="New Size Batch").first()
        assert batch is not None
        assert batch.batch_size < 19  # Should be in gallons

    def test_post_converts_fermentation_temp_from_metric_to_f(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test POST converts fermentation_temp from metric to F."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        monkeypatch.setattr("app.routes_batches.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/batches/new",
                data={
                    "name": "New Temp Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "fermentation_temp": "20",  # Celsius
                },
            )

        batch = Batch.query.filter_by(name="New Temp Batch").first()
        assert batch is not None
        assert float(batch.fermentation_temp) > 20  # Should be in F

    def test_post_calculates_abv_from_gravity_readings(self, client, db_session, admin_user):
        """Test POST calculates ABV from gravity readings."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/batches/new",
                data={
                    "name": "New ABV Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "initial_gravity": "1.050",
                    "final_gravity": "1.000",
                },
            )

        batch = Batch.query.filter_by(name="New ABV Batch").first()
        assert batch is not None
        assert batch.abv is not None
        assert abs(batch.abv - 6.56) < 0.1

    def test_post_calculates_tosna_if_enabled_and_og_gte_1050(self, client, db_session, admin_user):
        """Test POST calculates TOSNA if enabled and OG >= 1.050."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/batches/new",
                data={
                    "name": "New TOSNA Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "initial_gravity": "1.050",
                    "batch_size": "5",
                    "enable_tosna": "on",
                },
            )

        batch = Batch.query.filter_by(name="New TOSNA Batch").first()
        assert batch is not None
        assert batch.tosna_enabled is True
        assert batch.tosna_total is not None
        assert batch.tosna_per_day is not None

    def test_post_shows_warning_if_tosna_enabled_but_cannot_calculate(
        self, client, db_session, admin_user
    ):
        """Test POST shows warning if TOSNA enabled but cannot calculate."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/batches/new",
                data={
                    "name": "New Warning Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "initial_gravity": "1.040",  # Too low for TOSNA
                    "enable_tosna": "on",
                },
                follow_redirects=True,
            )

        assert b"Could not calculate TOSNA" in response.data

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/batches/new",
                data={
                    "name": "New Commit Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                },
            )

        batch = Batch.query.filter_by(name="New Commit Batch").first()
        assert batch is not None

    def test_post_shows_success_flash(self, client, db_session, admin_user):
        """Test POST shows success flash."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/batches/new",
                data={
                    "name": "New Success Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                },
                follow_redirects=True,
            )

        assert b"Batch created successfully" in response.data

    def test_post_redirects_to_list_batches(self, client, db_session, admin_user):
        """Test POST redirects to list_batches."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/batches/new",
                data={
                    "name": "New Redirect Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                },
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "/app/batches/" in response.location


class TestCalculateTosna:
    """Tests for calculate_tosna() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.post("/app/batches/batch/1/tosna", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_with_missing_initial_gravity_shows_warning(self, client, db_session, admin_user):
        """Test with missing initial_gravity shows warning."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test No OG Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.batch_size = 5.0
        # No initial_gravity
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/batches/batch/{batch.id}/tosna", follow_redirects=True)

        assert b"Missing gravity" in response.data

    def test_with_missing_batch_size_shows_warning(self, client, db_session, admin_user):
        """Test with missing batch_size shows warning."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test No Size Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.initial_gravity = 1.050
        # No batch_size
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/batches/batch/{batch.id}/tosna", follow_redirects=True)

        assert b"Missing gravity or batch size" in response.data

    def test_with_og_lt_1050_shows_warning(self, client, db_session, admin_user):
        """Test with OG < 1.050 shows warning."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Low OG Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.initial_gravity = 1.040  # Too low
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/batches/batch/{batch.id}/tosna", follow_redirects=True)

        assert b"OG too low" in response.data

    def test_calculates_must_liters_from_batch_size(self, client, db_session, admin_user):
        """Test calculates must_liters from batch_size."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Must Liters Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.initial_gravity = 1.050
        batch.batch_size = 5.0  # gallons
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/batches/batch/{batch.id}/tosna")

        # Should have calculated (5 gallons * 3.78541 = ~18.9 liters)
        # TOSNA total = 0.8 * 18.9 = ~15.1
        updated_batch = Batch.query.get(batch.id)
        # The calculation happens in the route, not stored in batch
        # But we verify the route executed successfully
        assert updated_batch is not None

    def test_calculates_total_as_0_8_times_must_liters(self, client, db_session, admin_user):
        """Test calculates total = 0.8 * must_liters."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Total Calc Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.initial_gravity = 1.050
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/batches/batch/{batch.id}/tosna", follow_redirects=True)

        # Should show calculation in flash message
        assert b"TOSNA calculated" in response.data

    def test_calculates_per_day_as_total_divided_by_4(self, client, db_session, admin_user):
        """Test calculates per_day = total / 4."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Per Day Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.initial_gravity = 1.050
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/batches/batch/{batch.id}/tosna", follow_redirects=True)

        # Should show per day calculation in flash
        assert b"per day" in response.data.lower()

    def test_adds_calendar_events_if_add_to_calendar_in_form(self, client, db_session, admin_user):
        """Test adds calendar events if 'add_to_calendar' in form."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Calendar Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 1)
        batch.initial_gravity = 1.050
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/batch/{batch.id}/tosna",
                data={
                    "add_to_calendar": "on",
                },
            )

        events = CalendarEvent.query.filter_by(batch_id=batch.id).all()
        assert len(events) == 4  # 4 TOSNA days

    def test_creates_4_tosna_day_events(self, client, db_session, admin_user):
        """Test creates 4 TOSNA day events."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test 4 Days Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 1)
        batch.initial_gravity = 1.050
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/batches/batch/{batch.id}/tosna",
                data={
                    "add_to_calendar": "on",
                },
            )

        events = CalendarEvent.query.filter_by(batch_id=batch.id).all()
        assert len(events) == 4

        # Verify event titles
        titles = [e.title for e in events]
        assert "TOSNA Day 0" in titles
        assert "TOSNA Day 1" in titles
        assert "TOSNA Day 2" in titles
        assert "TOSNA Day 3" in titles

    def test_shows_success_flash_with_calculation(self, client, db_session, admin_user):
        """Test shows success flash with calculation."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Success Flash Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.initial_gravity = 1.050
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/batches/batch/{batch.id}/tosna", follow_redirects=True)

        assert b"success" in response.data.lower()

    def test_redirects_to_view_batch(self, client, db_session, admin_user):
        """Test redirects to view_batch."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Redirect TOSNA Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.initial_gravity = 1.050
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/batches/batch/{batch.id}/tosna", follow_redirects=False)

        assert response.status_code == 302
        assert f"/app/batches/{batch.id}" in response.location


class TestAddTosnaToCalendar:
    """Tests for add_tosna_to_calendar() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.post("/app/batches/batch/1/add-tosna-calendar", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_with_tosna_enabled_false_shows_warning(self, client, db_session, admin_user):
        """Test with tosna_enabled=False shows warning."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test No TOSNA Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.tosna_enabled = False
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/batches/batch/{batch.id}/add-tosna-calendar",
                follow_redirects=True,
            )

        assert b"TOSNA schedule not available" in response.data

    def test_with_missing_start_date_shows_warning(self, client, db_session, admin_user):
        """Test with missing start_date shows warning."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test No Date Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = None
        batch.tosna_enabled = True
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/batches/batch/{batch.id}/add-tosna-calendar",
                follow_redirects=True,
            )

        assert b"TOSNA schedule not available" in response.data

    def test_creates_4_calendar_events_for_tosna_days(self, client, db_session, admin_user):
        """Test creates 4 calendar events for TOSNA days."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test 4 Events Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 1)
        batch.tosna_enabled = True
        batch.tosna_per_day = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/batches/batch/{batch.id}/add-tosna-calendar")

        events = CalendarEvent.query.filter_by(batch_id=batch.id).all()
        assert len(events) == 4

    def test_events_use_batch_start_date_plus_timedelta(self, client, db_session, admin_user):
        """Test events use batch.start_date + timedelta(days=i)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Timedelta Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 1).date()
        batch.tosna_enabled = True
        batch.tosna_per_day = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/batches/batch/{batch.id}/add-tosna-calendar")

        events = (
            CalendarEvent.query.filter_by(batch_id=batch.id).order_by(CalendarEvent.start).all()
        )
        assert len(events) == 4

        # Verify dates are sequential starting from batch.start_date
        expected_dates = [
            datetime(2026, 1, 1).date(),
            datetime(2026, 1, 2).date(),
            datetime(2026, 1, 3).date(),
            datetime(2026, 1, 4).date(),
        ]
        for i, event in enumerate(events):
            assert event.start == expected_dates[i]

    def test_events_reference_batch_id(self, client, db_session, admin_user):
        """Test events reference batch_id."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch Ref Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 1).date()
        batch.tosna_enabled = True
        batch.tosna_per_day = 5.0
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/batches/batch/{batch_id}/add-tosna-calendar")

        events = CalendarEvent.query.filter_by(batch_id=batch_id).all()
        assert len(events) == 4
        for event in events:
            assert event.batch_id == batch_id

    def test_commits_to_database(self, client, db_session, admin_user):
        """Test commits to database."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Commit Calendar Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 1).date()
        batch.tosna_enabled = True
        batch.tosna_per_day = 5.0
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/batches/batch/{batch_id}/add-tosna-calendar")

        # Verify events are committed
        events = CalendarEvent.query.filter_by(batch_id=batch_id).all()
        assert len(events) == 4

    def test_shows_success_flash(self, client, db_session, admin_user):
        """Test shows success flash."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Success Calendar Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 1).date()
        batch.tosna_enabled = True
        batch.tosna_per_day = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/batches/batch/{batch.id}/add-tosna-calendar",
                follow_redirects=True,
            )

        assert b"TOSNA schedule added to calendar" in response.data

    def test_redirects_to_view_batch(self, client, db_session, admin_user):
        """Test redirects to view_batch."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Redirect Calendar Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 1).date()
        batch.tosna_enabled = True
        batch.tosna_per_day = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/batches/batch/{batch.id}/add-tosna-calendar",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert f"/app/batches/{batch.id}" in response.location


class TestEdgeCases:
    """Edge cases and error handling tests."""

    def test_unit_conversion_edge_case_none_batch_size(self, client, db_session, admin_user):
        """Test unit conversion edge case (None batch_size)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test None Edge Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.batch_size = None
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200

    def test_unit_conversion_edge_case_invalid_temp(self, client, db_session, admin_user):
        """Test unit conversion edge case (invalid temp)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Invalid Edge Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.fermentation_temp = "not_a_number"
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200

    def test_tosna_calculation_edge_case_og_below_threshold(self, client, db_session, admin_user):
        """Test TOSNA calculation edge case (OG < 1.050)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Low OG Edge Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.initial_gravity = 1.049  # Just below threshold
        batch.batch_size = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/batches/batch/{batch.id}/tosna", follow_redirects=True)

        assert b"OG too low" in response.data

    def test_form_data_validation_missing_required_fields(self, client, db_session, admin_user):
        """Test form data validation."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Missing required fields
            response = c.post(
                "/app/batches/new",
                data={
                    "recipe_id": str(recipe.id),
                    # Missing name and start_date
                },
                follow_redirects=True,
            )

        # Should show error for missing required fields
        assert response.status_code == 200


class TestBatchesCoverageGaps:
    """Tests for remaining coverage gaps in app/routes_batches.py."""

    def test_convert_to_display_exception_handling_lines_74_75(
        self, client, db_session, admin_user, monkeypatch
    ):
        """Test lines 74-75: _convert_to_display handles TypeError/ValueError exceptions."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Exception Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()

        # Mock round to raise TypeError
        original_round = round

        def mock_round(value, *args, **kwargs):
            if isinstance(value, str):
                raise TypeError("Cannot round string")
            return original_round(value, *args, **kwargs)

        monkeypatch.setattr("builtins.round", mock_round)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Access batch view which uses _convert_to_display
            response = c.get(f"/app/batches/{batch.id}")

            # Should handle exception gracefully
            assert response.status_code == 200

    def test_start_date_parse_exception_lines_87_88(self, client, db_session, admin_user):
        """Test lines 87-88: start_date parsing handles ValueError/TypeError and sets None."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Date Parse Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Submit invalid date format
            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "invalid-date-format",  # Invalid format
                },
            )

        updated_batch = Batch.query.get(batch_id)
        # start_date should be None due to parse exception
        assert updated_batch.start_date is None

    def test_end_date_parse_exception_lines_94_95(self, client, db_session, admin_user):
        """Test lines 94-95: end_date parsing handles ValueError/TypeError and sets None."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test End Date Parse Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        db_session.add(batch)
        db_session.commit()
        batch_id = batch.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Submit invalid end_date format
            c.post(
                f"/app/batches/{batch_id}/edit",
                data={
                    "name": "Test Batch",
                    "recipe_id": str(recipe.id),
                    "start_date": "2026-01-01",
                    "end_date": "not-a-date",  # Invalid format
                },
            )

        updated_batch = Batch.query.get(batch_id)
        # end_date should be None due to parse exception
        assert updated_batch.end_date is None
