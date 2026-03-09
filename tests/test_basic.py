# tests/test_basic.py
from unittest.mock import patch


def test_app_creation(app):
    """
    Tests that the Flask application instance can be created successfully.
    The 'app' fixture from conftest.py provides the app instance.
    """
    assert app is not None
    assert (
        app.testing is True
    )  # Should be True due to test_config in conftest.py


def test_homepage_access_unauthorized(client):
    response = client.get("/")
    # 302 is the redirect status code
    assert response.status_code == 302
    # Ensure it's redirecting to the login page
    assert "/login" in response.headers["Location"]


def test_homepage_access_approved_user(client):
    # We patch 'current_user' to look like an authenticated, approved user
    with patch("helpers.decorators.current_user") as mock_user:
        mock_user.is_authenticated = True
        mock_user.approved = True

        response = client.get("/")
        assert response.status_code == 200
        assert (
            b"<h1>SPUN sequencing data submission form</h1>" in response.data
        )
