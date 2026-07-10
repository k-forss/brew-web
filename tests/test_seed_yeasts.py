"""
Comprehensive unit tests for yeast seeding function in app/seed_yeasts.py.

Test Strategy:
- Uses pytest-flask-sqlalchemy for transactional isolation
- Tests duplicate prevention logic (by name + alcohol_type)
- Tests all 16 default yeast entries
- Edge cases: all existing, none existing, partial existing

Functions Tested:
- seed_yeasts(): Data seeding with duplicate prevention
"""

from io import StringIO

import pytest

from app.models import Yeast


class TestSeedYeasts:
    """Tests for seed_yeasts() function."""

    def test_defines_16_default_yeast_entries(self, db_session):
        """Test defines 16 default yeast entries."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Run seed function
        seed_yeasts()

        # Count yeasts - should have 16 unique entries
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

    def test_checks_for_existing_yeast_by_name_and_alcohol_type(self, db_session, admin_user):
        """Test checks for existing yeast by name before adding."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Pre-populate one yeast
        existing_yeast = Yeast()
        existing_yeast.name = "Lalvin 71B-1122"
        existing_yeast.alcohol_type = "Mead"
        existing_yeast.tolerance = "14%"
        db_session.add(existing_yeast)
        db_session.commit()

        # Run seed function
        seed_yeasts()

        # Should have 16 yeasts (15 new + 1 existing)
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

        # Verify the existing yeast wasn't duplicated
        duplicate_count = Yeast.query.filter_by(name="Lalvin 71B-1122", alcohol_type="Mead").count()
        assert duplicate_count == 1

    def test_adds_only_non_duplicate_yeasts(self, db_session):
        """Test adds only non-duplicate yeasts."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Pre-populate half the yeasts
        yeast_data = [
            {
                "name": "Lalvin 71B-1122",
                "alcohol_type": "Mead",
                "tolerance": "14%",
                "strength": "Medium",
                "sweetness_retention": "Moderate",
                "flocculation": "Low",
                "attenuation": "70%",
                "notes": "Fruity esters; smooths acidity.",
            },
            {
                "name": "Lalvin D47",
                "alcohol_type": "Mead",
                "tolerance": "14%",
                "strength": "Medium",
                "sweetness_retention": "Low",
                "flocculation": "Medium",
                "attenuation": "75%",
                "notes": "Clean fermentation; enhances mouthfeel.",
            },
            {
                "name": "Lalvin K1V-1116",
                "alcohol_type": "Mead",
                "tolerance": "18%",
                "strength": "Strong",
                "sweetness_retention": "Low",
                "flocculation": "Low",
                "attenuation": "75%",
                "notes": "Strong fermenter; useful for restarting stuck fermentations.",
            },
            {
                "name": "Lalvin EC-1118",
                "alcohol_type": "Mead",
                "tolerance": "18%",
                "strength": "Strong",
                "sweetness_retention": "Low",
                "flocculation": "High",
                "attenuation": "80%",
                "notes": "Reliable and clean; high alcohol tolerance.",
            },
            {
                "name": "Lalvin EC-1118",
                "alcohol_type": "Wine",
                "tolerance": "18%",
                "strength": "Strong",
                "sweetness_retention": "Low",
                "flocculation": "High",
                "attenuation": "80%",
                "notes": "Champagne yeast; ferments fast and dry.",
            },
            {
                "name": "Lalvin RC-212",
                "alcohol_type": "Wine",
                "tolerance": "16%",
                "strength": "Medium",
                "sweetness_retention": "Medium",
                "flocculation": "Medium",
                "attenuation": "75%",
                "notes": "Great for red wines; enhances tannin and color.",
            },
            {
                "name": "Lalvin D47",
                "alcohol_type": "Wine",
                "tolerance": "14%",
                "strength": "Medium",
                "sweetness_retention": "Low",
                "flocculation": "Medium",
                "attenuation": "75%",
                "notes": "White wine favorite; promotes round mouthfeel.",
            },
            {
                "name": "Red Star Premier Rouge",
                "alcohol_type": "Wine",
                "tolerance": "14%",
                "strength": "Medium",
                "sweetness_retention": "Low",
                "flocculation": "Medium",
                "attenuation": "73%",
                "notes": "Great for full-bodied red wines.",
            },
        ]

        for data in yeast_data:
            yeast = Yeast()
            yeast.name = data["name"]
            yeast.alcohol_type = data["alcohol_type"]
            yeast.tolerance = data["tolerance"]
            db_session.add(yeast)
        db_session.commit()

        # Run seed function
        seed_yeasts()

        # Should have 16 yeasts total (8 existing + 8 new)
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

    def test_counts_added_yeasts(self, db_session):
        """Test counts added yeasts."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Run seed function and capture output
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            seed_yeasts()
        finally:
            sys.stdout = old_stdout

        output = captured_output.getvalue()

        # Verify success message
        assert "Yeast data seeded successfully" in output

        # Verify 16 yeasts were added
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

    def test_commits_to_database(self, db_session):
        """Test commits to database."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Run seed function
        seed_yeasts()

        # Verify commit by querying in fresh context
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

        # Verify specific yeast exists
        yeast = Yeast.query.filter_by(name="Lalvin 71B-1122", alcohol_type="Mead").first()
        assert yeast is not None

    def test_prints_success_message(self, db_session):
        """Test prints success message."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Run seed function and capture output
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            seed_yeasts()
        finally:
            sys.stdout = old_stdout

        output = captured_output.getvalue()

        # Verify success message
        assert "Yeast data seeded successfully" in output

    def test_yeast_data_includes_all_fields(self, db_session):
        """Test yeast data includes all fields: name, alcohol_type, tolerance,
        strength, sweetness_retention, flocculation, attenuation, notes."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Run seed function
        seed_yeasts()

        # Verify a sample yeast has all fields
        yeast = Yeast.query.filter_by(name="Lalvin 71B-1122", alcohol_type="Mead").first()
        assert yeast is not None
        assert yeast.name == "Lalvin 71B-1122"
        assert yeast.alcohol_type == "Mead"
        assert yeast.tolerance == "14%"
        assert yeast.strength == "Medium"
        assert yeast.sweetness_retention == "Moderate"
        assert yeast.flocculation == "Low"
        assert yeast.attenuation == "70%"
        assert yeast.notes == "Fruity esters; smooths acidity."

        # Verify another yeast with different characteristics
        yeast2 = Yeast.query.filter_by(name="SafAle US-05", alcohol_type="Beer").first()
        assert yeast2 is not None
        assert yeast2.name == "SafAle US-05"
        assert yeast2.alcohol_type == "Beer"
        assert yeast2.tolerance == "10%"
        assert yeast2.strength == "Medium"
        assert yeast2.sweetness_retention == "Medium"
        assert yeast2.flocculation == "Medium"
        assert yeast2.attenuation == "78%"
        assert yeast2.notes == "Clean American ale yeast."


class TestSeedYeastsEdgeCases:
    """Edge cases and error handling tests for seed_yeasts()."""

    def test_with_all_yeasts_already_existing(self, db_session):
        """Test with all yeasts already existing (adds 0)."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Pre-populate all 16 yeasts
        seed_yeasts()
        initial_count = Yeast.query.count()
        assert initial_count == 16

        # Run seed function again
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            seed_yeasts()
        finally:
            sys.stdout = old_stdout

        # Should still have 16 yeasts (no duplicates added)
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

        # Verify success message still printed
        output = captured_output.getvalue()
        assert "Yeast data seeded successfully" in output

    def test_with_no_yeasts_existing(self, db_session):
        """Test with no yeasts existing (adds all 16)."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Verify no yeasts exist
        initial_count = Yeast.query.count()
        assert initial_count == 0

        # Run seed function
        seed_yeasts()

        # Should have 16 yeasts
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

    def test_with_some_yeasts_existing(self, db_session):
        """Test with some yeasts existing (adds only missing)."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Pre-populate 8 yeasts (half)
        yeast_data = [
            {
                "name": "Lalvin 71B-1122",
                "alcohol_type": "Mead",
                "tolerance": "14%",
                "strength": "Medium",
                "sweetness_retention": "Moderate",
                "flocculation": "Low",
                "attenuation": "70%",
                "notes": "Fruity esters; smooths acidity.",
            },
            {
                "name": "Lalvin D47",
                "alcohol_type": "Mead",
                "tolerance": "14%",
                "strength": "Medium",
                "sweetness_retention": "Low",
                "flocculation": "Medium",
                "attenuation": "75%",
                "notes": "Clean fermentation; enhances mouthfeel.",
            },
            {
                "name": "Lalvin K1V-1116",
                "alcohol_type": "Mead",
                "tolerance": "18%",
                "strength": "Strong",
                "sweetness_retention": "Low",
                "flocculation": "Low",
                "attenuation": "75%",
                "notes": "Strong fermenter; useful for restarting stuck fermentations.",
            },
            {
                "name": "Lalvin EC-1118",
                "alcohol_type": "Mead",
                "tolerance": "18%",
                "strength": "Strong",
                "sweetness_retention": "Low",
                "flocculation": "High",
                "attenuation": "80%",
                "notes": "Reliable and clean; high alcohol tolerance.",
            },
            {
                "name": "Lalvin EC-1118",
                "alcohol_type": "Wine",
                "tolerance": "18%",
                "strength": "Strong",
                "sweetness_retention": "Low",
                "flocculation": "High",
                "attenuation": "80%",
                "notes": "Champagne yeast; ferments fast and dry.",
            },
            {
                "name": "Lalvin RC-212",
                "alcohol_type": "Wine",
                "tolerance": "16%",
                "strength": "Medium",
                "sweetness_retention": "Medium",
                "flocculation": "Medium",
                "attenuation": "75%",
                "notes": "Great for red wines; enhances tannin and color.",
            },
            {
                "name": "Lalvin D47",
                "alcohol_type": "Wine",
                "tolerance": "14%",
                "strength": "Medium",
                "sweetness_retention": "Low",
                "flocculation": "Medium",
                "attenuation": "75%",
                "notes": "White wine favorite; promotes round mouthfeel.",
            },
            {
                "name": "Red Star Premier Rouge",
                "alcohol_type": "Wine",
                "tolerance": "14%",
                "strength": "Medium",
                "sweetness_retention": "Low",
                "flocculation": "Medium",
                "attenuation": "73%",
                "notes": "Great for full-bodied red wines.",
            },
        ]

        for data in yeast_data:
            yeast = Yeast()
            yeast.name = data["name"]
            yeast.alcohol_type = data["alcohol_type"]
            yeast.tolerance = data["tolerance"]
            db_session.add(yeast)
        db_session.commit()

        # Verify 8 yeasts exist
        initial_count = Yeast.query.count()
        assert initial_count == 8

        # Run seed function
        seed_yeasts()

        # Should have 16 yeasts total (8 existing + 8 new)
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

    def test_database_commit_failures(self, db_session, monkeypatch):
        """Test database commit failures."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Mock db.session.commit to raise an exception
        def mock_commit():
            raise Exception("Database commit failed")

        monkeypatch.setattr(db_session, "commit", mock_commit)

        # Should raise exception
        with pytest.raises(Exception, match="Database commit failed"):
            seed_yeasts()

    def test_duplicate_prevention_by_name_and_alcohol_type_combination(self, db_session):
        """Test duplicate prevention uses name + alcohol_type combination."""
        from app.seed_yeasts import seed_yeasts

        # Clear any existing yeasts
        Yeast.query.delete()
        db_session.commit()

        # Pre-populate Lalvin EC-1118 for Mead
        yeast1 = Yeast()
        yeast1.name = "Lalvin EC-1118"
        yeast1.alcohol_type = "Mead"
        yeast1.tolerance = "18%"
        db_session.add(yeast1)
        db_session.commit()

        # Run seed function
        seed_yeasts()

        # Should have 16 yeasts (Lalvin EC-1118 for Mead exists, but Wine/Cider versions are added)
        yeast_count = Yeast.query.count()
        assert yeast_count == 16

        # Verify Lalvin EC-1118 exists for multiple alcohol types
        mead_yeast = Yeast.query.filter_by(name="Lalvin EC-1118", alcohol_type="Mead").first()
        wine_yeast = Yeast.query.filter_by(name="Lalvin EC-1118", alcohol_type="Wine").first()
        cider_yeast = Yeast.query.filter_by(
            name="Lalvin EC-1118", alcohol_type="Hard Cider"
        ).first()

        assert mead_yeast is not None
        assert wine_yeast is not None
        assert cider_yeast is not None

        # Each should be unique (no duplicates)
        assert Yeast.query.filter_by(name="Lalvin EC-1118", alcohol_type="Mead").count() == 1
        assert Yeast.query.filter_by(name="Lalvin EC-1118", alcohol_type="Wine").count() == 1
        assert Yeast.query.filter_by(name="Lalvin EC-1118", alcohol_type="Hard Cider").count() == 1
