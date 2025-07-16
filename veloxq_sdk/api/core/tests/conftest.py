import typing as t

from pytest import fixture

from veloxq_sdk.api.core.http import RestClient


@fixture
def client() -> t.Iterator[RestClient]:
    """Fixture to provide a RestClient instance for tests."""
    http_client = RestClient()
    try:
        yield http_client
    finally:
        http_client.close()
