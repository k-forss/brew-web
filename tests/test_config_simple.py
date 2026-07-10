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


def test_version_equals_1_4_0(monkeypatch):
    """Test VERSION equals "1.4.0"."""
    monkeypatch.setenv("SECRET_KEY", "test-key")
    import config

    assert config.Config.VERSION == "1.4.0"


def test_version_is_string(monkeypatch):
    """Test VERSION is a string."""
    monkeypatch.setenv("SECRET_KEY", "test-key")
    import config

    assert isinstance(config.Config.VERSION, str)


def test_secret_key_reads_from_environment(monkeypatch):
    """Test reads from os.environ.get('SECRET_KEY')."""
    monkeypatch.setenv("SECRET_KEY", "my-secure-test-key-123")

    import config

    importlib.reload(config)

    assert config.Config.SECRET_KEY == "my-secure-test-key-123"


def test_missing_secret_key_raises_error(monkeypatch):
    """Test raises RuntimeError when SECRET_KEY not set."""
    monkeypatch.delenv("SECRET_KEY", raising=False)

    import pytest

    import config

    with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
        importlib.reload(config)


def test_placeholder_secret_key_raises_error(monkeypatch):
    """Test raises RuntimeError when SECRET_KEY = 'changeme-in-production'."""
    monkeypatch.setenv("SECRET_KEY", "changeme-in-production")

    import pytest

    import config

    with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
        importlib.reload(config)


def test_valid_secret_key_accepted(monkeypatch):
    """Test accepts valid SECRET_KEY from environment."""
    monkeypatch.setenv("SECRET_KEY", "a-very-secure-random-key-xyz789")

    import config

    importlib.reload(config)

    assert config.Config.SECRET_KEY == "a-very-secure-random-key-xyz789"


def test_empty_secret_key_raises_error(monkeypatch):
    """Test empty string SECRET_KEY (should fail)."""
    monkeypatch.setenv("SECRET_KEY", "")

    import pytest

    import config

    with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
        importlib.reload(config)


def test_database_url_reads_from_environment(monkeypatch):
    """Test reads from os.environ.get('DATABASE_URL')."""
    monkeypatch.setenv("SECRET_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/customdb")

    import config

    importlib.reload(config)

    assert config.Config.SQLALCHEMY_DATABASE_URI == "postgresql://user:pass@localhost:5432/customdb"


def test_database_url_defaults(monkeypatch):
    """Test defaults to 'postgresql://brewuser:brewpass@db:5432/brewweb'."""
    monkeypatch.setenv("SECRET_KEY", "test-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import config

    importlib.reload(config)

    assert config.Config.SQLALCHEMY_DATABASE_URI == "postgresql://brewuser:brewpass@db:5432/brewweb"


def test_sqlalchemy_track_modifications_is_false(monkeypatch):
    """Test equals False."""
    monkeypatch.setenv("SECRET_KEY", "test-key")
    import config

    assert config.Config.SQLALCHEMY_TRACK_MODIFICATIONS is False


def test_wtf_csrf_enabled_is_true(monkeypatch):
    """Test equals True."""
    monkeypatch.setenv("SECRET_KEY", "test-key")
    import config

    assert config.Config.WTF_CSRF_ENABLED is True


def test_config_has_all_attributes(monkeypatch):
    """Test Config class has all required attributes."""
    monkeypatch.setenv("SECRET_KEY", "test-key")
    import config

    assert hasattr(config.Config, "VERSION")
    assert hasattr(config.Config, "SECRET_KEY")
    assert hasattr(config.Config, "SQLALCHEMY_DATABASE_URI")
    assert hasattr(config.Config, "SQLALCHEMY_TRACK_MODIFICATIONS")
    assert hasattr(config.Config, "WTF_CSRF_ENABLED")
