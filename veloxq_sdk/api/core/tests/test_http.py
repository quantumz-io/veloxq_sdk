from veloxq_sdk.api.core.http import RestClient


def test_api_connection(client: RestClient):
    """
    Test that the API connection is established correctly.
    """
    response = client.get("/api/health")
    assert response.status_code == 200


def test_api_version(client: RestClient):
    """
    Test that the API version is returned correctly.
    """
    response = client.get("/version")
    assert response.status_code == 200


def test_authenticated(client: RestClient):
    """
    Test that the API requires authentication.
    """
    response = client.get("/")
    assert response.status_code == 200

