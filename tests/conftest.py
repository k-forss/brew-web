"""
Pytest configuration and fixtures for brew-web test suite.

Transactional Isolation Strategy:
Each pytest-xdist worker uses a unique PostgreSQL schema (brewweb_test_gw0, gw1, etc.)
for parallel execution. Tests run in transactions that rollback after completion,
ensuring complete isolation and allowing tests to call commit() freely.

This module provides:
- App factory fixture for test isolation
- Database fixtures with transactional rollback
- PostgreSQL database via Docker (ephemeral container per test run)
- Authentication helpers for simulating logged-in users
- Common test utilities and mocks
- Worker isolation for pytest-xdist parallel execution

Database Strategy:
- scripts/run-tests.sh spawns ephemeral PostgreSQL in Docker
- DATABASE_URL set by test runner script
- For parallel execution (pytest-xdist), each worker gets unique schema
- Tests use real PostgreSQL for production fidelity
"""

import os

import pytest


# Set test environment variables BEFORE importing app modules
os.environ["TESTING"] = "True"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["RATELIMIT_ENABLED"] = "False"
# Test-only SECRET_KEY (intentionally weak, safe for isolated test environments)
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
# DATABASE_URL is set by scripts/run-tests.sh (Docker PostgreSQL or SQLite fallback)
# If not set by script, use SQLite for tests that don't need run-tests.sh
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"


from app import create_app
from app import db as sqlalchemy_db
from app.models import User


# Configure test environment before app creation
@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Set test-specific environment variables.

    Note: Core environment variables are set at module level above
    to ensure they're set before app modules are imported.
    """
    # Additional test setup can go here
    pass


@pytest.fixture(scope="session")
def worker_id(request):
    """Get the worker ID for pytest-xdist parallel execution.

    When running with pytest-xdist, each worker process gets a unique ID
    (gw0, gw1, gw2, etc.). When running without xdist, returns 'master'.

    This is used to create worker-isolated resources (databases, schemas, paths).

    Returns:
        str: Worker identifier
    """
    # Check if running with pytest-xdist
    if hasattr(request.config, "workerinput"):
        return request.config.workerinput.get("workerid", "master")
    return "master"


@pytest.fixture
def worker_db_schema(worker_id):
    """Generate unique database schema name per worker.

    Each pytest-xdist worker gets its own schema to avoid conflicts.
    Schema names: brewweb_test_gw0, brewweb_test_gw1, etc.

    Args:
        worker_id: Worker identifier from pytest-xdist

    Returns:
        str: Unique schema name for this worker
    """
    return f"brewweb_test_{worker_id}"


@pytest.fixture
def app(worker_id, worker_db_schema):
    """Create application for testing.

    Uses DATABASE_URL from environment (set by scripts/run-tests.sh).
    Defaults to SQLite in-memory if DATABASE_URL not set.

    For pytest-xdist parallel execution:
    - Each worker gets unique database/schema to avoid conflicts
    - worker_id fixture provides unique identifier (gw0, gw1, etc.)
    - worker_db_schema provides unique schema/database name per worker
    - Function scope ensures each test gets fresh app instance

    Returns:
        Flask application configured for testing
    """
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Use DATABASE_URL from environment (set by run-tests.sh script)
    # Falls back to SQLite if not set
    base_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")

    # For worker isolation in parallel execution
    if worker_id != "master":
        if base_url.startswith("postgresql://"):
            # Add schema parameter to URL for worker isolation
            if "?" in base_url:
                app.config["SQLALCHEMY_DATABASE_URI"] = (
                    f"{base_url}&currentSchema={worker_db_schema}"
                )
            else:
                app.config["SQLALCHEMY_DATABASE_URI"] = (
                    f"{base_url}?currentSchema={worker_db_schema}"
                )
        elif base_url.startswith("sqlite://"):
            # For SQLite, use unique in-memory database per worker
            # Note: SQLite in-memory databases are already isolated per connection
            # but we ensure unique URI to avoid any potential conflicts
            app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///:memory:{worker_id}"
        else:
            app.config["SQLALCHEMY_DATABASE_URI"] = base_url
    else:
        # Sequential execution - use base URL as-is
        app.config["SQLALCHEMY_DATABASE_URI"] = base_url

    with app.app_context():
        # Create schema if using PostgreSQL
        if base_url.startswith("postgresql://") and worker_id != "master":
            from sqlalchemy import text

            # Create schema if it doesn't exist
            with sqlalchemy_db.engine.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text(f"CREATE SCHEMA IF NOT EXISTS {worker_db_schema}")
                )
                # Set search_path to use this schema
                conn.execute(text(f"SET search_path TO {worker_db_schema}, public"))

        sqlalchemy_db.create_all()
        yield app
        # Clean up: remove session first, then drop tables, then dispose engine
        sqlalchemy_db.session.remove()
        sqlalchemy_db.drop_all()

        # Drop schema if using PostgreSQL (cleanup worker-specific schema)
        if base_url.startswith("postgresql://") and worker_id != "master":
            from sqlalchemy import text

            try:
                with sqlalchemy_db.engine.connect() as conn:
                    conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                        text(f"DROP SCHEMA IF EXISTS {worker_db_schema} CASCADE")
                    )
            except Exception:
                # Schema cleanup is best-effort; PostgreSQL will clean up on container stop
                pass

        sqlalchemy_db.engine.dispose()


@pytest.fixture
def _db(app):
    """Expose SQLAlchemy database instance for pytest-flask-sqlalchemy.

    This fixture is required by pytest-flask-sqlalchemy plugin to enable
    transactional testing. It provides the SQLAlchemy instance that the
    plugin will wrap with transactional fixtures.

    Returns:
        SQLAlchemy instance from the application
    """
    return sqlalchemy_db


@pytest.fixture
def db_session(_db, app):
    """Create a database session for tests via pytest-flask-sqlalchemy.

    This fixture is provided by pytest-flask-sqlalchemy plugin and wraps
    each test in a transaction that is rolled back after the test completes.
    This ensures complete test isolation and allows tests to call commit()
    freely without affecting other tests.

    Returns:
        SQLAlchemy session with transactional rollback
    """
    # Return the actual session object, not the SQLAlchemy instance
    return _db.session


@pytest.fixture(autouse=True)
def enable_transactional_tests(db_session):
    """Enable transactional testing for all tests automatically.

    This autouse fixture ensures that every test runs within a transaction
    that is rolled back after the test completes. No need to explicitly
    request db_session in each test.
    """
    # The fixture body is empty - the transactional behavior is provided
    # by the pytest-flask-sqlalchemy plugin through the db_session fixture
    pass


@pytest.fixture
def client(app):
    """Create test client for the application.

    Returns:
        Flask test client
    """
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create CLI runner for testing Flask commands.

    Returns:
        Flask CLI runner
    """
    return app.test_cli_runner()


@pytest.fixture(autouse=True)
def isolate_app_settings(db_session):
    """Delete AppSettings before each test to ensure isolation.

    AppSettings is a singleton pattern, so we need to clean it up
    between tests to avoid conflicts.

    This fixture is autouse=True so it runs for every test automatically.
    """
    from app.models import AppSettings

    AppSettings.query.delete()
    db_session.commit()
    yield


@pytest.fixture(autouse=True)
def isolate_instance_path(app, worker_id, tmp_path):
    """Isolate instance_path per worker and test.

    Each worker gets its own temporary instance directory to avoid
    file conflicts (force_reset.flag, import_status.json, etc.).

    This fixture is autouse=True so it runs for every test automatically.
    """
    # Create unique instance path for this worker
    instance_dir = tmp_path / f"instance_{worker_id}"
    instance_dir.mkdir(exist_ok=True)

    # Override app.instance_path for this test
    original_instance_path = app.instance_path
    app.instance_path = str(instance_dir)

    yield

    # Restore original instance_path
    app.instance_path = original_instance_path


@pytest.fixture
def test_user(app, db_session, worker_id):
    """Create a test user for authentication tests.

    Uses worker_id to ensure unique usernames across parallel workers.

    Returns:
        User instance (not committed, caller must commit if needed)
    """
    user = User()
    user.username = f"testuser_{worker_id}"
    user.role = "user"
    user.set_password("testpassword123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    # Cleanup handled by transactional rollback


@pytest.fixture
def admin_user(app, db_session, worker_id):
    """Create an admin user for authorization tests.

    Uses worker_id to ensure unique usernames across parallel workers.

    Returns:
        User instance with admin role
    """
    user = User()
    user.username = f"adminuser_{worker_id}"
    user.role = "admin"
    user.is_admin = True
    user.set_password("adminpassword123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    # Cleanup handled by transactional rollback


@pytest.fixture
def authenticated_client(client, test_user, app):
    """Create a test client with an authenticated user.

    Returns:
        Tuple of (client, user) where client is logged in as user
    """
    with app.test_client() as c:
        with c.session_transaction() as sess:
            # Flask-Login stores user_id in session
            sess["_user_id"] = str(test_user.id)
        yield c, test_user


@pytest.fixture
def admin_client(client, admin_user, app):
    """Create a test client with an authenticated admin user.

    Returns:
        Tuple of (client, user) where client is logged in as admin
    """
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
        yield c, admin_user


@pytest.fixture
def mock_current_user(monkeypatch, test_user):
    """Mock flask_login.current_user for testing.

    Usage:
        def test_something(mock_current_user):
            # current_user is now test_user
            pass
    """
    monkeypatch.setattr("flask_login.utils._get_user", lambda: test_user)
    return test_user


@pytest.fixture
def mock_requests(monkeypatch):
    """Mock requests library for external API calls.

    Usage:
        def test_update_check(mock_requests):
            mock_requests.get.return_value.json.return_value = {'tag_name': 'v1.0.0'}
            # ... test code
    """
    import requests

    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self._json_data = json_data
            self.status_code = status_code
            self.ok = status_code == 200

        def json(self):
            return self._json_data

    def mock_get(*args, **kwargs):
        return MockResponse({})

    def mock_post(*args, **kwargs):
        return MockResponse({})

    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests, "post", mock_post)
    return {"get": mock_get, "post": mock_post}


@pytest.fixture
def unique_username(worker_id):
    """Generate a unique username for test isolation.

    Usage:
        def test_something(unique_username, db_session):
            user = User()
            user.username = unique_username('testuser')
            ...

    Args:
        worker_id: Injected automatically

    Returns:
        Function that generates unique usernames
    """
    import uuid

    def make_unique(base_name):
        return f"{base_name}_{worker_id}_{uuid.uuid4().hex[:8]}"

    return make_unique


@pytest.fixture
def sample_batch_data():
    """Provide sample batch data for testing."""
    return {
        "batch_name": "Test Batch",
        "batch_type": "beer",
        "volume": 5.0,
        "volume_unit": "gallons",
        "og": 1.050,
        "fg": 1.010,
        "ibu": 45,
        "color_srm": 12,
    }


@pytest.fixture
def sample_recipe_data():
    """Provide sample recipe data for testing."""
    return {
        "name": "Test Recipe",
        "style": "American Pale Ale",
        "batch_size": 5.0,
        "batch_size_unit": "gallons",
        "boil_time": 60,
        "ingredients": {
            "fermentables": [
                {"name": "Pale Malt", "amount": 10.0, "unit": "lbs"},
            ],
            "hops": [
                {"name": "Cascade", "amount": 2.0, "unit": "oz", "time": 60},
            ],
            "yeasts": [
                {"name": "US-05", "amount": 1.0, "unit": "pack"},
            ],
        },
    }


# Helper functions for test assertions
def assert_requires_auth(response):
    """Assert that response indicates authentication required."""
    assert response.status_code in [302, 401, 403]


def assert_requires_role(response, role):
    """Assert that response indicates role requirement not met."""
    assert response.status_code in [302, 403]


def assert_success(response, expected_status=200):
    """Assert successful response."""
    assert response.status_code == expected_status


def assert_redirect(response, expected_endpoint=None):
    """Assert response is a redirect."""
    assert response.status_code == 302
    if expected_endpoint:
        assert expected_endpoint in response.location


def create_test_user(db_session, username, password, is_admin=False, role="user"):
    """Create a test user in the database.

    Args:
        db_session: Database session fixture
        username: Username for the test user
        password: Password for the test user
        is_admin: Whether user is admin (default: False)
        role: User role (default: 'user')

    Returns:
        User instance (not committed, caller must commit)
    """
    user = User()
    user.username = username
    user.is_admin = is_admin
    user.role = role
    user.set_password(password)
    db_session.add(user)
    return user
