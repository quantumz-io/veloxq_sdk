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

"""Atomic tests for veloxq_sdk.api.core.http."""

import ssl
from contextlib import contextmanager

import httpx
import pytest

from veloxq_sdk.api.core.http import ClientMixin, RestClient


def _response(status_code: int, **kwargs) -> httpx.Response:
    return httpx.Response(
        status_code,
        request=httpx.Request('GET', 'https://api.test/x'),
        **kwargs,
    )


class TestRestClient:
    def test_init_reads_config(self, api_config):
        client = RestClient()
        assert client.headers[RestClient.API_KEY_HEADER] == 'test-token'
        assert str(client.base_url) == 'https://api.test'

    def test_token_change_updates_header(self, api_config):
        client = RestClient()
        api_config.token = 'rotated'
        assert client.headers[RestClient.API_KEY_HEADER] == 'rotated'

    def test_url_change_updates_base_url(self, api_config):
        client = RestClient()
        api_config.url = 'https://other.test'
        assert str(client.base_url) == 'https://other.test'

    def test_client_mixin_returns_singleton(self, api_config):
        assert ClientMixin.http is ClientMixin.http
        assert ClientMixin().http is ClientMixin.http


class TestUpdateResponseReason:
    def test_json_message_becomes_reason(self):
        response = _response(400, json={'message': 'quota exceeded'})
        RestClient.update_response_reason(response)
        assert response.extensions['reason_phrase'] == b'quota exceeded'
        with pytest.raises(httpx.HTTPStatusError, match='quota exceeded'):
            response.raise_for_status()

    def test_non_json_body_becomes_reason(self):
        response = _response(500, content=b'upstream exploded')
        RestClient.update_response_reason(response)
        assert response.extensions['reason_phrase'] == b'upstream exploded'

    def test_success_response_is_untouched(self):
        response = _response(200, json={'message': 'not an error'})
        RestClient.update_response_reason(response)
        assert 'reason_phrase' not in response.extensions


class TestOpenWs:
    def test_missing_token_raises(self, api_config):
        api_config.token = ''
        client = RestClient()
        with pytest.raises(ValueError, match=RestClient.API_KEY_HEADER):
            with client.open_ws('jobs/1/status-updates'):
                pass

    @pytest.fixture
    def connect_kwargs(self, monkeypatch):
        recorded = {}

        @contextmanager
        def fake_connect(url, **kwargs):
            recorded['url'] = url
            recorded['kwargs'] = kwargs
            yield object()

        monkeypatch.setattr(
            'veloxq_sdk.api.core.http.connect', fake_connect,
        )
        return recorded

    def test_builds_wss_url_with_token(self, api_config, connect_kwargs, proxy_env):
        with RestClient().open_ws('jobs/1/status-updates'):
            pass

        url = httpx.URL(connect_kwargs['url'])
        assert url.scheme == 'wss'
        assert url.host == 'api.test'
        assert url.path == '/jobs/1/status-updates'
        assert url.params[RestClient.API_KEY_HEADER] == 'test-token'
        # proxy_ssl secures the hop to a proxy, not the server, and rejects
        # http:// proxies taken from the environment.
        assert 'proxy_ssl' not in connect_kwargs['kwargs']

    def test_default_ssl_uses_websockets_default(self, api_config, connect_kwargs):
        with RestClient().open_ws('jobs/1/status-updates'):
            pass
        assert connect_kwargs['kwargs']['ssl'] is None

    def test_disabled_ssl_skips_verification(self, api_config, connect_kwargs):
        api_config.ssl_context = False
        with RestClient().open_ws('jobs/1/status-updates'):
            pass
        context = connect_kwargs['kwargs']['ssl']
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_NONE
        assert context.check_hostname is False

    def test_ssl_context_is_built_once_per_setting(
        self, api_config, connect_kwargs, monkeypatch,
    ):
        built = []
        create = ssl.create_default_context

        def counting_create(*args, **kwargs):
            built.append(args or kwargs)
            return create(*args, **kwargs)

        monkeypatch.setattr(ssl, 'create_default_context', counting_create)
        api_config.ssl_context = False
        client = RestClient()
        for _ in range(3):
            with client.open_ws('jobs/1/status-updates'):
                pass
        assert len(built) == 1
        first = connect_kwargs['kwargs']['ssl']

        api_config.ssl_context = True
        with client.open_ws('jobs/1/status-updates'):
            pass
        assert connect_kwargs['kwargs']['ssl'] is None
        assert first.verify_mode == ssl.CERT_NONE

    def test_ca_directory_is_a_capath(self, api_config, connect_kwargs, tmp_path):
        api_config.ssl_context = str(tmp_path)
        with RestClient().open_ws('jobs/1/status-updates'):
            pass
        assert isinstance(connect_kwargs['kwargs']['ssl'], ssl.SSLContext)

    def test_open_timeout_is_forwarded(self, api_config, connect_kwargs):
        with RestClient().open_ws('jobs/1/status-updates', open_timeout=3.5):
            pass
        assert connect_kwargs['kwargs']['open_timeout'] == 3.5

    def test_custom_ssl_context_is_used(self, api_config, connect_kwargs):
        context = ssl.create_default_context()
        api_config.ssl_context = context
        with RestClient().open_ws('jobs/1/status-updates'):
            pass
        assert connect_kwargs['kwargs']['ssl'] is context

    @pytest.fixture
    def proxy_env(self, monkeypatch):
        for var in ('NO_PROXY', 'no_proxy', 'ALL_PROXY', 'all_proxy',
                    'WSS_PROXY', 'wss_proxy', 'SOCKS_PROXY', 'socks_proxy',
                    'HTTPS_PROXY', 'https_proxy'):
            monkeypatch.delenv(var, raising=False)

        def set_proxy(url):
            monkeypatch.setenv('https_proxy', url)

        return set_proxy

    def test_https_proxy_uses_configured_ssl(self, api_config, connect_kwargs, proxy_env):
        proxy_env('https://proxy.corp:443')
        context = ssl.create_default_context()
        api_config.ssl_context = context
        with RestClient().open_ws('jobs/1/status-updates'):
            pass
        assert connect_kwargs['kwargs']['proxy_ssl'] is context

    def test_http_proxy_gets_no_proxy_ssl(self, api_config, connect_kwargs, proxy_env):
        # websockets rejects proxy_ssl for an http:// proxy.
        proxy_env('http://proxy.corp:3128')
        api_config.ssl_context = ssl.create_default_context()
        with RestClient().open_ws('jobs/1/status-updates'):
            pass
        assert 'proxy_ssl' not in connect_kwargs['kwargs']
