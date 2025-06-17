# tests/test_static_page.py


def test_metadata_instructions_page_access(client):
    """
    Tests accessing the /metadata_instructions page and verifies its content.
    The 'client' fixture from conftest.py provides the test client.
    """
    response = client.get("/metadata_instructions")

    # Assert that the page was loaded successfully (HTTP status code 200 OK)
    assert response.status_code == 200

    # Assert that the expected heading is present in the response data
    # Use 'b' prefix because response.data is bytes
    assert b"<h1>Samples metadata file structure</h1>" in response.data
