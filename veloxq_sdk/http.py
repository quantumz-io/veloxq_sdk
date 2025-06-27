import atexit
import typing as t
from contextlib import contextmanager

import httpx
from websockets.sync.client import ClientConnection, connect

from veloxq_sdk.config import VeloxQAPIConfig


class RestClient(httpx.Client):
    """A custom HTTP client for VeloxQ API interactions."""

    API_KEY_HEADER = 'x-veloxq-auth-key'

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        config = VeloxQAPIConfig.instance()
        config.observe(self._update_token, names='token')
        config.observe(self._update_url, names='url')
        self.headers[self.API_KEY_HEADER] = config.token
        self.base_url = config.url

    def _update_token(self, change: dict) -> None:
        """Update the API token in the headers."""
        self.headers[self.API_KEY_HEADER] = change['new']

    def _update_url(self, change: dict) -> None:
        """Update the base URL in the client."""
        self.base_url = change['new']

    @contextmanager
    def open_ws(self, path: str) -> t.Iterator[ClientConnection]:
        """Context manager to open a WebSocket connection.

        Args:
            path (str): The WebSocket path to connect to.

        Yields:
            connect: A WebSocket connection object.

        """
        token = self.headers.get(self.API_KEY_HEADER)
        if not token:
            msg = (f'Missing required header: {self.API_KEY_HEADER}.'
                   ' Make sure that the token is set in the configuration.')
            raise ValueError(msg)
        url = self._merge_url(path).copy_with(
            scheme='wss',
            params={
               self.API_KEY_HEADER: token,
            }
        )
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
