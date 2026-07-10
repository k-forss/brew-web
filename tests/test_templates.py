"""Template rendering tests for brew-web.

Tests verify that templates render without errors with mock context.
"""


class TestBatchDetailTemplate:
    """Tests for batch_detail.html template (TOSNA conditional blocks)."""

    def test_batch_detail_renders_with_tosna_enabled(self, app, db_session, admin_user):
        """Test batch_detail.html renders when TOSNA is enabled."""
        from app.models import Batch, Recipe

        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "TOSNA Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.tosna_enabled = True
        batch.tosna_total = 500
        batch.tosna_per_day = 125
        db_session.add(batch)
        db_session.commit()

        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200
            assert b"TOSNA" in response.data

    def test_batch_detail_renders_with_tosna_disabled(self, app, db_session, admin_user):
        """Test batch_detail.html renders when TOSNA is disabled."""
        from app.models import Batch, Recipe

        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Non-TOSNA Batch"
        batch.recipe_id = recipe.id
        batch.alcohol_type = "Mead"
        batch.tosna_enabled = False
        db_session.add(batch)
        db_session.commit()

        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/batches/{batch.id}")
            assert response.status_code == 200


class TestCalculatorTemplates:
    """Tests for calculator templates (error handling)."""

    def test_abv_calculator_renders_with_error(self, app, admin_user):
        """Test abv.html renders with error result."""
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Test with invalid OG/FG that would cause error
            response = c.post(
                "/app/calculator/abv",
                data={"og": "1.000", "fg": "1.050"},  # FG > OG is invalid
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_abv_calculator_renders_with_success(self, app, admin_user):
        """Test abv.html renders with successful result."""
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/calculator/abv",
                data={"og": "1.090", "fg": "1.010"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"ABV" in response.data

    def test_carbonation_calculator_renders_with_error(self, app, admin_user):
        """Test carbonation.html renders with error result."""
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/calculator/carbonation",
                data={"volume": "5", "target_co2": "invalid"},
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_carbonation_calculator_renders_with_success(self, app, admin_user):
        """Test carbonation.html renders with successful result."""
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/calculator/carbonation",
                data={"volume": "5", "target_co2": "2.5"},
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_honey_required_calculator_renders_with_error(self, app, admin_user):
        """Test honey_required.html renders with error result."""
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/calculator/honey-needed",
                data={"volume": "5", "target_gravity": "invalid"},
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_honey_required_calculator_renders_with_success(self, app, admin_user):
        """Test honey_required.html renders with successful result."""
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/calculator/honey-needed",
                data={"volume": "5", "target_gravity": "1.090"},
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestSettingsSidebarTemplate:
    """Tests for settings/_sidebar.html template (url_for changes)."""

    def test_settings_sidebar_renders_for_admin(self, app, db_session, admin_user):
        """Test _sidebar.html renders for admin user."""
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/")
            assert response.status_code == 200
            assert b"Settings" in response.data
            assert b"Administration" in response.data

    def test_settings_sidebar_renders_for_user(self, app, db_session, test_user):
        """Test _sidebar.html renders for regular user (no admin link)."""
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.get("/app/settings/")
            assert response.status_code == 200
            assert b"Settings" in response.data
            # Regular users should not see Administration link
            assert b"Administration" not in response.data

    def test_settings_sidebar_url_for_links_work(self, app, db_session, admin_user):
        """Test that url_for links in sidebar work correctly."""
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/settings/")
            assert response.status_code == 200
            # Check that sidebar renders with valid links
            assert b"settings" in response.data.lower()
