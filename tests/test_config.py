"""
Comprehensive unit tests for Config class in config.py.

Test Strategy:
- Uses monkeypatch for environment variable testing
- Tests all Config attributes
- Tests error cases (missing/invalid SECRET_KEY)
- No database session needed (pure configuration tests)
- **CRITICAL**: All tests use monkeypatch to avoid polluting environment
- **CRITICAL**: Tests that reload config module are isolated via fixture

Config Attributes Tested:
- VERSION: Hardcoded version string
- SECRET_KEY: Required environment variable with validation
- SQLALCHEMY_DATABASE_URI: Optional with default fallback
- SQLALCHEMY_TRACK_MODIFICATIONS: Disabled flag
- WTF_CSRF_ENABLED: CSRF protection flag
"""

import importlib
import sys

import pytest


@pytest.fixture(autouse=True)
def reset_config_module():
    """Reset config module state after each test.

    This fixture ensures that tests using importlib.reload(config)
    don't pollute subsequent tests. It runs automatically for all
    tests in this file.

    Yields:
        None
    """
    yield
    # After test completes, remove config from sys.modules if it exists
    # This forces a fresh import in the next test
    if "config" in sys.modules:
        del sys.modules["config"]


class TestConfigVersion:
    """Tests for Config.VERSION attribute."""

    def test_version_equals_1_4_0(self, monkeypatch):
        """Test VERSION equals "1.4.0"."""
        # Set a valid SECRET_KEY to allow Config import
        monkeypatch.setenv("SECRET_KEY", "test-key")

        # Import config directly without triggering app init
        import config

        assert config.Config.VERSION == "1.4.0"

    def test_version_is_string(self, monkeypatch):
        """Test VERSION is a string."""
        monkeypatch.setenv("SECRET_KEY", "test-key")

        import config

        assert isinstance(config.Config.VERSION, str)


class TestConfigSecretKey:
    """Tests for Config.SECRET_KEY attribute."""

    def test_reads_from_os_environ_get_secret_key(self, monkeypatch):
        """Test reads from os.environ.get('SECRET_KEY')."""
        monkeypatch.setenv("SECRET_KEY", "my-secure-test-key-123")

        # Need to reload config to pick up new environment
        import config

        importlib.reload(config)

        assert config.Config.SECRET_KEY == "my-secure-test-key-123"

    def test_raises_runtime_error_when_secret_key_not_set(self, monkeypatch):
        """Test raises RuntimeError when SECRET_KEY not set."""
        # Remove SECRET_KEY from environment
        monkeypatch.delenv("SECRET_KEY", raising=False)

        # Import should raise RuntimeError
        import config

        with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
            importlib.reload(config)

    def test_raises_runtime_error_when_secret_key_is_changeme_placeholder(self, monkeypatch):
        """Test raises RuntimeError when SECRET_KEY = 'changeme-in-production'."""
        monkeypatch.setenv("SECRET_KEY", "changeme-in-production")

        import config

        with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
            importlib.reload(config)

    def test_accepts_valid_secret_key_from_environment(self, monkeypatch):
        """Test accepts valid SECRET_KEY from environment."""
        monkeypatch.setenv("SECRET_KEY", "a-very-secure-random-key-xyz789")

        import config

        importlib.reload(config)

        assert config.Config.SECRET_KEY == "a-very-secure-random-key-xyz789"

    def test_empty_string_secret_key_raises_error(self, monkeypatch):
        """Test empty string SECRET_KEY (should fail)."""
        monkeypatch.setenv("SECRET_KEY", "")

        import config

        with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
            importlib.reload(config)

    def test_whitespace_only_secret_key_is_accepted(self, monkeypatch):
        """Test whitespace-only SECRET_KEY (currently accepted, may need validation)."""
        monkeypatch.setenv("SECRET_KEY", "   ")

        import config

        importlib.reload(config)

        # Currently whitespace-only is accepted (not empty string check)
        assert config.Config.SECRET_KEY == "   "


class TestConfigDatabaseURI:
    """Tests for Config.SQLALCHEMY_DATABASE_URI attribute."""

    def test_reads_from_os_environ_get_database_url(self, monkeypatch):
        """Test reads from os.environ.get('DATABASE_URL')."""
        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/customdb")

        import config

        importlib.reload(config)

        assert (
            config.Config.SQLALCHEMY_DATABASE_URI
            == "postgresql://user:pass@localhost:5432/customdb"
        )

    def test_defaults_to_docker_compose_postgresql(self, monkeypatch):
        """Test defaults to 'postgresql://brewuser:brewpass@db:5432/brewweb'."""
        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        import config

        importlib.reload(config)

        assert (
            config.Config.SQLALCHEMY_DATABASE_URI
            == "postgresql://brewuser:brewpass@db:5432/brewweb"
        )

    def test_uses_environment_value_when_set(self, monkeypatch):
        """Test uses environment value when set."""
        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")

        import config

        importlib.reload(config)

        assert config.Config.SQLALCHEMY_DATABASE_URI == "sqlite:///test.db"

    def test_default_uri_contains_brewuser(self, monkeypatch):
        """Test default URI contains 'brewuser' username."""
        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        import config

        importlib.reload(config)

        assert "brewuser" in config.Config.SQLALCHEMY_DATABASE_URI

    def test_default_uri_contains_db_host(self, monkeypatch):
        """Test default URI contains 'db' host (Docker Compose service name)."""
        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        import config

        importlib.reload(config)

        assert "@db:" in config.Config.SQLALCHEMY_DATABASE_URI


class TestConfigSQLAlchemyTrackModifications:
    """Tests for Config.SQLALCHEMY_TRACK_MODIFICATIONS attribute."""

    def test_equals_false(self, monkeypatch):
        """Test equals False."""
        monkeypatch.setenv("SECRET_KEY", "test-key")

        import config

        assert config.Config.SQLALCHEMY_TRACK_MODIFICATIONS is False

    def test_is_boolean(self, monkeypatch):
        """Test is a boolean value."""
        monkeypatch.setenv("SECRET_KEY", "test-key")

        import config

        assert isinstance(config.Config.SQLALCHEMY_TRACK_MODIFICATIONS, bool)


class TestConfigWTFCSRFEnabled:
    """Tests for Config.WTF_CSRF_ENABLED attribute."""

    def test_equals_true(self, monkeypatch):
        """Test equals True."""
        monkeypatch.setenv("SECRET_KEY", "test-key")

        import config

        assert config.Config.WTF_CSRF_ENABLED is True

    def test_is_boolean(self, monkeypatch):
        """Test is a boolean value."""
        monkeypatch.setenv("SECRET_KEY", "test-key")

        import config

        assert isinstance(config.Config.WTF_CSRF_ENABLED, bool)


class TestConfigEdgeCases:
    """Edge cases and error handling tests."""

    def test_none_secret_key_raises_error(self, monkeypatch):
        """Test None SECRET_KEY (should fail)."""
        # Setting to None in environment actually sets it to string 'None'
        # To test None, we need to delete it
        monkeypatch.delenv("SECRET_KEY", raising=False)

        import config

        with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
            importlib.reload(config)

    def test_config_has_all_required_attributes(self, monkeypatch):
        """Test Config class has all required attributes."""
        monkeypatch.setenv("SECRET_KEY", "test-key")

        import config

        importlib.reload(config)

        assert hasattr(config.Config, "VERSION")
        assert hasattr(config.Config, "SECRET_KEY")
        assert hasattr(config.Config, "SQLALCHEMY_DATABASE_URI")
        assert hasattr(config.Config, "SQLALCHEMY_TRACK_MODIFICATIONS")
        assert hasattr(config.Config, "WTF_CSRF_ENABLED")

    def test_config_attributes_are_class_attributes_not_instance(self, monkeypatch):
        """Test Config attributes are class attributes."""
        monkeypatch.setenv("SECRET_KEY", "test-key")

        import config

        importlib.reload(config)

        # Should be accessible on the class itself, not just instances
        assert config.Config.VERSION == "1.4.0"
        assert config.Config.SECRET_KEY == "test-key"
        assert config.Config.SQLALCHEMY_TRACK_MODIFICATIONS is False
        assert config.Config.WTF_CSRF_ENABLED is True

    def test_multiple_config_reloads_with_different_keys(self, monkeypatch):
        """Test multiple config reloads with different SECRET_KEY values."""
        import config

        # First load
        monkeypatch.setenv("SECRET_KEY", "key-one")
        importlib.reload(config)
        assert config.Config.SECRET_KEY == "key-one"

        # Second load with different key
        monkeypatch.setenv("SECRET_KEY", "key-two")
        importlib.reload(config)
        assert config.Config.SECRET_KEY == "key-two"

        # Third load with invalid key
        monkeypatch.setenv("SECRET_KEY", "changeme-in-production")
        with pytest.raises(RuntimeError):
            importlib.reload(config)
