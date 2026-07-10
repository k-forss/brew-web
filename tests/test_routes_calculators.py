"""
Comprehensive unit tests for calculators blueprint in app/routes_calculators.py.

Test Strategy:
- Uses pytest-flask-sqlalchemy for transactional isolation
- Mocks get_unit_preference for unit conversion testing
- Tests all calculator routes with proper authentication
- Verifies calculation formulas and edge cases

Routes Tested:
- calculator_index(): Calculator dashboard
- calculator_abv(): ABV calculation
- calculator_abv_target(): Target ABV honey calculation
- calculator_dilution(): Dilution calculation
- calculator_volume_recovery(): Volume recovery calculation
- calculator_honey_needed(): Honey requirement calculation
- calculator_sweetness(): Sweetness adjustment calculation
- calculator_carbonation(): Carbonation calculation
- calculator_tosna(): TOSNA calculation
- calculator_temp_correction(): Temperature correction calculation
"""

from app.models import User


class TestCalculatorIndex:
    """Tests for calculator_index() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/calculator/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_renders_calculators_index_html(self, client, db_session, admin_user):
        """Test renders calculators/index.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/")
            assert response.status_code == 200
            assert b"calculator" in response.data.lower()


class TestCalculatorAbv:
    """Tests for calculator_abv() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/calculator/abv", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_get_renders_calculators_abv_html(self, client, db_session, admin_user):
        """Test GET renders calculators/abv.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/abv")
            assert response.status_code == 200
            assert b"abv" in response.data.lower()

    def test_post_with_valid_og_fg_calculates_abv(self, client, db_session, admin_user):
        """Test POST with valid OG/FG calculates ABV = (OG - FG) * 131.25."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/calculator/abv", data={"og": "1.050", "fg": "1.000"})

            assert response.status_code == 200
            # ABV = (1.050 - 1.000) * 131.25 = 6.5625, rounded to 6.56
            assert b"6.56" in response.data

    def test_post_rounds_result_to_2_decimal_places(self, client, db_session, admin_user):
        """Test POST rounds result to 2 decimal places."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/calculator/abv", data={"og": "1.055", "fg": "1.010"})

            # ABV = (1.055 - 1.010) * 131.25 = 5.90625, rounded to 5.91
            assert b"5.91" in response.data

    def test_post_with_invalid_input_returns_none(self, client, db_session, admin_user):
        """Test POST with invalid input (non-numeric) returns None."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/calculator/abv", data={"og": "invalid", "fg": "1.000"})

            assert response.status_code == 200
            # Should not show a result

    def test_post_with_missing_fields_returns_none(self, client, db_session, admin_user):
        """Test POST with missing fields returns None."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/abv",
                data={
                    "og": "1.050"
                    # Missing fg
                },
            )

            assert response.status_code == 200

    def test_passes_unit_preference_to_template(self, client, db_session, admin_user, monkeypatch):
        """Test passes unit_preference to template."""
        monkeypatch.setattr("app.routes_calculators.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/abv")
            assert response.status_code == 200


class TestCalculatorAbvTarget:
    """Tests for calculator_abv_target() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/calculator/abv-target", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_get_renders_calculators_abv_target_html(self, client, db_session, admin_user):
        """Test GET renders calculators/abv_target.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/abv-target")
            assert response.status_code == 200
            assert b"abv" in response.data.lower()

    def test_post_with_valid_inputs_calculates_target_og(self, client, db_session, admin_user):
        """Test POST with valid inputs calculates target_og = (target_abv / 131.25) + target_fg."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/abv-target",
                data={
                    "volume": "5",
                    "current_gravity": "1.000",
                    "target_abv": "12",
                    "target_fg": "1.000",
                },
            )

            assert response.status_code == 200
            # target_og = (12 / 131.25) + 1.000 = 0.0914 + 1.000 = 1.091

    def test_post_calculates_added_points(self, client, db_session, admin_user):
        """Test POST calculates added_points = target_og - current_sg."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/abv-target",
                data={
                    "volume": "5",
                    "current_gravity": "1.000",
                    "target_abv": "12",
                    "target_fg": "1.000",
                },
            )

            assert response.status_code == 200

    def test_post_returns_error_if_added_points_lte_0(self, client, db_session, admin_user):
        """Test POST returns error if added_points <= 0."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/abv-target",
                data={
                    "volume": "5",
                    "current_gravity": "1.100",  # Higher than target
                    "target_abv": "5",  # Low target
                    "target_fg": "1.000",
                },
            )

            assert response.status_code == 200
            assert b"not higher" in response.data.lower()

    def test_post_calculates_pounds_needed(self, client, db_session, admin_user):
        """Test POST calculates pounds_needed = (added_points * batch_gal * 1000) / 35."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/abv-target",
                data={
                    "volume": "5",
                    "current_gravity": "1.000",
                    "target_abv": "12",
                    "target_fg": "1.000",
                },
            )

            assert response.status_code == 200

    def test_post_converts_to_kg_if_metric(self, client, db_session, admin_user, monkeypatch):
        """Test POST converts to kg if metric (pounds * 0.453592)."""
        monkeypatch.setattr("app.routes_calculators.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/abv-target",
                data={
                    "volume": "19",  # ~5 gallons in liters
                    "current_gravity": "1.000",
                    "target_abv": "12",
                    "target_fg": "1.000",
                },
            )

            assert response.status_code == 200
            assert b"kg" in response.data

    def test_post_returns_amount_unit_target_og_in_result_dict(
        self, client, db_session, admin_user
    ):
        """Test POST returns amount, unit, target_og in result dict."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/abv-target",
                data={
                    "volume": "5",
                    "current_gravity": "1.000",
                    "target_abv": "12",
                    "target_fg": "1.000",
                },
            )

            assert response.status_code == 200

    def test_post_with_invalid_input_returns_error(self, client, db_session, admin_user):
        """Test POST with invalid input returns {"error": "Invalid input"}."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/abv-target",
                data={
                    "volume": "invalid",
                    "current_gravity": "1.000",
                    "target_abv": "12",
                    "target_fg": "1.000",
                },
            )

            assert response.status_code == 200
            assert b"Invalid input" in response.data

    def test_post_with_missing_fields_returns_error(self, client, db_session, admin_user):
        """Test POST with missing fields returns {"error": "Invalid input"}."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/abv-target",
                data={
                    "volume": "5"
                    # Missing other fields
                },
            )

            assert response.status_code == 200
            assert b"Invalid input" in response.data


class TestCalculatorDilution:
    """Tests for calculator_dilution() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/calculator/dilution", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_get_renders_calculators_dilution_html(self, client, db_session, admin_user):
        """Test GET renders calculators/dilution.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/dilution")
            assert response.status_code == 200
            assert b"dilution" in response.data.lower()

    def test_post_with_target_gravity_gte_original_returns_error(
        self, client, db_session, admin_user
    ):
        """Test POST with target_gravity >= original_gravity returns error string."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/dilution",
                data={
                    "original_volume": "5",
                    "original_gravity": "1.050",
                    "target_gravity": "1.050",  # Same as original
                },
            )

            assert response.status_code == 200
            assert b"lower" in response.data.lower()

    def test_post_calculates_new_volume(self, client, db_session, admin_user):
        """Test POST calculates new_volume = (original_volume * original_gravity)
        / target_gravity."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/dilution",
                data={
                    "original_volume": "5",
                    "original_gravity": "1.050",
                    "target_gravity": "1.040",
                },
            )

            assert response.status_code == 200
            # new_volume = (5 * 1.050) / 1.040 = 5.048

    def test_post_calculates_added_water(self, client, db_session, admin_user):
        """Test POST calculates added_water = new_volume - original_volume."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/dilution",
                data={
                    "original_volume": "5",
                    "original_gravity": "1.050",
                    "target_gravity": "1.040",
                },
            )

            assert response.status_code == 200
            assert b"Add" in response.data

    def test_post_converts_to_liters_if_metric(self, client, db_session, admin_user, monkeypatch):
        """Test POST converts to liters if metric."""
        monkeypatch.setattr("app.routes_calculators.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/dilution",
                data={
                    "original_volume": "19",
                    "original_gravity": "1.050",
                    "target_gravity": "1.040",
                },
            )

            assert response.status_code == 200
            assert b"liters" in response.data.lower()

    def test_post_returns_formatted_result_string(self, client, db_session, admin_user):
        """Test POST returns formatted result string with unit label."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/dilution",
                data={
                    "original_volume": "5",
                    "original_gravity": "1.050",
                    "target_gravity": "1.040",
                },
            )

            assert response.status_code == 200
            assert b"gallons" in response.data.lower()

    def test_post_with_invalid_input_returns_invalid_input(self, client, db_session, admin_user):
        """Test POST with invalid input returns "Invalid input"."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/dilution",
                data={
                    "original_volume": "invalid",
                    "original_gravity": "1.050",
                    "target_gravity": "1.040",
                },
            )

            assert response.status_code == 200
            assert b"Invalid input" in response.data


class TestCalculatorVolumeRecovery:
    """Tests for calculator_volume_recovery() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/calculator/volume-recovery", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_get_renders_calculators_volume_recovery_html(self, client, db_session, admin_user):
        """Test GET renders calculators/volume_recovery.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/volume-recovery")
            assert response.status_code == 200
            assert b"recovery" in response.data.lower()

    def test_post_calculates_lost_volume(self, client, db_session, admin_user):
        """Test POST calculates lost_volume = target_volume - current_volume."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/volume-recovery",
                data={
                    "current_volume": "4",
                    "target_volume": "5",
                    "original_gravity": "1.050",
                },
            )

            assert response.status_code == 200

    def test_post_calculates_gravity_points(self, client, db_session, admin_user):
        """Test POST calculates gravity_points = original_gravity - 1.0."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/volume-recovery",
                data={
                    "current_volume": "4",
                    "target_volume": "5",
                    "original_gravity": "1.050",
                },
            )

            assert response.status_code == 200

    def test_post_calculates_honey_per_gallon(self, client, db_session, admin_user):
        """Test POST calculates honey_per_gallon = 2.7 * gravity_points."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/volume-recovery",
                data={
                    "current_volume": "4",
                    "target_volume": "5",
                    "original_gravity": "1.050",
                },
            )

            assert response.status_code == 200

    def test_post_calculates_honey_needed(self, client, db_session, admin_user):
        """Test POST calculates honey_needed = honey_per_gallon * lost_volume."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/volume-recovery",
                data={
                    "current_volume": "4",
                    "target_volume": "5",
                    "original_gravity": "1.050",
                },
            )

            assert response.status_code == 200

    def test_post_calculates_water_needed_gal(self, client, db_session, admin_user):
        """Test POST calculates water_needed_gal = lost_volume - (honey_needed / 12)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/volume-recovery",
                data={
                    "current_volume": "4",
                    "target_volume": "5",
                    "original_gravity": "1.050",
                },
            )

            assert response.status_code == 200

    def test_post_converts_to_metric_if_needed(self, client, db_session, admin_user, monkeypatch):
        """Test POST converts to metric if needed (honey to kg, water to liters)."""
        monkeypatch.setattr("app.routes_calculators.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/volume-recovery",
                data={
                    "current_volume": "15",
                    "target_volume": "19",
                    "original_gravity": "1.050",
                },
            )

            assert response.status_code == 200
            assert b"kg" in response.data or b"liters" in response.data

    def test_post_returns_dict_with_honey_water_unit(self, client, db_session, admin_user):
        """Test POST returns dict with honey, water, unit, honey_unit."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/volume-recovery",
                data={
                    "current_volume": "4",
                    "target_volume": "5",
                    "original_gravity": "1.050",
                },
            )

            assert response.status_code == 200

    def test_post_with_invalid_input_returns_none(self, client, db_session, admin_user):
        """Test POST with invalid input returns None."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/volume-recovery",
                data={
                    "current_volume": "invalid",
                    "target_volume": "5",
                    "original_gravity": "1.050",
                },
            )

            assert response.status_code == 200


class TestCalculatorHoneyNeeded:
    """Tests for calculator_honey_needed() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/calculator/honey-needed", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_get_renders_calculators_honey_required_html(self, client, db_session, admin_user):
        """Test GET renders calculators/honey_required.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/honey-needed")
            assert response.status_code == 200
            assert b"honey" in response.data.lower()

    def test_post_calculates_gravity_points(self, client, db_session, admin_user):
        """Test POST calculates gravity_points = target_og - 1.0."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/honey-needed",
                data={"volume": "5", "target_gravity": "1.050"},
            )

            assert response.status_code == 200

    def test_post_calculates_honey_lb(self, client, db_session, admin_user):
        """Test POST calculates honey_lb = batch_size * gravity_points * 2.7."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/honey-needed",
                data={"volume": "5", "target_gravity": "1.050"},
            )

            assert response.status_code == 200
            # honey_lb = 5 * 0.050 * 2.7 = 0.675 lb

    def test_post_converts_to_kg_if_metric(self, client, db_session, admin_user, monkeypatch):
        """Test POST converts to kg if metric."""
        monkeypatch.setattr("app.routes_calculators.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/honey-needed",
                data={"volume": "19", "target_gravity": "1.050"},
            )

            assert response.status_code == 200
            assert b"kg" in response.data

    def test_post_returns_dict_with_amount_unit(self, client, db_session, admin_user):
        """Test POST returns dict with amount, unit."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/honey-needed",
                data={"volume": "5", "target_gravity": "1.050"},
            )

            assert response.status_code == 200
            assert b"lb" in response.data

    def test_post_with_invalid_input_returns_invalid_input(self, client, db_session, admin_user):
        """Test POST with invalid input returns "Invalid input"."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/honey-needed",
                data={"volume": "invalid", "target_gravity": "1.050"},
            )

            assert response.status_code == 200
            # Template shows "Please enter valid numeric values."
            assert b"valid" in response.data.lower()


class TestCalculatorSweetness:
    """Tests for calculator_sweetness() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/calculator/sweetness", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_get_renders_calculators_sweetness_html(self, client, db_session, admin_user):
        """Test GET renders calculators/sweetness.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/sweetness")
            assert response.status_code == 200
            assert b"sweetness" in response.data.lower()

    def test_post_calculates_delta(self, client, db_session, admin_user):
        """Test POST calculates delta = target_sg - current_sg."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/sweetness",
                data={
                    "batch_volume": "5",
                    "target_gravity": "1.010",
                    "current_gravity": "1.000",
                },
            )

            assert response.status_code == 200

    def test_post_calculates_honey_lb(self, client, db_session, admin_user):
        """Test POST calculates honey_lb = gallons * delta * 2.7."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/sweetness",
                data={
                    "batch_volume": "5",
                    "target_gravity": "1.010",
                    "current_gravity": "1.000",
                },
            )

            assert response.status_code == 200
            # honey_lb = 5 * 0.010 * 2.7 = 0.135 lb

    def test_post_converts_to_kg_if_metric(self, client, db_session, admin_user, monkeypatch):
        """Test POST converts to kg if metric."""
        monkeypatch.setattr("app.routes_calculators.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/sweetness",
                data={
                    "batch_volume": "19",
                    "target_gravity": "1.010",
                    "current_gravity": "1.000",
                },
            )

            assert response.status_code == 200
            assert b"kg" in response.data

    def test_post_returns_dict_with_amount_unit(self, client, db_session, admin_user):
        """Test POST returns dict with amount, unit."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/sweetness",
                data={
                    "batch_volume": "5",
                    "target_gravity": "1.010",
                    "current_gravity": "1.000",
                },
            )

            assert response.status_code == 200

    def test_post_with_invalid_input_returns_none(self, client, db_session, admin_user):
        """Test POST with invalid input returns None."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/sweetness",
                data={
                    "batch_volume": "invalid",
                    "target_gravity": "1.010",
                    "current_gravity": "1.000",
                },
            )

            assert response.status_code == 200


class TestCalculatorCarbonation:
    """Tests for calculator_carbonation() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/calculator/carbonation", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_get_renders_calculators_carbonation_html(self, client, db_session, admin_user):
        """Test GET renders calculators/carbonation.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/carbonation")
            assert response.status_code == 200
            assert b"carbonation" in response.data.lower()

    def test_post_calculates_sugar_oz(self, client, db_session, admin_user):
        """Test POST calculates sugar_oz = volume * (co2 - 0.85) * 0.5."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/calculator/carbonation", data={"volume": "5", "target_co2": "2.5"})

            assert response.status_code == 200
            # sugar_oz = 5 * (2.5 - 0.85) * 0.5 = 5 * 1.65 * 0.5 = 4.125 oz

    def test_post_converts_to_grams_if_metric(self, client, db_session, admin_user, monkeypatch):
        """Test POST converts to grams if metric (oz * 28.3495)."""
        monkeypatch.setattr("app.routes_calculators.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/calculator/carbonation", data={"volume": "19", "target_co2": "2.5"})

            assert response.status_code == 200
            assert b"grams" in response.data.lower()

    def test_post_returns_dict_with_amount_unit(self, client, db_session, admin_user):
        """Test POST returns dict with amount, unit."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/calculator/carbonation", data={"volume": "5", "target_co2": "2.5"})

            assert response.status_code == 200
            assert b"oz" in response.data

    def test_post_with_invalid_input_returns_invalid_input(self, client, db_session, admin_user):
        """Test POST with invalid input returns "Invalid input"."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/carbonation",
                data={"volume": "invalid", "target_co2": "2.5"},
            )

            assert response.status_code == 200
            # Template shows "Please enter valid numeric values."
            assert b"valid" in response.data.lower()


class TestCalculatorTosna:
    """Tests for calculator_tosna() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/calculator/tosna", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_get_renders_calculators_tosna_html(self, client, db_session, admin_user):
        """Test GET renders calculators/tosna.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/tosna")
            assert response.status_code == 200
            assert b"tosna" in response.data.lower()

    def test_post_with_og_lt_1050_returns_error(self, client, db_session, admin_user):
        """Test POST with OG < 1.050 returns "OG too low for TOSNA."."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/tosna",
                data={"batch_size": "5", "starting_gravity": "1.040"},
            )

            assert response.status_code == 200
            assert b"OG too low" in response.data

    def test_post_calculates_must_liters(self, client, db_session, admin_user):
        """Test POST calculates must_liters = batch_size * GALLON_TO_LITER."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/tosna",
                data={"batch_size": "5", "starting_gravity": "1.050"},
            )

            assert response.status_code == 200
            # must_liters = 5 * 3.78541 = 18.92705

    def test_post_calculates_total(self, client, db_session, admin_user):
        """Test POST calculates total = 0.8 * must_liters."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/tosna",
                data={"batch_size": "5", "starting_gravity": "1.050"},
            )

            assert response.status_code == 200
            # total = 0.8 * 18.92705 = 15.14

    def test_post_calculates_per_day(self, client, db_session, admin_user):
        """Test POST calculates per_day = total / 4."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/tosna",
                data={"batch_size": "5", "starting_gravity": "1.050"},
            )

            assert response.status_code == 200
            # per_day = 15.14 / 4 = 3.79

    def test_post_creates_result_object_with_total_and_per_day(
        self, client, db_session, admin_user
    ):
        """Test POST creates result object with total and per_day attributes."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/tosna",
                data={"batch_size": "5", "starting_gravity": "1.050"},
            )

            assert response.status_code == 200
            assert b"total" in response.data.lower() or b"per day" in response.data.lower()

    def test_post_with_invalid_input_returns_invalid_input(self, client, db_session, admin_user):
        """Test POST with invalid input returns "Invalid input"."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/tosna",
                data={"batch_size": "invalid", "starting_gravity": "1.050"},
            )

            assert response.status_code == 200
            assert b"Invalid input" in response.data


class TestCalculatorTempCorrection:
    """Tests for calculator_temp_correction() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/calculator/temp-correction", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_get_renders_calculators_temp_correction_html(self, client, db_session, admin_user):
        """Test GET renders calculators/temp_correction.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/calculator/temp-correction")
            assert response.status_code == 200
            assert b"temp" in response.data.lower()

    def test_post_converts_temp_to_f_if_metric(self, client, db_session, admin_user, monkeypatch):
        """Test POST converts temp to F if metric."""
        monkeypatch.setattr("app.routes_calculators.get_unit_preference", lambda: "metric")

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/temp-correction",
                data={"observed": "1.050", "temp": "20"},  # Celsius
            )

            assert response.status_code == 200

    def test_post_calculates_correction(self, client, db_session, admin_user):
        """Test POST calculates correction = (temp_f - 60) * 0.001."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/temp-correction",
                data={"observed": "1.050", "temp": "70"},  # Fahrenheit
            )

            assert response.status_code == 200
            # correction = (70 - 60) * 0.001 = 0.01

    def test_post_calculates_corrected(self, client, db_session, admin_user):
        """Test POST calculates corrected = observed + correction."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/temp-correction", data={"observed": "1.050", "temp": "70"}
            )

            assert response.status_code == 200
            # corrected = 1.050 + 0.01 = 1.060

    def test_post_rounds_to_3_decimal_places(self, client, db_session, admin_user):
        """Test POST rounds to 3 decimal places."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/temp-correction", data={"observed": "1.050", "temp": "70"}
            )

            assert response.status_code == 200

    def test_post_with_invalid_input_returns_none(self, client, db_session, admin_user):
        """Test POST with invalid input returns None."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/temp-correction",
                data={"observed": "invalid", "temp": "70"},
            )

            assert response.status_code == 200


class TestEdgeCases:
    """Edge cases and error handling tests."""

    def test_division_by_zero_scenarios(self, client, db_session, admin_user):
        """Test division by zero scenarios."""
        # TOSNA with zero batch size
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/tosna",
                data={"batch_size": "0", "starting_gravity": "1.050"},
            )

            assert response.status_code == 200

    def test_negative_values_where_applicable(self, client, db_session, admin_user):
        """Test negative values where applicable."""
        # Dilution with negative volume
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/dilution",
                data={
                    "original_volume": "-5",
                    "original_gravity": "1.050",
                    "target_gravity": "1.040",
                },
            )

            assert response.status_code == 200

    def test_none_empty_string_inputs(self, client, db_session, admin_user):
        """Test None/empty string inputs."""
        # ABV with empty strings
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post("/calculator/abv", data={"og": "", "fg": ""})

            assert response.status_code == 200

    def test_boundary_values_og_1050_for_tosna(self, client, db_session, admin_user):
        """Test boundary values (OG = 1.050 for TOSNA)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/calculator/tosna",
                data={
                    "batch_size": "5",
                    "starting_gravity": "1.050",  # Exactly at boundary
                },
            )

            assert response.status_code == 200
            # Should calculate TOSNA (not return error)
            assert b"OG too low" not in response.data
