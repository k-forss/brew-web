"""Tests for wsgi.py application entry point."""

from app import create_app


def test_wsgi_app_can_be_created():
    """Test that the WSGI app can be imported and created."""
    from wsgi import app

    assert app is not None
    assert isinstance(app, type(create_app()))
