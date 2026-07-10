"""
Test suite for brew-web Flask application.

This package contains all unit and integration tests for the brew-web application.
Tests are organized by module/component:

- test_app_init.py: Application factory and configuration
- test_models.py: SQLAlchemy models
- test_auth.py: Authentication routes
- test_decorators.py: Route decorators
- test_utils.py: Utility functions
- test_routes*.py: Route handlers by feature
- test_config.py: Configuration validation
- test_seed_yeasts.py: Yeast seeding

Run tests with:
    pytest
    ./scripts/run-tests.sh
    ./scripts/coverage-report.sh
"""
