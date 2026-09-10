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

"""Shared pytest fixtures for the veloxq_sdk test suite.

Atomic tests never touch the network: HTTP goes through an in-memory
``httpx.MockTransport`` (the ``mock_api`` fixture) and WebSockets are
replaced by ``FakeWS`` objects (the ``ws_factory`` fixture).
"""

from __future__ import annotations

import typing as t
from contextlib import contextmanager

import httpx
import pytest

from veloxq_sdk.config import VeloxQAPIConfig

_UNSET = object()


class MockAPI:
    """In-memory route table served through ``httpx.MockTransport``.

    Routes are keyed by ``(method, path)``. Every request the client makes
    is recorded in ``requests`` so tests can assert on bodies and params.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._routes: dict[
            tuple[str, str], t.Callable[[httpx.Request], httpx.Response]
        ] = {}

    @staticmethod
    def _key(method: str, path: str) -> tuple[str, str]:
        if not path.startswith('/'):
            path = '/' + path
        return (method.upper(), path)

    def add(
        self,
        method: str,
        path: str,
        *,
        json: t.Any = _UNSET,
        content: bytes | None = None,
        text: str | None = None,
        status_code: int = 200,
    ) -> None:
        """Register a static response for ``method path``."""

        def _handler(_request: httpx.Request) -> httpx.Response:
            kwargs: dict[str, t.Any] = {}
            if json is not _UNSET:
                kwargs['json'] = json
            if content is not None:
                kwargs['content'] = content
            if text is not None:
                kwargs['text'] = text
            return httpx.Response(status_code, **kwargs)

        self._routes[self._key(method, path)] = _handler

    def add_handler(
        self,
        method: str,
        path: str,
        handler: t.Callable[[httpx.Request], httpx.Response],
    ) -> None:
        """Register a dynamic handler for ``method path``."""
        self._routes[self._key(method, path)] = handler

    def calls(self, method: str, path: str) -> list[httpx.Request]:
        """Return the recorded requests matching ``method path``."""
        key = self._key(method, path)
        return [
            r for r in self.requests if (r.method, r.url.path) == key
        ]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = (request.method, request.url.path)
        handler = self._routes.get(key)
        if handler is None:
            return httpx.Response(
                404, json={'message': f'no mock route for {key}'},
            )
        return handler(request)


class FakeWS:
    """Stand-in for a ``websockets`` client connection.

    ``recv`` pops from ``recv_messages`` (a message may be a callable that
    produces the payload, letting tests inject delays) and returns ``b'ack'``
    once the queue is exhausted. ``send`` records every payload.
    """

    def __init__(self, recv_messages: t.Iterable[t.Any] = ()) -> None:
        self.sent: list[bytes] = []
        self.recv_calls = 0
        self._messages = list(recv_messages)

    def send(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, decode: bool = True) -> t.Any:  # noqa: FBT001, FBT002
        self.recv_calls += 1
        if self._messages:
            message = self._messages.pop(0)
            return message() if callable(message) else message
        return b'ack'


@pytest.fixture(autouse=True)
def _fresh_singletons() -> t.Iterator[None]:
    """Isolate every test from the config and HTTP-client singletons."""
    from veloxq_sdk.api.core.http import _RestClientGetter

    def _reset() -> None:
        if _RestClientGetter.client is not None:
            _RestClientGetter.client.close()
            _RestClientGetter.client = None
        VeloxQAPIConfig.clear_instance()

    _reset()
    yield
    _reset()


@pytest.fixture
def api_config() -> VeloxQAPIConfig:
    """A fresh config singleton pointing at a fake host."""
    config = VeloxQAPIConfig.instance()
    config.token = 'test-token'
    config.url = 'https://api.test'
    return config


@pytest.fixture
def mock_api(api_config: VeloxQAPIConfig) -> MockAPI:
    """Route the shared RestClient through an in-memory transport."""
    from veloxq_sdk.api.core.http import ClientMixin

    api = MockAPI()
    client = ClientMixin.http
    client._transport = httpx.MockTransport(api)
    return api


@pytest.fixture
def ws_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> t.Callable[..., list[str]]:
    """Patch ``RestClient.open_ws`` to yield the given FakeWS objects.

    Returns an installer: ``paths = ws_factory(ws1, ws2, ...)``. Each call
    to ``open_ws`` records its path in ``paths`` and yields the next fake
    connection.
    """
    from veloxq_sdk.api.core.http import RestClient

    def install(*connections: FakeWS) -> list[str]:
        queue = list(connections)
        opened_paths: list[str] = []

        @contextmanager
        def fake_open_ws(_self: RestClient, path: str) -> t.Iterator[FakeWS]:
            opened_paths.append(path)
            yield queue.pop(0)

        monkeypatch.setattr(RestClient, 'open_ws', fake_open_ws)
        return opened_paths

    return install
