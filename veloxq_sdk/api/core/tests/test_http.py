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

    def test_builds_wss_url_with_token_and_ssl_context(
        self, api_config, monkeypatch,
    ):
        recorded = {}

        @contextmanager
        def fake_connect(url, **kwargs):
            recorded['url'] = url
            recorded['kwargs'] = kwargs
            yield object()

        monkeypatch.setattr(
            'veloxq_sdk.api.core.http.connect', fake_connect,
        )
        api_config.ssl_context = False
        client = RestClient()
        with client.open_ws('jobs/1/status-updates'):
            pass

        url = httpx.URL(recorded['url'])
        assert url.scheme == 'wss'
        assert url.host == 'api.test'
        assert url.path == '/jobs/1/status-updates'
        assert url.params[RestClient.API_KEY_HEADER] == 'test-token'
        assert recorded['kwargs']['proxy_ssl'] is False
