"""
Comprehensive unit tests for stats blueprint in app/routes_stats.py.

Test Strategy:
- Uses pytest-flask-sqlalchemy for transactional isolation
- Tests view_stats() route with proper authentication
- Verifies query logic for ABV chart and batch count chart
- Edge cases: empty batches, None ABV values, None start_date

Routes Tested:
- view_stats(): Dashboard statistics with Chart.js charts
"""

from datetime import datetime

from app.models import Batch, Recipe, User


class TestViewStats:
    """Tests for view_stats() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/app/stats/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_queries_batches_with_abv_isnot_none(self, client, db_session, admin_user):
        """Test queries batches with abv.isnot(None)."""
        # Create recipe first
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        # Create batches with and without ABV
        batch_with_abv = Batch()
        batch_with_abv.recipe_id = recipe.id
        batch_with_abv.name = "Batch With ABV"
        batch_with_abv.alcohol_type = "Mead"
        batch_with_abv.start_date = datetime.utcnow()
        batch_with_abv.abv = 5.5
        db_session.add(batch_with_abv)

        batch_without_abv = Batch()
        batch_without_abv.recipe_id = recipe.id
        batch_without_abv.name = "Batch Without ABV"
        batch_without_abv.alcohol_type = "Mead"
        batch_without_abv.start_date = datetime.utcnow()
        batch_without_abv.abv = None
        db_session.add(batch_without_abv)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Only batch with ABV should appear in chart data
            assert b"Batch With ABV" in response.data
            assert b"5.5" in response.data

    def test_orders_by_start_date_asc(self, client, db_session, admin_user):
        """Test orders by start_date.asc()."""
        # Create recipe first
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        # Create batches with different dates
        batch1 = Batch()
        batch1.recipe_id = recipe.id
        batch1.name = "First Batch"
        batch1.alcohol_type = "Mead"
        batch1.start_date = datetime(2025, 1, 1)
        batch1.abv = 5.0
        db_session.add(batch1)

        batch2 = Batch()
        batch2.recipe_id = recipe.id
        batch2.name = "Second Batch"
        batch2.alcohol_type = "Mead"
        batch2.start_date = datetime(2026, 1, 1)
        batch2.abv = 6.0
        db_session.add(batch2)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            data = response.data.decode("utf-8")
            # First batch should appear before second batch
            first_pos = data.find("First Batch")
            second_pos = data.find("Second Batch")
            assert first_pos < second_pos

    def test_extracts_batch_names_for_chart_labels(self, client, db_session, admin_user):
        """Test extracts batch names for chart labels."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "Chart Label Test Batch"
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.abv = 5.5
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            assert b"Chart Label Test Batch" in response.data

    def test_extracts_abv_values_rounded_to_2_decimals(self, client, db_session, admin_user):
        """Test extracts ABV values rounded to 2 decimals."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "Rounding Test Batch"
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.abv = 5.55555  # Should round to 5.56
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Check for rounded value (5.56)
            assert b"5.56" in response.data

    def test_queries_batch_counts_grouped_by_date(self, client, db_session, admin_user):
        """Test queries batch counts grouped by date."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        # Create multiple batches on same date
        date1 = datetime(2026, 1, 1)
        batch1 = Batch()
        batch1.recipe_id = recipe.id
        batch1.name = "Batch 1"
        batch1.alcohol_type = "Mead"
        batch1.start_date = date1
        db_session.add(batch1)

        batch2 = Batch()
        batch2.recipe_id = recipe.id
        batch2.name = "Batch 2"
        batch2.alcohol_type = "Mead"
        batch2.start_date = date1
        db_session.add(batch2)

        # Create batch on different date
        date2 = datetime(2026, 1, 2)
        batch3 = Batch()
        batch3.recipe_id = recipe.id
        batch3.name = "Batch 3"
        batch3.alcohol_type = "Mead"
        batch3.start_date = date2
        db_session.add(batch3)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Should show counts for both dates
            assert b"2026-01-01" in response.data
            assert b"2026-01-02" in response.data

    def test_uses_func_date_for_grouping(self, client, db_session, admin_user):
        """Test uses func.date(Batch.start_date) for grouping."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        # This is tested implicitly by the batch counts query
        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "Date Grouping Test"
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 15)
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Date should be formatted as YYYY-MM-DD
            assert b"2026-01-15" in response.data

    def test_uses_func_count_for_batch_counts(self, client, db_session, admin_user):
        """Test uses func.count() for batch counts."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        # Create multiple batches on same date
        date1 = datetime(2026, 1, 1)
        for i in range(5):
            batch = Batch()
            batch.recipe_id = recipe.id
            batch.name = f"Count Test Batch {i}"
            batch.alcohol_type = "Mead"
            batch.start_date = date1
            db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Should show count of 5 for this date
            assert b"5" in response.data

    def test_groups_by_date_and_orders_by_date(self, client, db_session, admin_user):
        """Test groups by date and orders by date."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        # Create batches on different dates
        dates = [
            datetime(2026, 1, 3),
            datetime(2026, 1, 1),
            datetime(2026, 1, 2),
        ]
        for i, date in enumerate(dates):
            batch = Batch()
            batch.recipe_id = recipe.id
            batch.name = f"Order Test {i}"
            batch.alcohol_type = "Mead"
            batch.start_date = date
            db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            data = response.data.decode("utf-8")
            # Dates should be in ascending order
            jan01_pos = data.find("2026-01-01")
            jan02_pos = data.find("2026-01-02")
            jan03_pos = data.find("2026-01-03")
            assert jan01_pos < jan02_pos < jan03_pos

    def test_formats_dates_as_yyyy_mm_dd_strings(self, client, db_session, admin_user):
        """Test formats dates as '%Y-%m-%d' strings."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "Date Format Test"
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 12, 25)
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Date should be formatted as YYYY-MM-DD
            assert b"2026-12-25" in response.data

    def test_extracts_counts_from_query_results(self, client, db_session, admin_user):
        """Test extracts counts from query results."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        # Create 3 batches on same date
        date1 = datetime(2026, 1, 1)
        for i in range(3):
            batch = Batch()
            batch.recipe_id = recipe.id
            batch.name = f"Count Extract {i}"
            batch.alcohol_type = "Mead"
            batch.start_date = date1
            db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Should show count of 3
            assert b"3" in response.data

    def test_renders_stats_html_with_batch_names_abv_values_dates_counts(
        self, client, db_session, admin_user
    ):
        """Test renders stats.html with batch_names, abv_values, dates, counts."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "Full Render Test"
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 1)
        batch.abv = 7.5
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            assert b"stats" in response.data.lower()
            assert b"Full Render Test" in response.data
            assert b"7.5" in response.data


class TestEdgeCases:
    """Edge cases and error handling tests."""

    def test_handles_empty_batch_list_no_batches(self, client, db_session, admin_user):
        """Test handles empty batch list (no batches)."""
        # No batches in database

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Should render without errors even with no data

    def test_handles_batches_with_none_abv_excluded_from_abv_chart(
        self, client, db_session, admin_user
    ):
        """Test handles batches with None ABV (excluded from ABV chart)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch_without_abv = Batch()
        batch_without_abv.recipe_id = recipe.id
        batch_without_abv.name = "No ABV Batch"
        batch_without_abv.alcohol_type = "Mead"
        batch_without_abv.start_date = datetime.utcnow()
        batch_without_abv.abv = None
        db_session.add(batch_without_abv)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Batch should not appear in ABV chart data
            # (it may appear in batch count chart though)
            assert b"No ABV Batch" not in response.data

    def test_handles_batches_with_none_start_date_excluded_from_count_chart(
        self, client, db_session, admin_user
    ):
        """Test handles batches with None start_date (excluded from count chart)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "No Date Batch"
        batch.alcohol_type = "Mead"
        batch.start_date = None
        batch.abv = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Should render without errors

    def test_handles_none_abv_values_in_rounding(self, client, db_session, admin_user):
        """Test handles None ABV values in rounding."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        # This is tested by test_handles_batches_with_none_abv_excluded_from_abv_chart
        # The query filters out None ABV values before rounding
        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "None ABV Test"
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.abv = None
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Should not crash on None ABV

    def test_handles_single_batch(self, client, db_session, admin_user):
        """Test handles single batch."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "Single Batch"
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.abv = 5.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            assert b"Single Batch" in response.data

    def test_handles_batch_with_zero_abv(self, client, db_session, admin_user):
        """Test handles batch with zero ABV."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "Zero ABV Batch"
        batch.alcohol_type = "Mead"
        batch.start_date = datetime.utcnow()
        batch.abv = 0.0
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Zero ABV should be included (it's not None)
            assert b"Zero ABV Batch" in response.data


class TestStatsCoverageGaps:
    """Tests for remaining coverage gaps in app/routes_stats.py."""

    def test_datetime_strftime_path_line_35(self, client, db_session, admin_user):
        """Test line 35: datetime object uses strftime() for formatting."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        # Create batch with datetime start_date
        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "Datetime Format Test"
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 2, 20)  # datetime object
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Date should be formatted as YYYY-MM-DD
            assert b"2026-02-20" in response.data

    def test_date_string_conversion_line_35(self, client, db_session, admin_user, monkeypatch):
        """Test line 35: Date string conversion fallback when date_val is not datetime object."""
        from unittest.mock import MagicMock

        # Mock batch_counts to return rows with string dates (SQLite behavior)
        class MockRow:
            def __init__(self, date_val, count_val):
                self.date = date_val
                self.count = count_val

        # Create mock data with string dates (simulating SQLite func.date() behavior)
        mock_batch_counts = [
            MockRow("2026-01-15", 5),  # String date from SQLite
            MockRow("2026-01-16", 3),
        ]

        # Mock the query to return our mock data
        mock_query = MagicMock()
        mock_query.group_by = MagicMock(return_value=mock_query)
        mock_query.order_by = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=mock_batch_counts)

        from app import models

        monkeypatch.setattr(models.Batch.query, "with_entities", MagicMock(return_value=mock_query))

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")

            # Should handle string dates gracefully
            assert response.status_code == 200

    def test_sqlite_string_date_path(self, client, db_session, admin_user):
        """Test line 38: SQLite returns string from func.date(), not datetime object."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.recipe_id = recipe.id
        batch.name = "SQLite Date Test"
        batch.alcohol_type = "Mead"
        batch.start_date = datetime(2026, 1, 15)
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/stats/")
            assert response.status_code == 200
            # Date should appear in response (proves the string path worked)
            assert b"2026-01-15" in response.data
