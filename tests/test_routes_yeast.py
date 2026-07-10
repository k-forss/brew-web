"""
Comprehensive unit tests for yeast blueprint in app/routes_yeast.py.

Test Strategy:
- Uses pytest-flask-sqlalchemy for transactional isolation
- Tests all routes with proper authentication/authorization
- Edge cases: duplicate yeasts, missing fields, invalid IDs

Routes Tested:
- list_yeasts(): Yeast categorization by alcohol type
- restore_yeasts(): Seed default yeasts
- add_yeast(): Create new yeast
- delete_yeast(): Remove yeast
- edit_yeast(): Update yeast
"""

from app.models import User, Yeast


class TestListYeasts:
    """Tests for list_yeasts() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/app/yeasts/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_queries_yeasts_by_alcohol_type_mead(self, client, db_session, admin_user):
        """Test queries yeasts by alcohol_type: Mead."""
        yeast = Yeast()
        yeast.name = "Test Mead Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/yeasts/")
            assert response.status_code == 200
            assert b"Test Mead Yeast" in response.data

    def test_queries_yeasts_by_alcohol_type_wine(self, client, db_session, admin_user):
        """Test queries yeasts by alcohol_type: Wine."""
        yeast = Yeast()
        yeast.name = "Test Wine Yeast"
        yeast.alcohol_type = "Wine"
        db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/yeasts/")
            assert response.status_code == 200
            assert b"Test Wine Yeast" in response.data

    def test_queries_yeasts_by_alcohol_type_beer(self, client, db_session, admin_user):
        """Test queries yeasts by alcohol_type: Beer."""
        yeast = Yeast()
        yeast.name = "Test Beer Yeast"
        yeast.alcohol_type = "Beer"
        db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/yeasts/")
            assert response.status_code == 200
            assert b"Test Beer Yeast" in response.data

    def test_queries_yeasts_by_alcohol_type_hard_cider(self, client, db_session, admin_user):
        """Test queries yeasts by alcohol_type: Hard Cider."""
        yeast = Yeast()
        yeast.name = "Test Cider Yeast"
        yeast.alcohol_type = "Hard Cider"
        db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/yeasts/")
            assert response.status_code == 200
            assert b"Test Cider Yeast" in response.data

    def test_queries_other_yeasts_with_in_filter_or_alcohol_type_none(
        self, client, db_session, admin_user
    ):
        """Test queries "other" yeasts with ~in_() filter or alcohol_type == None."""
        yeast = Yeast()
        yeast.name = "Test Other Yeast"
        yeast.alcohol_type = "Sake"  # Not in the main categories
        db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/yeasts/")
            assert response.status_code == 200
            assert b"Test Other Yeast" in response.data

    def test_renders_yeasts_html_with_categorized_yeasts(self, client, db_session, admin_user):
        """Test renders yeasts.html with categorized yeasts."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/yeasts/")
            assert response.status_code == 200
            assert b"yeast" in response.data.lower()


class TestRestoreYeasts:
    """Tests for restore_yeasts() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.post("/app/yeasts/restore", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_role_admin(self, client, db_session, test_user):
        """Test requires role 'admin' (@role_required)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.post("/app/yeasts/restore", follow_redirects=True)
            assert response.status_code == 403

    def test_post_defines_16_default_yeast_entries(self, client, db_session, admin_user):
        """Test POST defines 16 default yeast entries."""
        # Clear any existing yeasts first
        Yeast.query.delete()
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/yeasts/restore")

        # Count yeasts added
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

    def test_post_checks_if_yeast_exists_by_name_before_adding(
        self, client, db_session, admin_user
    ):
        """Test POST checks if yeast exists by name before adding."""
        # Add a yeast that will be a duplicate (same name AND alcohol_type)
        yeast = Yeast()
        yeast.name = "Lalvin 71B-1122"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/yeasts/restore")

        # Should not have duplicates (same name + alcohol_type)
        duplicate_count = Yeast.query.filter_by(name="Lalvin 71B-1122", alcohol_type="Mead").count()
        assert duplicate_count == 1

    def test_post_adds_only_non_duplicate_yeasts(self, client, db_session, admin_user):
        """Test POST adds only non-duplicate yeasts."""
        # Add all 16 default yeasts first
        for i in range(16):
            yeast = Yeast()
            yeast.name = f"Yeast {i}"
            yeast.alcohol_type = "Mead"
            db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/yeasts/restore")

        # Should have original 16 + 16 new = 32
        yeast_count = Yeast.query.count()
        assert yeast_count == 32

    def test_post_counts_added_yeasts(self, client, db_session, admin_user):
        """Test POST counts added yeasts."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/yeasts/restore", follow_redirects=True)

        assert b"16 yeast types restored" in response.data

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        # Clear any existing yeasts first
        Yeast.query.delete()
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/yeasts/restore")

        # Verify commit by querying
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

    def test_post_shows_success_flash_with_count(self, client, db_session, admin_user):
        """Test POST shows success flash with count."""
        # Clear any existing yeasts first
        Yeast.query.delete()
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/yeasts/restore", follow_redirects=True)

        assert b"16 yeast types restored" in response.data

    def test_post_redirects_to_list_yeasts(self, client, db_session, admin_user):
        """Test POST redirects to list_yeasts."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/yeasts/restore", follow_redirects=False)

        assert response.status_code == 302
        assert "/app/yeasts/" in response.location

    def test_default_yeast_data_includes_all_fields(self, client, db_session, admin_user):
        """Test default yeast data includes: name, alcohol_type, tolerance,
        strength, sweetness_retention, flocculation, attenuation, notes."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post("/app/yeasts/restore")

        yeast = Yeast.query.filter_by(name="Lalvin EC-1118").first()
        assert yeast is not None
        assert yeast.name is not None
        assert yeast.alcohol_type is not None
        assert yeast.tolerance is not None
        assert yeast.strength is not None
        assert yeast.sweetness_retention is not None
        assert yeast.flocculation is not None
        assert yeast.attenuation is not None
        assert yeast.notes is not None


class TestAddYeast:
    """Tests for add_yeast() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.post("/app/yeasts/add", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_role_admin(self, client, db_session, test_user):
        """Test requires role 'admin' (@role_required)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.post("/app/yeasts/add", follow_redirects=True)
            assert response.status_code == 403

    def test_post_creates_yeast_from_form_fields(self, client, db_session, admin_user):
        """Test POST creates Yeast from form fields."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/yeasts/add",
                data={
                    "name": "Test Custom Yeast",
                    "alcohol_type": "Mead",
                },
            )

        yeast = Yeast.query.filter_by(name="Test Custom Yeast").first()
        assert yeast is not None

    def test_post_sets_all_fields(self, client, db_session, admin_user):
        """Test POST sets all fields: name, alcohol_type, tolerance, strength,
        sweetness_retention, flocculation, attenuation, notes."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/yeasts/add",
                data={
                    "name": "Full Field Yeast",
                    "alcohol_type": "Wine",
                    "tolerance": "15%",
                    "strength": "Strong",
                    "sweetness_retention": "High",
                    "flocculation": "Medium",
                    "attenuation": "80%",
                    "notes": "Test notes",
                },
            )

        yeast = Yeast.query.filter_by(name="Full Field Yeast").first()
        assert yeast is not None
        assert yeast.alcohol_type == "Wine"
        assert yeast.tolerance == "15%"
        assert yeast.strength == "Strong"
        assert yeast.sweetness_retention == "High"
        assert yeast.flocculation == "Medium"
        assert yeast.attenuation == "80%"
        assert yeast.notes == "Test notes"

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/yeasts/add",
                data={
                    "name": "Commit Test Yeast",
                    "alcohol_type": "Mead",
                },
            )

        yeast = Yeast.query.filter_by(name="Commit Test Yeast").first()
        assert yeast is not None

    def test_post_shows_success_flash_with_yeast_name(self, client, db_session, admin_user):
        """Test POST shows success flash with yeast name."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/yeasts/add",
                data={
                    "name": "Flash Test Yeast",
                    "alcohol_type": "Mead",
                },
                follow_redirects=True,
            )

        # HTML escapes single quotes as &#39;
        assert b"Yeast" in response.data
        assert b"Flash Test Yeast" in response.data
        assert b"added" in response.data

    def test_post_redirects_to_list_yeasts(self, client, db_session, admin_user):
        """Test POST redirects to list_yeasts."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/yeasts/add",
                data={
                    "name": "Redirect Test Yeast",
                    "alcohol_type": "Mead",
                },
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "/app/yeasts/" in response.location


class TestDeleteYeast:
    """Tests for delete_yeast() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.post("/app/yeasts/delete/1", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_role_admin(self, client, db_session, test_user):
        """Test requires role 'admin' (@role_required)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.post("/app/yeasts/delete/1", follow_redirects=True)
            assert response.status_code == 403

    def test_post_with_valid_id_deletes_yeast(self, client, db_session, admin_user):
        """Test POST with valid ID deletes yeast."""
        yeast = Yeast()
        yeast.name = "Delete Test Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()
        yeast_id = yeast.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/yeasts/delete/{yeast_id}")

        deleted = Yeast.query.get(yeast_id)
        assert deleted is None

    def test_post_with_invalid_id_raises_404(self, client, db_session, admin_user):
        """Test POST with invalid ID raises 404."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/yeasts/delete/99999")

        assert response.status_code == 404

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        yeast = Yeast()
        yeast.name = "Commit Delete Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()
        yeast_id = yeast.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(f"/app/yeasts/delete/{yeast_id}")

        assert Yeast.query.get(yeast_id) is None

    def test_post_shows_success_flash_with_yeast_name(self, client, db_session, admin_user):
        """Test POST shows success flash with yeast name."""
        yeast = Yeast()
        yeast.name = "Flash Delete Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()
        yeast_id = yeast.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/yeasts/delete/{yeast_id}", follow_redirects=True)

        # HTML escapes single quotes as &#39;
        assert b"Yeast" in response.data
        assert b"Flash Delete Yeast" in response.data
        assert b"deleted" in response.data

    def test_post_redirects_to_list_yeasts(self, client, db_session, admin_user):
        """Test POST redirects to list_yeasts."""
        yeast = Yeast()
        yeast.name = "Redirect Delete Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()
        yeast_id = yeast.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(f"/app/yeasts/delete/{yeast_id}", follow_redirects=False)

        assert response.status_code == 302
        assert "/app/yeasts/" in response.location


class TestEditYeast:
    """Tests for edit_yeast() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/app/yeasts/edit/1", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_role_admin(self, client, db_session, test_user):
        """Test requires role 'admin' (@role_required)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.get("/app/yeasts/edit/1", follow_redirects=True)
            assert response.status_code == 403

    def test_get_with_valid_id_returns_yeast(self, client, db_session, admin_user):
        """Test GET with valid ID returns yeast."""
        yeast = Yeast()
        yeast.name = "Edit Test Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/yeasts/edit/{yeast.id}")
            assert response.status_code == 200
            assert b"Edit Test Yeast" in response.data

    def test_get_with_invalid_id_raises_404(self, client, db_session, admin_user):
        """Test GET with invalid ID raises 404."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/yeasts/edit/99999")

        assert response.status_code == 404

    def test_get_renders_edit_yeast_html(self, client, db_session, admin_user):
        """Test GET renders edit_yeast.html."""
        yeast = Yeast()
        yeast.name = "Edit Render Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get(f"/app/yeasts/edit/{yeast.id}")
            assert response.status_code == 200
            assert b"edit" in response.data.lower()

    def test_post_with_valid_data_updates_all_yeast_fields(self, client, db_session, admin_user):
        """Test POST with valid data updates all yeast fields."""
        yeast = Yeast()
        yeast.name = "Original Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()
        yeast_id = yeast.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/yeasts/edit/{yeast_id}",
                data={
                    "name": "Updated Yeast",
                    "alcohol_type": "Wine",
                    "tolerance": "16%",
                    "strength": "Strong",
                    "sweetness_retention": "Low",
                    "flocculation": "High",
                    "attenuation": "85%",
                    "notes": "Updated notes",
                },
            )

        updated = Yeast.query.get(yeast_id)
        assert updated.name == "Updated Yeast"
        assert updated.alcohol_type == "Wine"
        assert updated.tolerance == "16%"
        assert updated.strength == "Strong"
        assert updated.sweetness_retention == "Low"
        assert updated.flocculation == "High"
        assert updated.attenuation == "85%"
        assert updated.notes == "Updated notes"

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        yeast = Yeast()
        yeast.name = "Original Commit Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()
        yeast_id = yeast.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                f"/app/yeasts/edit/{yeast_id}",
                data={
                    "name": "Updated Commit Yeast",
                    "alcohol_type": "Mead",
                },
            )

        updated = Yeast.query.get(yeast_id)
        assert updated.name == "Updated Commit Yeast"

    def test_post_shows_success_flash(self, client, db_session, admin_user):
        """Test POST shows success flash."""
        yeast = Yeast()
        yeast.name = "Flash Edit Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()
        yeast_id = yeast.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/yeasts/edit/{yeast_id}",
                data={
                    "name": "Updated Flash Yeast",
                    "alcohol_type": "Mead",
                },
                follow_redirects=True,
            )

        assert b"Yeast updated" in response.data

    def test_post_redirects_to_list_yeasts(self, client, db_session, admin_user):
        """Test POST redirects to list_yeasts."""
        yeast = Yeast()
        yeast.name = "Redirect Edit Yeast"
        yeast.alcohol_type = "Mead"
        db_session.add(yeast)
        db_session.commit()
        yeast_id = yeast.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                f"/app/yeasts/edit/{yeast_id}",
                data={
                    "name": "Updated Redirect Yeast",
                    "alcohol_type": "Mead",
                },
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "/app/yeasts/" in response.location


class TestEdgeCases:
    """Edge cases and error handling tests."""

    def test_missing_form_fields_in_add_yeast(self, client, db_session, admin_user):
        """Test missing form fields in add_yeast."""
        # alcohol_type is required by model, so provide it
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/yeasts/add",
                data={
                    "name": "Minimal Yeast",
                    "alcohol_type": "Mead",
                    # Other fields missing
                },
            )

        yeast = Yeast.query.filter_by(name="Minimal Yeast").first()
        assert yeast is not None
        # Missing fields should be None
        assert yeast.tolerance is None

    def test_missing_form_fields_in_edit_yeast(self, client, db_session, admin_user):
        """Test missing form fields in edit_yeast."""
        yeast = Yeast()
        yeast.name = "Edit Missing Fields Yeast"
        yeast.alcohol_type = "Mead"
        yeast.tolerance = "14%"
        db_session.add(yeast)
        db_session.commit()
        yeast_id = yeast.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Must provide alcohol_type as it's NOT NULL
            c.post(
                f"/app/yeasts/edit/{yeast_id}",
                data={
                    "name": "Updated Name",
                    "alcohol_type": "Mead",
                    # Other fields missing - should become None
                },
            )

        updated = Yeast.query.get(yeast_id)
        assert updated.name == "Updated Name"
        assert updated.tolerance is None

    def test_restore_yeasts_with_all_yeasts_already_existing_count_0(
        self, client, db_session, admin_user
    ):
        """Test restore_yeasts with all yeasts already existing (count = 0)."""
        # Add all 16 default yeasts first
        default_yeasts = [
            {"name": "Lalvin 71B-1122", "alcohol_type": "Mead"},
            {"name": "Lalvin D47", "alcohol_type": "Mead"},
            {"name": "Lalvin K1V-1116", "alcohol_type": "Mead"},
            {"name": "Lalvin EC-1118", "alcohol_type": "Mead"},
            {"name": "Lalvin EC-1118", "alcohol_type": "Wine"},
            {"name": "Lalvin RC-212", "alcohol_type": "Wine"},
            {"name": "Lalvin D47", "alcohol_type": "Wine"},
            {"name": "Red Star Premier Rouge", "alcohol_type": "Wine"},
            {"name": "Lalvin 71B-1122", "alcohol_type": "Wine"},
            {"name": "SafAle US-05", "alcohol_type": "Beer"},
            {"name": "Wyeast 1056 (American Ale)", "alcohol_type": "Beer"},
            {"name": "Nottingham Ale Yeast", "alcohol_type": "Beer"},
            {"name": "WLP775 English Cider", "alcohol_type": "Hard Cider"},
            {"name": "Mangrove Jack's M02", "alcohol_type": "Hard Cider"},
            {"name": "Nottingham Ale Yeast", "alcohol_type": "Hard Cider"},
            {"name": "Lalvin EC-1118", "alcohol_type": "Hard Cider"},
        ]
        for data in default_yeasts:
            yeast = Yeast()
            yeast.name = data["name"]
            yeast.alcohol_type = data["alcohol_type"]
            db_session.add(yeast)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/app/yeasts/restore", follow_redirects=True)

        # Should show 0 added
        assert b"0 yeast types restored" in response.data
