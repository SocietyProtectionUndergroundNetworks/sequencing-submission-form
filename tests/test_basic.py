# tests/test_basic.py


def test_app_creation(app):
    """
    Tests that the Flask application instance can be created successfully.
    The 'app' fixture from conftest.py provides the app instance.
    """
    assert app is not None
    assert (
        app.testing is True
    )  # Should be True due to test_config in conftest.py


def test_homepage_access(client):
    """
    Tests accessing a simple Flask route (e.g., homepage) using the test client.
    The 'client' fixture from conftest.py provides the test client.
    """
    # Assuming you have a route like:
    # @app.route('/')
    # def index():
    #     return "Welcome to the homepage!"

    response = client.get("/")
    assert response.status_code == 200
    # Check for content in the response, if applicable
    # assert b"Welcome to the homepage!" in response.data
