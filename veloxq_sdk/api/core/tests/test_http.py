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
import threading
from contextlib import contextmanager

import certifi
import httpx
import pytest

from veloxq_sdk.api.core.http import ClientMixin, RestClient, use_access_token


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

    def test_no_credentials_sends_neither_header(self, api_config):
        api_config.token = ''
        client = RestClient()
        assert RestClient.API_KEY_HEADER not in client.headers
        assert RestClient.AUTHORIZATION_HEADER not in client.headers

    def test_url_change_updates_base_url(self, api_config):
        client = RestClient()
        api_config.url = 'https://other.test'
        assert str(client.base_url) == 'https://other.test'

    def test_ca_path_reaches_httpx_as_ssl_context(
        self, api_config, tmp_path, monkeypatch,
    ):
        seen = {}
        init = httpx.Client.__init__

        def spy(client, *args, **kwargs):
            seen.update(kwargs)
            init(client, *args, **kwargs)

        monkeypatch.setattr(httpx.Client, '__init__', spy)
        api_config.ssl_context = str(tmp_path)
        client = RestClient()
        assert isinstance(seen['verify'], ssl.SSLContext)
        assert seen['verify'] is client._ws_ssl

    def test_ca_file_is_loaded_as_cafile(self, api_config):
        # A cafile loads its certificates eagerly, a capath only on demand.
        api_config.ssl_context = certifi.where()
        client = RestClient()
        assert client._ws_ssl.cert_store_stats()['x509_ca'] > 0

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
    def test_missing_credentials_raise(self, api_config):
        api_config.token = ''
        client = RestClient()
        with pytest.raises(ValueError, match='No credentials configured'):
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

    def test_builds_wss_url_with_token_header(self, api_config, connect_kwargs, proxy_env):
        with RestClient().open_ws('jobs/1/status-updates'):
            pass

        url = httpx.URL(connect_kwargs['url'])
        assert url.scheme == 'wss'
        assert url.host == 'api.test'
        assert url.path == '/jobs/1/status-updates'
        assert not url.params
        headers = connect_kwargs['kwargs']['additional_headers']
        assert headers == {RestClient.API_KEY_HEADER: 'test-token'}
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


class TestStorageClient:
    def test_signed_url_requests_carry_no_credential(self, api_config, mock_api):
        mock_api.add('GET', '/blob', content=b'x')
        with use_access_token('eyJ.user'), ClientMixin.http.storage.stream('GET', 'https://blob.test/blob') as r:
            r.read()
        sent = mock_api.calls('GET', '/blob')[0].headers
        assert RestClient.API_KEY_HEADER not in sent
        assert RestClient.AUTHORIZATION_HEADER not in sent

    def test_api_requests_still_carry_the_credential(self, api_config, mock_api):
        mock_api.add('GET', '/jobs', json={'data': []})
        ClientMixin.http.get('jobs')
        sent = mock_api.calls('GET', '/jobs')[0].headers
        assert sent[RestClient.API_KEY_HEADER] == 'test-token'


class TestWebsocketScheme:
    def test_plain_http_api_uses_ws(self, api_config, monkeypatch):
        api_config.url = 'http://localhost:8000'
        seen: list[str] = []

        class _Conn:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr(
            'veloxq_sdk.api.core.http.connect',
            lambda url, **kw: (seen.append(url), _Conn())[1],
        )
        with ClientMixin.http.open_ws('jobs/1/status-updates'):
            pass
        assert seen == ['ws://localhost:8000/jobs/1/status-updates']


class TestUseAccessToken:
    def test_requests_in_the_context_carry_its_bearer_only(self, api_config, mock_api):
        mock_api.add('GET', '/jobs', json={'data': []})
        with use_access_token('eyJ.user'):
            ClientMixin.http.get('jobs')
        sent = mock_api.calls('GET', '/jobs')[0].headers
        assert sent[RestClient.AUTHORIZATION_HEADER] == 'Bearer eyJ.user'
        assert RestClient.API_KEY_HEADER not in sent

    def test_requests_after_the_context_use_the_configuration(self, api_config, mock_api):
        mock_api.add('GET', '/jobs', json={'data': []})
        with use_access_token('eyJ.user'):
            pass
        ClientMixin.http.get('jobs')
        sent = mock_api.calls('GET', '/jobs')[0].headers
        assert sent[RestClient.API_KEY_HEADER] == 'test-token'
        assert RestClient.AUTHORIZATION_HEADER not in sent

    def test_other_hosts_never_receive_the_bearer(self, api_config, mock_api):
        mock_api.add('GET', '/blob', content=b'x')
        with use_access_token('eyJ.user'):
            ClientMixin.http.get('https://blob.test/blob')
        assert RestClient.AUTHORIZATION_HEADER not in mock_api.calls('GET', '/blob')[0].headers

    def test_threads_keep_their_own_token(self, api_config, mock_api):
        mock_api.add('GET', '/jobs', json={'data': []})
        barrier = threading.Barrier(2)

        def call(token):
            with use_access_token(token):
                barrier.wait()
                ClientMixin.http.get('jobs', params={'who': token})

        threads = [threading.Thread(target=call, args=(f'eyJ.{k}',)) for k in 'ab']
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        for request in mock_api.calls('GET', '/jobs'):
            who = request.url.params['who']
            assert request.headers[RestClient.AUTHORIZATION_HEADER] == f'Bearer {who}'

    def test_websocket_uses_the_context_bearer(self, api_config, monkeypatch):
        seen = {}

        @contextmanager
        def fake_connect(url, **kwargs):
            seen.update(kwargs)
            yield object()

        monkeypatch.setattr('veloxq_sdk.api.core.http.connect', fake_connect)
        with use_access_token('eyJ.user'), ClientMixin.http.open_ws('jobs/1/status-updates'):
            pass
        assert seen['additional_headers'] == {RestClient.AUTHORIZATION_HEADER: 'Bearer eyJ.user'}

    def test_websocket_without_any_credential_uses_the_context_bearer(self, api_config, monkeypatch):
        api_config.token = ''
        seen = {}

        @contextmanager
        def fake_connect(url, **kwargs):
            seen['url'] = url
            seen.update(kwargs)
            yield object()

        monkeypatch.setattr('veloxq_sdk.api.core.http.connect', fake_connect)
        with use_access_token('eyJ.user'), ClientMixin.http.open_ws('jobs/1/status-updates'):
            pass
        assert not httpx.URL(seen['url']).params
        assert seen['additional_headers'] == {RestClient.AUTHORIZATION_HEADER: 'Bearer eyJ.user'}

    def test_empty_token_is_refused(self):
        with pytest.raises(ValueError, match='access token must be a non-empty string'):
            with use_access_token(''):
                pass
