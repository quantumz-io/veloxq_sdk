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

import httpx
from websockets.sync.client import ClientConnection, connect
from websockets.uri import parse_uri

try:
    from websockets.proxy import get_proxy, parse_proxy
except ImportError:  # websockets 15 keeps them in websockets.uri
    from websockets.uri import get_proxy, parse_proxy

from veloxq_sdk.config import VeloxQAPIConfig


class RestClient(httpx.Client):
    """A custom HTTP client for VeloxQ API interactions."""

    API_KEY_HEADER = 'x-veloxq-auth-key'

    def __init__(self) -> None:
        config = VeloxQAPIConfig.instance()
        super().__init__(verify=config.ssl_context)
        config.observe(self._update_token, names='token')
        config.observe(self._update_url, names='url')
        config.observe(self._update_ssl_context, names='ssl_context')
        self.headers[self.API_KEY_HEADER] = config.token
        self.base_url = config.url
        self.event_hooks = {
            'response': [self.update_response_reason],
        }
        self.timeout = httpx.Timeout(connect=5, read=30, write=15, pool=10)
        self._ws_ssl = _websocket_ssl(config.ssl_context)

    def _update_token(self, change: dict) -> None:
        """Update the API token in the headers."""
        self.headers[self.API_KEY_HEADER] = change['new']

    def _update_url(self, change: dict) -> None:
        """Update the base URL in the client."""
        self.base_url = change['new']

    def _update_ssl_context(self, change: dict) -> None:
        """Update the SSL context in the client."""
        self._ws_ssl = _websocket_ssl(change['new'])
        self.verify = change['new']

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
        kwargs = {}
        if _uses_https_proxy(str(url)):
            kwargs['proxy_ssl'] = self._ws_ssl
        with connect(
            str(url),
            ssl=self._ws_ssl,
            open_timeout=open_timeout,
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


def _websocket_ssl(setting: ssl.SSLContext | str | bool) -> ssl.SSLContext | None:
    """Convert ``ssl_context`` setting into websocket's ``ssl`` argument."""
    if isinstance(setting, ssl.SSLContext):
        return setting
    if isinstance(setting, str):
        if os.path.isdir(setting):  # noqa: PTH112
            return ssl.create_default_context(capath=setting)
        return ssl.create_default_context(cafile=setting)
    if setting:
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

