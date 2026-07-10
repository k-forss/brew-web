"""
Comprehensive unit tests for calendar blueprint in app/routes_calendar.py.

Test Strategy:
- Uses pytest-flask-sqlalchemy for transactional isolation
- Mocks request.get_json for JSON POST/PUT tests
- Tests all calendar routes with proper authentication/authorization
- Edge cases: missing dates, invalid JSON, None values

Routes Tested:
- calendar(): Main calendar page (FullCalendar.js frontend)
- calendar_events(): API for FullCalendar to fetch events
- create_calendar_event(): JSON POST to create event
- update_calendar_event(): JSON PUT to update event
- delete_calendar_event(): JSON DELETE to remove event
"""

import json

from datetime import date, datetime

from app.models import Batch, CalendarEvent, Recipe, User


class TestCalendar:
    """Tests for calendar() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/app/calendar", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_renders_calendar_html(self, client, db_session, admin_user):
        """Test renders calendar.html."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/calendar")
            assert response.status_code == 200
            assert b"calendar" in response.data.lower()

    def test_uses_endpoint_calendar_explicit_naming(self, client, db_session, admin_user):
        """Test uses endpoint='calendar' explicit naming."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Verify the endpoint exists and is accessible
            response = c.get("/app/calendar")
            assert response.status_code == 200


class TestCalendarEvents:
    """Tests for calendar_events() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.get("/app/api/calendar-events", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_queries_all_batches(self, client, db_session, admin_user):
        """Test queries all batches."""
        # Create test batches
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Test Batch"
        batch.recipe_id = recipe.id
        batch.start_date = datetime(2026, 1, 1)
        batch.end_date = datetime(2026, 2, 1)
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            data = response.get_json()
            assert len(data) >= 1

    def test_queries_all_calendar_events(self, client, db_session, admin_user):
        """Test queries all calendar events."""
        # Create test calendar event
        event = CalendarEvent()
        event.title = "Test Event"
        event.start = date(2026, 1, 15)
        event.description = "Test Description"
        event.all_day = True
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            data = response.get_json()
            assert len(data) >= 1

    def test_creates_batch_start_events_if_start_date_exists(self, client, db_session, admin_user):
        """Test creates batch start events (if start_date exists)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Start Batch"
        batch.recipe_id = recipe.id
        batch.start_date = datetime(2026, 1, 1)
        batch.end_date = None  # No end date
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            data = response.get_json()
            # Should have start event
            start_events = [e for e in data if "Start:" in e.get("title", "")]
            assert len(start_events) >= 1

    def test_creates_batch_bottle_events_if_end_date_exists(self, client, db_session, admin_user):
        """Test creates batch bottle events (if end_date exists)."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "End Batch"
        batch.recipe_id = recipe.id
        batch.start_date = datetime(2026, 1, 1)
        batch.end_date = datetime(2026, 2, 1)
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            data = response.get_json()
            # Should have bottle event
            bottle_events = [e for e in data if "Bottle:" in e.get("title", "")]
            assert len(bottle_events) >= 1

    def test_batch_events_have_required_fields(self, client, db_session, admin_user):
        """Test batch events have: title, start, allDay, description, custom=False, type="batch"."""
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Field Test Batch"
        batch.recipe_id = recipe.id
        batch.start_date = datetime(2026, 1, 1)
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            data = response.get_json()

            start_events = [e for e in data if "Start:" in e.get("title", "")]
            assert len(start_events) > 0
            event = start_events[0]

            assert "title" in event
            assert "start" in event
            assert "allDay" in event
            assert "description" in event
            assert event.get("custom") is False
            assert event.get("type") == "batch"

    def test_custom_events_have_required_fields(self, client, db_session, admin_user):
        """Test custom events have: id, title, start, end, allDay, description,
        custom=True, type="custom"."""
        event = CalendarEvent()
        event.title = "Custom Event"
        event.start = date(2026, 1, 15)
        event.end = date(2026, 1, 16)
        event.description = "Custom Description"
        event.all_day = True
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            data = response.get_json()

            custom_events = [e for e in data if e.get("custom") is True]
            assert len(custom_events) > 0
            event_data = custom_events[0]

            assert "id" in event_data
            assert "title" in event_data
            assert "start" in event_data
            assert "allDay" in event_data
            assert "description" in event_data
            assert event_data.get("custom") is True
            assert event_data.get("type") == "custom"

    def test_returns_json_array_of_events(self, client, db_session, admin_user):
        """Test returns JSON array of events."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            assert response.content_type == "application/json"
            data = response.get_json()
            assert isinstance(data, list)

    def test_date_formatting_yyyy_mm_dd(self, client, db_session, admin_user):
        """Test date formatting: "%Y-%m-%d"."""
        # Create recipe first (required by Batch model)
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "Date Format Batch"
        batch.recipe_id = recipe.id
        batch.start_date = datetime(2026, 1, 15)
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            data = response.get_json()

            start_events = [e for e in data if "Start:" in e.get("title", "")]
            assert len(start_events) > 0
            # Check date format YYYY-MM-DD
            assert start_events[0]["start"] == "2026-01-15"

    def test_handles_none_end_date_for_batches(self, client, db_session, admin_user):
        """Test handles None end_date for batches."""
        # Create recipe first (required by Batch model)
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "No End Date Batch"
        batch.recipe_id = recipe.id
        batch.start_date = datetime(2026, 1, 1)
        batch.end_date = None
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            data = response.get_json()

            # Should have start event but no bottle event
            start_events = [e for e in data if "Start:" in e.get("title", "")]
            bottle_events = [e for e in data if "Bottle:" in e.get("title", "")]
            assert len(start_events) >= 1
            assert len(bottle_events) == 0

    def test_handles_none_end_for_custom_events(self, client, db_session, admin_user):
        """Test handles None end for custom events."""
        event = CalendarEvent()
        event.title = "No End Event"
        event.start = date(2026, 1, 15)
        event.end = None
        event.description = "Test"
        event.all_day = True
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            data = response.get_json()

            custom_events = [e for e in data if e.get("custom") is True]
            assert len(custom_events) > 0
            # End should be None in JSON
            assert custom_events[0].get("end") is None


class TestCreateCalendarEvent:
    """Tests for create_calendar_event() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/app/calendar-event",
            data=json.dumps({"title": "Test"}),
            content_type="application/json",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_role_admin_or_editor(self, client, db_session, test_user):
        """Test requires role 'admin' or 'editor' (@role_required)."""
        # test_user has role 'user', should be forbidden
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.post(
                "/app/calendar-event",
                data=json.dumps({"title": "Test"}),
                content_type="application/json",
                follow_redirects=True,
            )
            assert response.status_code == 403

    def test_csrf_exempt(self, client, db_session, admin_user):
        """Test CSRF exempt (@csrf.exempt)."""
        # If CSRF was not exempt, this would fail without CSRF token
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/calendar-event",
                data=json.dumps({"title": "CSRF Test", "start": "2026-01-15"}),
                content_type="application/json",
            )
            # Should succeed (CSRF exempt)
            assert response.status_code == 200

    def test_post_with_json_creates_calendarevent(self, client, db_session, admin_user):
        """Test POST with JSON creates CalendarEvent."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/calendar-event",
                data=json.dumps({"title": "New Event", "start": "2026-01-15"}),
                content_type="application/json",
            )

        event = CalendarEvent.query.filter_by(title="New Event").first()
        assert event is not None

    def test_post_sets_title_from_json(self, client, db_session, admin_user):
        """Test POST sets title from JSON."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/calendar-event",
                data=json.dumps({"title": "Title Test Event", "start": "2026-01-15"}),
                content_type="application/json",
            )

        event = CalendarEvent.query.filter_by(title="Title Test Event").first()
        assert event is not None
        assert event.title == "Title Test Event"

    def test_post_sets_start_from_json(self, client, db_session, admin_user):
        """Test POST sets start from JSON (parses "%Y-%m-%d")."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/calendar-event",
                data=json.dumps({"title": "Start Test", "start": "2026-03-20"}),
                content_type="application/json",
            )

        event = CalendarEvent.query.filter_by(title="Start Test").first()
        assert event is not None
        assert event.start == date(2026, 3, 20)

    def test_post_sets_end_from_json_if_provided(self, client, db_session, admin_user):
        """Test POST sets end from JSON if provided."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/calendar-event",
                data=json.dumps({"title": "End Test", "start": "2026-01-15", "end": "2026-01-20"}),
                content_type="application/json",
            )

        event = CalendarEvent.query.filter_by(title="End Test").first()
        assert event is not None
        assert event.end == date(2026, 1, 20)

    def test_post_sets_description_from_json(self, client, db_session, admin_user):
        """Test POST sets description from JSON."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/calendar-event",
                data=json.dumps(
                    {
                        "title": "Description Test",
                        "start": "2026-01-15",
                        "description": "Test Description",
                    }
                ),
                content_type="application/json",
            )

        event = CalendarEvent.query.filter_by(title="Description Test").first()
        assert event is not None
        assert event.description == "Test Description"

    def test_post_sets_all_day_true_hardcoded(self, client, db_session, admin_user):
        """Test POST sets all_day=True (hardcoded)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/calendar-event",
                data=json.dumps({"title": "All Day Test", "start": "2026-01-15"}),
                content_type="application/json",
            )

        event = CalendarEvent.query.filter_by(title="All Day Test").first()
        assert event is not None
        assert event.all_day is True

    def test_post_sets_created_by_current_user_id(self, client, db_session, admin_user):
        """Test POST sets created_by=current_user.id."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/calendar-event",
                data=json.dumps({"title": "Created By Test", "start": "2026-01-15"}),
                content_type="application/json",
            )

        event = CalendarEvent.query.filter_by(title="Created By Test").first()
        assert event is not None
        assert event.created_by == admin_user.id

    def test_post_commits_to_database(self, client, db_session, admin_user):
        """Test POST commits to database."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.post(
                "/app/calendar-event",
                data=json.dumps({"title": "Commit Test", "start": "2026-01-15"}),
                content_type="application/json",
            )

        # Verify commit by querying
        event = CalendarEvent.query.filter_by(title="Commit Test").first()
        assert event is not None

    def test_post_returns_success_true(self, client, db_session, admin_user):
        """Test POST returns {"success": True}."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.post(
                "/app/calendar-event",
                data=json.dumps({"title": "Success Test", "start": "2026-01-15"}),
                content_type="application/json",
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True


class TestUpdateCalendarEvent:
    """Tests for update_calendar_event() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.put(
            "/app/calendar-event/1",
            data=json.dumps({"title": "Test"}),
            content_type="application/json",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_role_admin_or_editor(self, client, db_session, test_user):
        """Test requires role 'admin' or 'editor' (@role_required)."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.put(
                "/app/calendar-event/1",
                data=json.dumps({"title": "Test"}),
                content_type="application/json",
                follow_redirects=True,
            )
            assert response.status_code == 403

    def test_csrf_exempt(self, client, db_session, admin_user):
        """Test CSRF exempt (@csrf.exempt)."""
        # Create event first
        event = CalendarEvent()
        event.title = "Update Test"
        event.start = date(2026, 1, 15)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.put(
                f"/app/calendar-event/{event_id}",
                data=json.dumps(
                    {"title": "Updated", "start": "2026-01-15"}  # Required field
                ),
                content_type="application/json",
            )
            # Should succeed (CSRF exempt)
            assert response.status_code == 200

    def test_put_with_valid_id_updates_event(self, client, db_session, admin_user):
        """Test PUT with valid ID updates event."""
        # Create event first
        event = CalendarEvent()
        event.title = "Original Title"
        event.start = date(2026, 1, 15)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.put(
                f"/app/calendar-event/{event_id}",
                data=json.dumps(
                    {"title": "Updated Title", "start": "2026-01-15"}  # Required field
                ),
                content_type="application/json",
            )

        updated_event = CalendarEvent.query.get(event_id)
        assert updated_event.title == "Updated Title"

    def test_put_with_invalid_id_raises_404(self, client, db_session, admin_user):
        """Test PUT with invalid ID raises 404."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.put(
                "/app/calendar-event/99999",
                data=json.dumps({"title": "Test"}),
                content_type="application/json",
            )
            assert response.status_code == 404

    def test_put_updates_title_from_json(self, client, db_session, admin_user):
        """Test PUT updates title from JSON."""
        event = CalendarEvent()
        event.title = "Old Title"
        event.start = date(2026, 1, 15)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.put(
                f"/app/calendar-event/{event_id}",
                data=json.dumps(
                    {"title": "New Title", "start": "2026-01-15"}  # Required field
                ),
                content_type="application/json",
            )

        updated_event = CalendarEvent.query.get(event_id)
        assert updated_event.title == "New Title"

    def test_put_updates_start_from_json(self, client, db_session, admin_user):
        """Test PUT updates start from JSON."""
        event = CalendarEvent()
        event.title = "Start Update Test"
        event.start = date(2026, 1, 15)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.put(
                f"/app/calendar-event/{event_id}",
                data=json.dumps(
                    {
                        "title": "Start Update Test",  # Keep existing title
                        "start": "2026-06-20",
                    }
                ),
                content_type="application/json",
            )

        updated_event = CalendarEvent.query.get(event_id)
        assert updated_event.start == date(2026, 6, 20)

    def test_put_updates_end_from_json_if_provided(self, client, db_session, admin_user):
        """Test PUT updates end from JSON if provided."""
        event = CalendarEvent()
        event.title = "End Update Test"
        event.start = date(2026, 1, 15)
        event.end = date(2026, 1, 20)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.put(
                f"/app/calendar-event/{event_id}",
                data=json.dumps(
                    {
                        "title": "End Update Test",  # Keep existing title
                        "start": "2026-01-15",  # Keep existing start
                        "end": "2026-01-25",
                    }
                ),
                content_type="application/json",
            )

        updated_event = CalendarEvent.query.get(event_id)
        assert updated_event.end == date(2026, 1, 25)

    def test_put_updates_description_from_json(self, client, db_session, admin_user):
        """Test PUT updates description from JSON."""
        event = CalendarEvent()
        event.title = "Desc Update Test"
        event.start = date(2026, 1, 15)
        event.description = "Old Description"
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.put(
                f"/app/calendar-event/{event_id}",
                data=json.dumps(
                    {
                        "title": "Desc Update Test",  # Keep existing title
                        "start": "2026-01-15",  # Required field
                        "description": "New Description",
                    }
                ),
                content_type="application/json",
            )

        updated_event = CalendarEvent.query.get(event_id)
        assert updated_event.description == "New Description"

    def test_put_commits_to_database(self, client, db_session, admin_user):
        """Test PUT commits to database."""
        event = CalendarEvent()
        event.title = "Commit Update Test"
        event.start = date(2026, 1, 15)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.put(
                f"/app/calendar-event/{event_id}",
                data=json.dumps(
                    {
                        "title": "Committed Title",
                        "start": "2026-01-15",  # Required field
                    }
                ),
                content_type="application/json",
            )

        # Verify commit
        updated_event = CalendarEvent.query.get(event_id)
        assert updated_event.title == "Committed Title"

    def test_put_returns_success_true(self, client, db_session, admin_user):
        """Test PUT returns {"success": True}."""
        event = CalendarEvent()
        event.title = "Success Update Test"
        event.start = date(2026, 1, 15)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.put(
                f"/app/calendar-event/{event_id}",
                data=json.dumps(
                    {"title": "Updated", "start": "2026-01-15"}  # Required field
                ),
                content_type="application/json",
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True


class TestDeleteCalendarEvent:
    """Tests for delete_calendar_event() route."""

    def test_requires_login(self, client, db_session):
        """Test requires login (@login_required)."""
        user = User()
        user.username = "testuser"
        user.set_password("password")
        db_session.add(user)
        db_session.commit()

        response = client.delete("/app/calendar-event/1", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_requires_role_admin_only(self, client, db_session, test_user):
        """Test requires role 'admin' only (@role_required('admin'))."""
        # test_user has role 'user', should be forbidden
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(test_user.id)

            response = c.delete("/app/calendar-event/1", follow_redirects=True)
            assert response.status_code == 403

    def test_csrf_exempt(self, client, db_session, admin_user):
        """Test CSRF exempt (@csrf.exempt)."""
        # Create event first
        event = CalendarEvent()
        event.title = "Delete Test"
        event.start = date(2026, 1, 15)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.delete(f"/app/calendar-event/{event_id}")
            # Should succeed (CSRF exempt)
            assert response.status_code == 200

    def test_delete_with_valid_id_deletes_event(self, client, db_session, admin_user):
        """Test DELETE with valid ID deletes event."""
        event = CalendarEvent()
        event.title = "Delete Me"
        event.start = date(2026, 1, 15)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.delete(f"/app/calendar-event/{event_id}")

        deleted_event = CalendarEvent.query.get(event_id)
        assert deleted_event is None

    def test_delete_with_invalid_id_raises_404(self, client, db_session, admin_user):
        """Test DELETE with invalid ID raises 404."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.delete("/app/calendar-event/99999")
            assert response.status_code == 404

    def test_delete_commits_to_database(self, client, db_session, admin_user):
        """Test DELETE commits to database."""
        event = CalendarEvent()
        event.title = "Commit Delete Test"
        event.start = date(2026, 1, 15)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            c.delete(f"/app/calendar-event/{event_id}")

        # Verify deletion is committed
        assert CalendarEvent.query.get(event_id) is None

    def test_delete_returns_success_true(self, client, db_session, admin_user):
        """Test DELETE returns {"success": True}."""
        event = CalendarEvent()
        event.title = "Success Delete Test"
        event.start = date(2026, 1, 15)
        event.created_by = admin_user.id
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.delete(f"/app/calendar-event/{event_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True


class TestEdgeCases:
    """Edge cases and error handling tests."""

    def test_missing_json_fields_in_create(self, client, db_session, admin_user):
        """Test missing JSON fields in create."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Missing required 'start' field - should raise TypeError
            # In TESTING mode, Flask propagates exceptions
            import pytest

            with pytest.raises(TypeError):
                c.post(
                    "/app/calendar-event",
                    data=json.dumps({"title": "Missing Start"}),
                    content_type="application/json",
                )

    def test_invalid_date_format_in_json(self, client, db_session, admin_user):
        """Test invalid date format in JSON."""
        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Invalid date format - should raise ValueError
            import pytest

            with pytest.raises(ValueError):
                c.post(
                    "/app/calendar-event",
                    data=json.dumps(
                        {"title": "Invalid Date", "start": "2026/01/15"}  # Wrong format
                    ),
                    content_type="application/json",
                )

    def test_database_commit_failures(self, client, db_session, admin_user, monkeypatch):
        """Test database commit failures."""

        def mock_commit():
            raise Exception("Database error")

        monkeypatch.setattr("app.routes_calendar.db.session.commit", mock_commit)

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            # Should raise Exception
            import pytest

            with pytest.raises(Exception, match=r".*"):
                c.post(
                    "/app/calendar-event",
                    data=json.dumps({"title": "Commit Fail Test", "start": "2026-01-15"}),
                    content_type="application/json",
                )

    def test_batches_with_no_dates(self, client, db_session, admin_user):
        """Test batches with no dates (start_date/end_date None)."""
        # Create recipe first (required by Batch model)
        recipe = Recipe()
        recipe.name = "Test Recipe"
        recipe.alcohol_type = "Mead"
        db_session.add(recipe)
        db_session.commit()

        batch = Batch()
        batch.name = "No Dates Batch"
        batch.recipe_id = recipe.id
        batch.start_date = None
        batch.end_date = None
        db_session.add(batch)
        db_session.commit()

        with client as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)

            response = c.get("/app/api/calendar-events")
            assert response.status_code == 200
            data = response.get_json()

            # Should not create any events for this batch
            batch_events = [e for e in data if "No Dates Batch" in e.get("title", "")]
            assert len(batch_events) == 0
