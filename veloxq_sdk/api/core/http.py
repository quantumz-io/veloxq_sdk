# Copyright 2025-2026 QUANTUMZ.IO sp. z o.o.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import atexit
import os
import ssl
import typing as t
from contextlib import contextmanager, suppress
from contextvars import ContextVar

import httpx
from websockets.sync.client import ClientConnection, connect
from websockets.uri import parse_uri

try:
    from websockets.proxy import get_proxy, parse_proxy
except ImportError:  # websockets 15 keeps them in websockets.uri
    from websockets.uri import get_proxy, parse_proxy

from veloxq_sdk.config import VeloxQAPIConfig

_context_access_token: ContextVar[t.Optional[str]] = ContextVar('veloxq_access_token', default=None)


@contextmanager
def use_access_token(token: str) -> t.Iterator[None]:
    """Send ``token`` as the bearer credential for API calls made in this context.

    Replaces the configured API key for the current thread or task, so a server
    acting for several users can share one client. Worker threads see it when
    started with the context copied, same as ``asyncio.to_thread`` and
    ``anyio.to_thread.run_sync``.
    """
    if not isinstance(token, str) or not token:
        msg = 'access token must be a non-empty string'
        raise ValueError(msg)
    reset = _context_access_token.set(token)
    try:
        yield
    finally:
        _context_access_token.reset(reset)


class RestClient(httpx.Client):
    """A custom HTTP client for VeloxQ API interactions."""

    API_KEY_HEADER = 'x-veloxq-auth-key'
    AUTHORIZATION_HEADER = 'Authorization'

    def __init__(self) -> None:
        config = VeloxQAPIConfig.instance()
        verify = _ssl_verify(config.ssl_context)
        super().__init__(verify=verify)
        config.observe(self._update_api_key, names='token')
        config.observe(self._update_url, names='url')
        config.observe(self._update_ssl_context, names='ssl_context')
        self._set_api_key(config.token)
        self.base_url = config.url
        self.event_hooks = {
            'request': [self._apply_context_access_token],
            'response': [self.update_response_reason],
        }
        self.timeout = httpx.Timeout(connect=5, read=30, write=15, pool=10)
        self._ws_ssl = _websocket_ssl(verify)

    def _update_api_key(self, change: dict) -> None:
        self._set_api_key(change['new'])

    def _set_api_key(self, api_key: str) -> None:
        self.headers.pop(self.API_KEY_HEADER, None)
        if api_key:
            self.headers[self.API_KEY_HEADER] = api_key

    def _apply_context_access_token(self, request: httpx.Request) -> None:
        token = _context_access_token.get()
        if token is None:
            return
        base = self.base_url
        if (request.url.scheme, request.url.host, request.url.port) != (base.scheme, base.host, base.port):
            return
        request.headers.pop(self.API_KEY_HEADER, None)
        request.headers[self.AUTHORIZATION_HEADER] = f'Bearer {token}'

    def _credential_header(self) -> dict[str, str]:
        """Return the one credential header the client is sending."""
        if token := _context_access_token.get():
            return {self.AUTHORIZATION_HEADER: f'Bearer {token}'}
        if api_key := self.headers.get(self.API_KEY_HEADER):
            return {self.API_KEY_HEADER: api_key}
        msg = ('No credentials configured. Set `token` (API key) in the '
               'configuration or wrap the call in `use_access_token`.')
        raise ValueError(msg)

    def _update_url(self, change: dict) -> None:
        """Update the base URL in the client."""
        self.base_url = change['new']

    def _update_ssl_context(self, change: dict) -> None:
        """Update the SSL context in the client."""
        verify = _ssl_verify(change['new'])
        self._ws_ssl = _websocket_ssl(verify)
        self.verify = verify

    @contextmanager
    def open_ws(
        self,
        path: str,
        *,
        open_timeout: float | None = 10,
    ) -> t.Iterator[ClientConnection]:
        """Context manager to open a WebSocket connection.

        Args:
            path (str): The WebSocket path to connect to.
            open_timeout (float | None): Seconds allowed for the opening
                handshake. None waits indefinitely.

        Yields:
            connect: A WebSocket connection object.

        """
        scheme = 'wss' if self.base_url.scheme == 'https' else 'ws'
        url = self._merge_url(path).copy_with(scheme=scheme)
        kwargs = {}
        if _uses_https_proxy(str(url)):
            kwargs['proxy_ssl'] = self._ws_ssl
        with connect(
            str(url),
            ssl=self._ws_ssl,
            open_timeout=open_timeout,
            additional_headers=self._credential_header(),
            **kwargs,
        ) as ws:
            yield ws  # type: ignore[return]

    @staticmethod
    def update_response_reason(response: httpx.Response) -> None:
        """Update the reason phrase of the response based on its content."""
        if response.is_success:
            return
        message = ''
        with suppress(Exception):
            message = response.read()
        try:
            response.extensions['reason_phrase'] = response.json().get('message', '').encode('ascii')
        except Exception:
            if message:
                response.extensions['reason_phrase'] = message


def _uses_https_proxy(url: str) -> bool:
    """Whether websockets connects to `url` through an https:// proxy."""
    proxy = get_proxy(parse_uri(url))
    return proxy is not None and parse_proxy(proxy).scheme == 'https'


def _ssl_verify(setting: ssl.SSLContext | str | bool) -> ssl.SSLContext | bool:
    """Convert ``ssl_context`` setting into httpx's ``verify`` argument."""
    if isinstance(setting, str):
        if os.path.isdir(setting):  # noqa: PTH112
            return ssl.create_default_context(capath=setting)
        return ssl.create_default_context(cafile=setting)
    return setting


def _websocket_ssl(verify: ssl.SSLContext | bool) -> ssl.SSLContext | None:
    """Convert httpx's ``verify`` argument into websocket's ``ssl`` argument."""
    if isinstance(verify, ssl.SSLContext):
        return verify
    if verify:
        return None
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class _RestClientGetter:
    client = None

    def __get__(self, *args, **kwargs) -> RestClient:
        if _RestClientGetter.client is None:
            _RestClientGetter.client = RestClient()
            atexit.register(_RestClientGetter.client.close)
        return _RestClientGetter.client


class ClientMixin:
    """Mixin class to provide HTTP client functionality."""

    _http = _RestClientGetter()

    http = _http

