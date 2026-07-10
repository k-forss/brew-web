"""
Unit tests for decorators (app/decorators.py).

Tests cover:
- role_required decorator factory and behavior
- Role matching and access control
- Multiple role support
- Function metadata preservation
- Argument passing through decorator
- Edge cases (empty roles, None roles, case sensitivity)
"""

from unittest.mock import Mock

import pytest

from werkzeug.exceptions import HTTPException

from app.decorators import role_required


class TestRoleRequiredDecorator:
    """Tests for role_required decorator factory and basic functionality."""

    def test_decorator_factory_returns_decorator(self):
        """Test role_required('admin') returns a decorator function."""
        decorator = role_required("admin")
        assert callable(decorator)

    def test_matching_role_allows_execution(self, monkeypatch):
        """Test user with 'admin' role can access admin function."""
        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required("admin")
        def admin_func():
            return "access granted"

        result = admin_func()
        assert result == "access granted"

    def test_non_matching_role_calls_abort(self, monkeypatch):
        """Test user with 'user' role gets 403 on admin function."""
        mock_user = Mock()
        mock_user.role = "user"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required("admin")
        def admin_func():
            return "should not reach here"

        with pytest.raises(HTTPException) as exc_info:
            admin_func()
        assert exc_info.value.code == 403

    def test_multiple_roles_any_match(self, monkeypatch):
        """Test @role_required('admin', 'editor') allows both roles."""
        # Test with admin role
        mock_admin = Mock()
        mock_admin.role = "admin"
        mock_admin.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_admin)

        @role_required("admin", "editor")
        def protected_func():
            return "access granted"

        result = protected_func()
        assert result == "access granted"

        # Test with editor role
        mock_editor = Mock()
        mock_editor.role = "editor"
        mock_editor.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_editor)

        result = protected_func()
        assert result == "access granted"

    def test_unauthenticated_user_403(self, monkeypatch):
        """Test unauthenticated user (no role) gets 403."""
        mock_user = Mock()
        mock_user.role = None
        mock_user.is_authenticated = False
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required("admin")
        def protected_func():
            return "should not reach here"

        with pytest.raises(HTTPException) as exc_info:
            protected_func()
        assert exc_info.value.code == 403

    def test_preserves_function_metadata(self, monkeypatch):
        """Test __name__ and __doc__ preserved via functools.wraps."""
        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required("admin")
        def documented_func():
            """This is the docstring."""
            pass

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is the docstring."

    def test_passes_positional_arguments(self, monkeypatch):
        """Test wrapped function receives *args."""
        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required("admin")
        def func_with_args(a, b, c):
            return a + b + c

        result = func_with_args(1, 2, 3)
        assert result == 6

    def test_passes_keyword_arguments(self, monkeypatch):
        """Test wrapped function receives **kwargs."""
        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required("admin")
        def func_with_kwargs(x, y=10):
            return x * y

        result = func_with_kwargs(5, y=20)
        assert result == 100

    def test_returns_wrapped_function_value(self, monkeypatch):
        """Test decorator returns function's return value."""
        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required("admin")
        def returns_dict():
            return {"status": "ok", "count": 42}

        result = returns_dict()
        assert result == {"status": "ok", "count": 42}


class TestEdgeCases:
    """Edge cases and error handling tests."""

    def test_empty_roles_list_always_403(self, monkeypatch):
        """Test @role_required() with no args always returns 403."""
        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required()
        def protected_func():
            return "should not reach here"

        with pytest.raises(HTTPException) as exc_info:
            protected_func()
        assert exc_info.value.code == 403

    def test_none_role_in_current_user(self, monkeypatch):
        """Test current_user.role = None gets 403."""
        mock_user = Mock()
        mock_user.role = None
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required("admin")
        def protected_func():
            return "should not reach here"

        with pytest.raises(HTTPException) as exc_info:
            protected_func()
        assert exc_info.value.code == 403

    def test_empty_string_role(self, monkeypatch):
        """Test current_user.role = '' gets 403."""
        mock_user = Mock()
        mock_user.role = ""
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required("admin")
        def protected_func():
            return "should not reach here"

        with pytest.raises(HTTPException) as exc_info:
            protected_func()
        assert exc_info.value.code == 403

    def test_case_sensitive_role_matching(self, monkeypatch):
        """Test 'Admin' != 'admin' (case sensitive)."""
        mock_user = Mock()
        mock_user.role = "Admin"
        mock_user.is_authenticated = True
        monkeypatch.setattr("app.decorators.current_user", mock_user)

        @role_required("admin")
        def protected_func():
            return "should not reach here"

        with pytest.raises(HTTPException) as exc_info:
            protected_func()
        assert exc_info.value.code == 403
