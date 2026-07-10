"""
Comprehensive unit tests for all utility functions in app/utils.py.

Test Strategy:
- Uses pytest-flask-sqlalchemy for transactional isolation (get_unit_preference)
- Mocks external dependencies (requests, current_app, current_user)
- Tests all functions with edge cases and error handling
- Real database tests for get_unit_preference() with AppSettings

Functions Tested:
- is_strong_password(): Password validation with regex patterns
- role_required(): Decorator for role-based access control
- check_for_updates(): GitHub version check with HTTP handling
- get_unit_preference(): Database-backed unit preference with error recovery
- is_metric(): Wrapper around get_unit_preference()
- read_import_status_file(): File I/O with JSON parsing
- Unit conversions: gallons_to_liters, liters_to_gallons, f_to_c, c_to_f
"""

from unittest.mock import MagicMock, Mock

import pytest
import requests

from sqlalchemy.exc import ProgrammingError
from werkzeug.exceptions import HTTPException

from app.models import AppSettings


class TestIsStrongPassword:
    """Tests for is_strong_password() function."""

    def test_valid_password_with_all_requirements(self):
        """Test valid password: 8+ chars, uppercase, lowercase, symbol."""
        from app.utils import is_strong_password

        assert is_strong_password("SecureP@ss")

    def test_too_short_password(self):
        """Test too short password (< 8 chars)."""
        from app.utils import is_strong_password

        assert not is_strong_password("Sh0rt!")

    def test_missing_uppercase_letter(self):
        """Test missing uppercase letter."""
        from app.utils import is_strong_password

        assert not is_strong_password("lowercase!@#")

    def test_missing_lowercase_letter(self):
        """Test missing lowercase letter."""
        from app.utils import is_strong_password

        assert not is_strong_password("UPPERCASE1!")

    def test_missing_symbol(self):
        """Test missing symbol (only alphanumeric)."""
        from app.utils import is_strong_password

        assert not is_strong_password("NoSymbol1")

    def test_empty_string(self):
        """Test empty string."""
        from app.utils import is_strong_password

        assert not is_strong_password("")

    def test_boundary_exactly_8_characters(self):
        """Test boundary: exactly 8 characters."""
        from app.utils import is_strong_password

        assert is_strong_password("Pass1!@#")

    def test_various_symbols(self):
        """Test symbols: various special characters (!@#$%^&*)."""
        from app.utils import is_strong_password

        assert is_strong_password("Test!123")
        assert is_strong_password("Test@123")
        assert is_strong_password("Test#123")
        assert is_strong_password("Test$123")
        assert is_strong_password("Test%123")
        assert is_strong_password("Test^123")
        assert is_strong_password("Test&123")
        assert is_strong_password("Test*123")

    def test_numbers_only_no_symbols(self):
        """Test numbers without symbols fails."""
        from app.utils import is_strong_password

        assert not is_strong_password("12345678")

    def test_symbols_only_no_letters(self):
        """Test symbols without letters fails."""
        from app.utils import is_strong_password

        assert not is_strong_password("!@#$%^&*")


class TestRoleRequired:
    """Tests for role_required() decorator from utils.py."""

    def test_decorator_with_allowed_role_returns_function_result(self, monkeypatch):
        """Test decorator with allowed role returns function result."""
        from app.utils import role_required

        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.utils.current_user", mock_user)

        @role_required("admin")
        def admin_func():
            return "access granted"

        result = admin_func()
        assert result == "access granted"

    def test_decorator_with_disallowed_role_raises_403(self, monkeypatch):
        """Test decorator with disallowed role raises 403."""
        from app.utils import role_required

        mock_user = Mock()
        mock_user.role = "user"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.utils.current_user", mock_user)

        @role_required("admin")
        def admin_func():
            return "should not reach here"

        with pytest.raises(HTTPException) as exc_info:
            admin_func()
        assert exc_info.value.code == 403

    def test_decorator_with_unauthenticated_user_raises_403(self, monkeypatch):
        """Test decorator with unauthenticated user raises 403."""
        from app.utils import role_required

        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.is_authenticated = False
        monkeypatch.setattr("app.utils.current_user", mock_user)

        @role_required("admin")
        def protected_func():
            return "should not reach here"

        with pytest.raises(HTTPException) as exc_info:
            protected_func()
        assert exc_info.value.code == 403

    def test_decorator_with_multiple_roles_any_match(self, monkeypatch):
        """Test decorator with multiple roles (any match allowed)."""
        from app.utils import role_required

        # Test with admin role
        mock_admin = Mock()
        mock_admin.role = "admin"
        mock_admin.is_authenticated = True
        monkeypatch.setattr("app.utils.current_user", mock_admin)

        @role_required("admin", "editor")
        def protected_func():
            return "access granted"

        result = protected_func()
        assert result == "access granted"

        # Test with editor role
        mock_editor = Mock()
        mock_editor.role = "editor"
        mock_editor.is_authenticated = True
        monkeypatch.setattr("app.utils.current_user", mock_editor)

        result = protected_func()
        assert result == "access granted"

    def test_decorator_preserves_function_metadata(self, monkeypatch):
        """Test decorator preserves function metadata (functools.wraps)."""
        from app.utils import role_required

        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.utils.current_user", mock_user)

        @role_required("admin")
        def documented_func():
            """This is the docstring."""
            pass

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is the docstring."

    def test_decorator_passes_arguments_to_wrapped_function(self, monkeypatch):
        """Test decorator passes arguments to wrapped function."""
        from app.utils import role_required

        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.utils.current_user", mock_user)

        @role_required("admin")
        def func_with_args(a, b, c):
            return a + b + c

        result = func_with_args(1, 2, 3)
        assert result == 6


class TestCheckForUpdates:
    """Tests for check_for_updates() function."""

    def test_successful_update_available(self, monkeypatch):
        """Test successful update available (version mismatch)."""
        from app import Config
        from app.utils import check_for_updates, reset_update_cache

        # Reset cache to ensure fresh request
        reset_update_cache()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "v999.0.0"  # Different from current version

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("app.utils.requests.get", mock_get)

        result = check_for_updates()

        assert result["update_available"] is True
        assert result["current"] == Config.VERSION
        assert result["latest"] == "v999.0.0"
        assert "error" not in result

    def test_no_update_available(self, monkeypatch):
        """Test no update available (version match)."""
        from app import Config
        from app.utils import check_for_updates, reset_update_cache

        # Reset cache to ensure fresh request
        reset_update_cache()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = Config.VERSION  # Same as current version

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("app.utils.requests.get", mock_get)

        result = check_for_updates()

        assert result["update_available"] is False
        assert result["current"] == Config.VERSION
        assert result["latest"] == Config.VERSION
        assert "error" not in result

    def test_http_error_requests_exception(self, monkeypatch):
        """Test HTTP error (requests exception)."""
        from app import Config
        from app.utils import check_for_updates, reset_update_cache

        # Reset cache to ensure fresh request
        reset_update_cache()

        def mock_get_exception(*args, **kwargs):
            raise requests.exceptions.RequestException("Network error")

        monkeypatch.setattr("app.utils.requests.get", mock_get_exception)

        result = check_for_updates()

        assert result["update_available"] is False
        assert result["current"] == Config.VERSION
        assert result["latest"] == "unknown"
        assert "error" in result

    def test_timeout_exception(self, monkeypatch):
        """Test timeout exception."""
        from app import Config
        from app.utils import check_for_updates, reset_update_cache

        # Reset cache to ensure fresh request
        reset_update_cache()

        def mock_get_timeout(*args, **kwargs):
            raise requests.exceptions.Timeout("Request timed out")

        monkeypatch.setattr("app.utils.requests.get", mock_get_timeout)

        result = check_for_updates()

        assert result["update_available"] is False
        assert result["current"] == Config.VERSION
        assert result["latest"] == "unknown"
        assert "error" in result

    def test_non_200_status_code(self, monkeypatch):
        """Test non-200 status code."""
        from app import Config
        from app.utils import check_for_updates, reset_update_cache

        # Reset cache to ensure fresh request
        reset_update_cache()

        mock_response = Mock()
        mock_response.status_code = 404

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("app.utils.requests.get", mock_get)

        result = check_for_updates()

        # Should fall through to default return (no update)
        assert result["update_available"] is False
        assert result["current"] == Config.VERSION
        assert result["latest"] == "unknown"

    def test_empty_response_body(self, monkeypatch):
        """Test empty response body."""
        from app import Config
        from app.utils import check_for_updates, reset_update_cache

        # Reset cache to ensure fresh request
        reset_update_cache()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = ""

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("app.utils.requests.get", mock_get)

        result = check_for_updates()

        assert result["update_available"] is True  # Empty != VERSION
        assert result["current"] == Config.VERSION
        assert result["latest"] == ""

    def test_response_with_whitespace(self, monkeypatch):
        """Test response with whitespace (strip handling)."""
        from app.utils import check_for_updates, reset_update_cache

        # Reset cache to ensure fresh request
        reset_update_cache()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "  v999.0.0\n  "

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("app.utils.requests.get", mock_get)

        result = check_for_updates()

        assert result["update_available"] is True
        assert result["latest"] == "v999.0.0"  # Should be stripped

    def test_return_value_structure(self, monkeypatch):
        """Test return value structure: update_available, current, latest, error."""
        from app.utils import check_for_updates

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "v999.0.0"

        mock_get = Mock(return_value=mock_response)
        monkeypatch.setattr("app.utils.requests.get", mock_get)

        result = check_for_updates()

        # Verify structure
        assert "update_available" in result
        assert "current" in result
        assert "latest" in result
        assert isinstance(result["update_available"], bool)
        assert isinstance(result["current"], str)
        assert isinstance(result["latest"], str)


class TestGetUnitPreference:
    """Tests for get_unit_preference() function with real database."""

    def test_returns_imperial_when_appsettings_exists_with_imperial(self, db_session):
        """Test returns 'imperial' when AppSettings exists with imperial."""
        from app.utils import get_unit_preference

        # Clear any existing settings
        AppSettings.query.delete()
        db_session.commit()

        # Create settings with imperial
        settings = AppSettings()
        settings.unit_preference = "imperial"
        db_session.add(settings)
        db_session.commit()

        result = get_unit_preference()
        assert result == "imperial"

    def test_returns_metric_when_appsettings_exists_with_metric(self, db_session):
        """Test returns 'metric' when AppSettings exists with metric."""
        from app.utils import get_unit_preference

        # Clear any existing settings
        AppSettings.query.delete()
        db_session.commit()

        # Create settings with metric
        settings = AppSettings()
        settings.unit_preference = "metric"
        db_session.add(settings)
        db_session.commit()

        result = get_unit_preference()
        assert result == "metric"

    def test_returns_imperial_when_appsettings_is_none(self, db_session):
        """Test returns 'imperial' when AppSettings is None."""
        from app.utils import get_unit_preference

        # Clear any existing settings
        AppSettings.query.delete()
        db_session.commit()

        # Verify no settings exist
        assert AppSettings.query.first() is None

        result = get_unit_preference()
        assert result == "imperial"

    def test_returns_imperial_when_unit_preference_is_none(self, db_session):
        """Test returns 'imperial' when AppSettings.unit_preference is None."""
        from app.utils import get_unit_preference

        # Clear any existing settings
        AppSettings.query.delete()
        db_session.commit()

        # Create settings with None unit_preference
        settings = AppSettings()
        settings.unit_preference = None
        db_session.add(settings)
        db_session.commit()

        result = get_unit_preference()
        assert result == "imperial"

    def test_handles_programming_error(self, db_session, monkeypatch):
        """Test handles ProgrammingError (missing column scenario)."""
        from app.utils import get_unit_preference

        # Mock AppSettings.query to raise ProgrammingError
        def mock_query_first():
            raise ProgrammingError(
                "column unit_preference does not exist", None, Exception("mock error")
            )

        mock_query = Mock()
        mock_query.first = mock_query_first
        monkeypatch.setattr("app.models.AppSettings.query", mock_query)

        # The function should catch ProgrammingError and return 'imperial' as fallback
        result = get_unit_preference()
        assert result == "imperial"

    def test_programming_error_recovery_alter_table(self, db_session, monkeypatch):
        """Test ProgrammingError recovery: ALTER TABLE attempt."""
        from app.utils import get_unit_preference

        # This test verifies that ProgrammingError is caught and handled
        # The actual ALTER TABLE logic is tested indirectly by verifying
        # the function doesn't crash and returns a fallback value

        call_count = [0]

        def mock_query_first():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ProgrammingError(
                    "column unit_preference does not exist", None, Exception("mock error")
                )
            # Second call would return settings after ALTER, but we test fallback
            return None

        mock_query = Mock()
        mock_query.first = mock_query_first
        monkeypatch.setattr("app.models.AppSettings.query", mock_query)

        # The function should catch the error and return 'imperial' as fallback
        result = get_unit_preference()
        assert result == "imperial"

    def test_handles_general_exception(self, db_session, monkeypatch):
        """Test handles general Exception (fallback to imperial)."""
        from app.utils import get_unit_preference

        # Mock AppSettings.query to raise general Exception
        def mock_query_first():
            raise Exception("Unexpected error")

        mock_query = Mock()
        mock_query.first = mock_query_first
        monkeypatch.setattr("app.models.AppSettings.query", mock_query)

        result = get_unit_preference()
        assert result == "imperial"

    def test_local_import_of_appsettings_works(self, db_session):
        """Test local import of AppSettings works correctly."""
        from app.utils import get_unit_preference

        # Clear any existing settings
        AppSettings.query.delete()
        db_session.commit()

        # Create settings
        settings = AppSettings()
        settings.unit_preference = "metric"
        db_session.add(settings)
        db_session.commit()

        # This tests that the local import in get_unit_preference works
        result = get_unit_preference()
        assert result == "metric"


class TestIsMetric:
    """Tests for is_metric() function."""

    def test_returns_true_when_get_unit_preference_returns_metric(self, db_session, monkeypatch):
        """Test returns True when get_unit_preference() returns 'metric'."""
        from app.utils import is_metric

        # Mock get_unit_preference to return 'metric'
        monkeypatch.setattr("app.utils.get_unit_preference", lambda: "metric")

        result = is_metric()
        assert result is True

    def test_returns_false_when_get_unit_preference_returns_imperial(self, db_session, monkeypatch):
        """Test returns False when get_unit_preference() returns 'imperial'."""
        from app.utils import is_metric

        # Mock get_unit_preference to return 'imperial'
        monkeypatch.setattr("app.utils.get_unit_preference", lambda: "imperial")

        result = is_metric()
        assert result is False


class TestReadImportStatusFile:
    """Tests for read_import_status_file() function."""

    def test_returns_dict_when_file_exists_with_valid_json(self, app, tmp_path, monkeypatch):
        """Test returns dict when file exists with valid JSON."""
        from app.utils import read_import_status_file

        # Create test file
        test_file = tmp_path / "import_status.json"
        test_file.write_text('{"status": "completed", "count": 42}')

        # Mock current_app.instance_path
        monkeypatch.setattr("flask.current_app", Mock(instance_path=str(tmp_path)))

        result = read_import_status_file()

        assert result is not None
        assert result["status"] == "completed"
        assert result["count"] == 42

    def test_returns_none_when_file_does_not_exist(self, app, tmp_path, monkeypatch):
        """Test returns None when file does not exist."""
        from app.utils import read_import_status_file

        # Mock current_app.instance_path to empty directory
        monkeypatch.setattr("flask.current_app", Mock(instance_path=str(tmp_path)))

        result = read_import_status_file()
        assert result is None

    def test_returns_none_when_file_contains_invalid_json(self, app, tmp_path, monkeypatch):
        """Test returns None when file contains invalid JSON."""
        from app.utils import read_import_status_file

        # Create test file with invalid JSON
        test_file = tmp_path / "import_status.json"
        test_file.write_text('{"invalid": json}')

        # Mock current_app.instance_path
        monkeypatch.setattr("flask.current_app", Mock(instance_path=str(tmp_path)))

        result = read_import_status_file()
        assert result is None

    def test_returns_none_on_file_read_exception(self, app, tmp_path, monkeypatch):
        """Test returns None on file read exception."""
        from pathlib import Path as PathlibPath

        from app.utils import read_import_status_file

        # Create test file
        test_file = tmp_path / "import_status.json"
        test_file.write_text('{"status": "ok"}')

        # Mock Path.read_text to raise exception
        original_read_text = PathlibPath.read_text

        def mock_read_text(self, *args, **kwargs):
            if "import_status.json" in str(self):
                raise OSError("Cannot read file")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr("pathlib.Path.read_text", mock_read_text)
        monkeypatch.setattr("flask.current_app", Mock(instance_path=str(tmp_path)))

        result = read_import_status_file()
        assert result is None

    def test_uses_current_app_instance_path_correctly(self, app, tmp_path, monkeypatch):
        """Test uses current_app.instance_path correctly."""

        from app.utils import read_import_status_file

        # Create test file in tmp_path
        test_file = tmp_path / "import_status.json"
        test_file.write_text('{"test": true}')

        # Mock current_app.instance_path
        mock_app = Mock(instance_path=str(tmp_path))
        monkeypatch.setattr("flask.current_app", mock_app)

        result = read_import_status_file()

        assert result is not None
        assert result["test"] is True


class TestGallonsToLiters:
    """Tests for gallons_to_liters() function."""

    def test_1_gallon_equals_3_78541_liters(self):
        """Test 1 gallon = 3.78541 liters."""
        from app.utils import gallons_to_liters

        result = gallons_to_liters(1)
        assert abs(result - 3.78541) < 0.0001

    def test_0_gallons_equals_0_liters(self):
        """Test 0 gallons = 0 liters."""
        from app.utils import gallons_to_liters

        assert gallons_to_liters(0) == 0

    def test_none_input_returns_none(self):
        """Test None input returns None."""
        from app.utils import gallons_to_liters

        assert gallons_to_liters(None) is None

    def test_negative_value(self):
        """Test negative value."""
        from app.utils import gallons_to_liters

        result = gallons_to_liters(-5)
        assert abs(result - (-18.92705)) < 0.0001

    def test_fractional_gallons(self):
        """Test fractional gallons."""
        from app.utils import gallons_to_liters

        result = gallons_to_liters(0.5)
        assert abs(result - 1.892705) < 0.0001


class TestLitersToGallons:
    """Tests for liters_to_gallons() function."""

    def test_3_78541_liters_equals_1_gallon(self):
        """Test 3.78541 liters = 1 gallon."""
        from app.utils import liters_to_gallons

        result = liters_to_gallons(3.78541)
        assert abs(result - 1) < 0.0001

    def test_0_liters_equals_0_gallons(self):
        """Test 0 liters = 0 gallons."""
        from app.utils import liters_to_gallons

        assert liters_to_gallons(0) == 0

    def test_none_input_returns_none(self):
        """Test None input returns None."""
        from app.utils import liters_to_gallons

        assert liters_to_gallons(None) is None

    def test_negative_value(self):
        """Test negative value."""
        from app.utils import liters_to_gallons

        result = liters_to_gallons(-10)
        assert result < 0

    def test_fractional_liters(self):
        """Test fractional liters."""
        from app.utils import liters_to_gallons

        result = liters_to_gallons(1.892705)
        assert abs(result - 0.5) < 0.0001


class TestFToC:
    """Tests for f_to_c() function."""

    def test_32_fahrenheit_equals_0_celsius(self):
        """Test 32°F = 0°C."""
        from app.utils import f_to_c

        result = f_to_c(32)
        assert abs(result - 0) < 0.01

    def test_212_fahrenheit_equals_100_celsius(self):
        """Test 212°F = 100°C."""
        from app.utils import f_to_c

        result = f_to_c(212)
        assert abs(result - 100) < 0.01

    def test_0_fahrenheit_equals_approx_minus_17_78_celsius(self):
        """Test 0°F = -17.78°C (approx)."""
        from app.utils import f_to_c

        result = f_to_c(0)
        assert abs(result - (-17.78)) < 0.01

    def test_none_input_returns_none(self):
        """Test None input returns None."""
        from app.utils import f_to_c

        assert f_to_c(None) is None

    def test_negative_fahrenheit(self):
        """Test negative Fahrenheit."""
        from app.utils import f_to_c

        result = f_to_c(-40)
        assert abs(result - (-40)) < 0.01  # -40°F = -40°C


class TestCToF:
    """Tests for c_to_f() function."""

    def test_0_celsius_equals_32_fahrenheit(self):
        """Test 0°C = 32°F."""
        from app.utils import c_to_f

        result = c_to_f(0)
        assert abs(result - 32) < 0.01

    def test_100_celsius_equals_212_fahrenheit(self):
        """Test 100°C = 212°F."""
        from app.utils import c_to_f

        result = c_to_f(100)
        assert abs(result - 212) < 0.01

    def test_minus_40_celsius_equals_minus_40_fahrenheit(self):
        """Test -40°C = -40°F."""
        from app.utils import c_to_f

        result = c_to_f(-40)
        assert abs(result - (-40)) < 0.01

    def test_none_input_returns_none(self):
        """Test None input returns None."""
        from app.utils import c_to_f

        assert c_to_f(None) is None

    def test_negative_celsius(self):
        """Test negative Celsius."""
        from app.utils import c_to_f

        result = c_to_f(-10)
        assert result < 32  # Should be below freezing


class TestEdgeCases:
    """Edge cases and error handling tests for all functions."""

    def test_is_strong_password_with_unicode(self):
        """Test is_strong_password with unicode characters."""
        from app.utils import is_strong_password

        # Unicode symbols should count as symbols
        assert is_strong_password("Passwörd1!")

    def test_is_strong_password_with_spaces(self):
        """Test is_strong_password with spaces."""
        from app.utils import is_strong_password

        # Spaces count as symbols
        assert is_strong_password("Pass word1")

    def test_check_for_updates_with_connection_error(self, monkeypatch):
        """Test check_for_updates with connection error."""
        from app.utils import check_for_updates, reset_update_cache

        # Reset cache to ensure fresh request
        reset_update_cache()

        def mock_get_connection_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError("No network")

        monkeypatch.setattr("app.utils.requests.get", mock_get_connection_error)

        result = check_for_updates()
        assert result["update_available"] is False
        assert "error" in result

    def test_gallons_to_liters_with_string_input(self):
        """Test gallons_to_liters with string input (should fail or handle)."""
        from app.utils import gallons_to_liters

        # This will raise TypeError, which is expected behavior
        with pytest.raises(TypeError):
            gallons_to_liters("5")

    def test_f_to_c_with_string_input(self):
        """Test f_to_c with string input (should fail or handle)."""
        from app.utils import f_to_c

        # This will raise TypeError, which is expected behavior
        with pytest.raises(TypeError):
            f_to_c("32")


class TestUtilsCoverageGaps:
    """Tests for remaining coverage gaps in app/utils.py."""

    def test_get_unit_preference_programming_error_recovery_lines_66_69(
        self, db_session, monkeypatch
    ):
        """Test lines 66-69: ProgrammingError recovery path adds column and retries."""
        from sqlalchemy.exc import ProgrammingError

        from app.utils import get_unit_preference

        # Mock AppSettings.query.first() to raise ProgrammingError then succeed
        call_count = [0]

        def mock_first():
            call_count[0] += 1
            if call_count[0] == 1:
                # First call raises ProgrammingError
                raise ProgrammingError(
                    "column unit_preference does not exist", {}, Exception("mock error")
                )
            # Second call returns settings with unit_preference
            settings = MagicMock()
            settings.unit_preference = "metric"
            return settings

        mock_query = MagicMock()
        mock_query.first = mock_first

        from app import models

        monkeypatch.setattr(models.AppSettings, "query", mock_query)

        # Mock db.session.execute and commit
        monkeypatch.setattr(db_session, "execute", MagicMock())
        monkeypatch.setattr(db_session, "commit", MagicMock())

        result = get_unit_preference()

        # Should return 'metric' after recovery
        assert result == "metric"
        # Should have called first() twice (once before ALTER, once after)
        assert call_count[0] == 2
