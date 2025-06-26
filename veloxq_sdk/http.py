import atexit
import typing as t
from contextlib import contextmanager

import httpx
from websockets.sync.client import connect

from veloxq_sdk.config import APIConfig

if t.TYPE_CHECKING:
    from websockets.sync.client import ClientConnection


class RestClient(httpx.Client):
    """A custom HTTP client for VeloxQ API interactions."""

    API_KEY_HEADER = 'x-veloxq-auth-key'

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        self.config = APIConfig.instance()
        headers = {
            self.API_KEY_HEADER: self.config.token,
        }
        super().__init__(*args, **kwargs, base_url = self.config.url, headers = headers)

    @contextmanager
    def open_ws(self, path: str) -> t.Iterator[ClientConnection]:
        """Context manager to open a WebSocket connection.

        Args:
            path (str): The WebSocket path to connect to.

        Yields:
            connect: A WebSocket connection object.

        """
        url = httpx.URL(self._merge_url(path), params={
            self.API_KEY_HEADER: self.config.token,
        })
        with connect(str(url)) as ws:
            yield ws  # type: ignore[return]


class ClientMixin:
    """Mixin class to provide HTTP client functionality."""

    _http = RestClient()

    @property
    def http(self) -> RestClient:
        """Get the HTTP client instance."""
        return self._http


@atexit.register
def __close_http_client() -> None:
    """Close the HTTP client on exit."""
    if ClientMixin._http.is_closed: # noqa: SLF001
        return
    ClientMixin._http.close() # noqa: SLF001
