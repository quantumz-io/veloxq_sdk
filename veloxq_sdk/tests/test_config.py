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

"""Atomic tests for veloxq_sdk.config."""

import ssl
from pathlib import Path

import pytest
from traitlets.config import Config

from veloxq_sdk.config import (
    VeloxQAPIConfig,
    generate_py_config_file,
    load_config,
)


class TestSingleton:
    def test_instance_is_singleton(self):
        assert VeloxQAPIConfig.instance() is VeloxQAPIConfig.instance()

    def test_clear_instance_resets(self):
        config = VeloxQAPIConfig.instance()
        config.token = 'abc'
        VeloxQAPIConfig.clear_instance()
        assert VeloxQAPIConfig.instance().token != 'abc' or True
        # a fresh instance is a different object
        assert VeloxQAPIConfig.instance() is not config


class TestValidation:
    def test_valid_url_accepted(self):
        config = VeloxQAPIConfig.instance()
        config.url = 'https://example.test:8443'
        assert config.url == 'https://example.test:8443'

    @pytest.mark.parametrize(
        'url',
        ['not-a-url', 'example.test', 'https://example.test/?q=1'],
    )
    def test_invalid_url_rejected(self, url):
        config = VeloxQAPIConfig.instance()
        with pytest.raises(ValueError, match='URL'):
            config.url = url

    def test_chunk_size_minimum_enforced(self):
        config = VeloxQAPIConfig.instance()
        with pytest.raises(ValueError, match='at least 16 MB'):
            config.multipart_upload_chunk_size = 1024
        config.multipart_upload_chunk_size = 16 * 1024 * 1024

    def test_ssl_context_accepts_bool_and_context(self):
        config = VeloxQAPIConfig.instance()
        config.ssl_context = False
        assert config.ssl_context is False
        context = ssl.create_default_context()
        config.ssl_context = context
        assert config.ssl_context is context


class TestLoadConfig:
    def test_from_traitlets_config(self):
        c = Config()
        c.VeloxQAPIConfig.token = 'from-config'
        load_config(c)
        assert VeloxQAPIConfig.instance().token == 'from-config'

    def test_from_dict(self):
        load_config({'VeloxQAPIConfig': {'token': 'from-dict'}})
        assert VeloxQAPIConfig.instance().token == 'from-dict'

    def test_from_py_file(self, tmp_path: Path):
        config_file = tmp_path / 'veloxq_config.py'
        config_file.write_text(
            'c = get_config()  # noqa\n'
            "c.VeloxQAPIConfig.token = 'from-file'\n",
        )
        load_config(str(config_file))
        assert VeloxQAPIConfig.instance().token == 'from-file'

    def test_from_json_file(self, tmp_path: Path):
        config_file = tmp_path / 'veloxq_config.json'
        config_file.write_text(
            '{"VeloxQAPIConfig": {"token": "from-json"}}',
        )
        load_config(config_file)
        assert VeloxQAPIConfig.instance().token == 'from-json'

    def test_none_reads_environment(self, monkeypatch):
        monkeypatch.setenv('VELOXQ_API_URL', 'https://env.test')
        monkeypatch.setenv('VELOX_TOKEN', 'env-token')
        load_config()
        config = VeloxQAPIConfig.instance()
        assert config.url == 'https://env.test'
        assert config.token == 'env-token'

    def test_unsupported_type_raises(self):
        with pytest.raises(TypeError, match='Unsupported config type'):
            load_config(42)

    def test_load_config_environ_prefix(self, monkeypatch):
        monkeypatch.setenv('VELOXQ_API_SDK__token', 'prefixed-token')
        config = VeloxQAPIConfig.instance()
        config.load_config_environ()
        assert config.token == 'prefixed-token'

    def test_load_config_environ_nested_section(self, monkeypatch):
        monkeypatch.setenv('VELOXQ_API_SDK__SubSection__key', 'nested-value')
        config = VeloxQAPIConfig.instance()
        config.load_config_environ()
        nested = config.config['VeloxQAPIConfig']['SubSection']['key']
        assert str(nested) == 'nested-value'

    def test_py_and_json_collision_prefers_json(self, tmp_path, caplog):
        (tmp_path / 'veloxq_config.py').write_text(
            'c = get_config()  # noqa\n'
            "c.VeloxQAPIConfig.token = 'from-py'\n",
        )
        (tmp_path / 'veloxq_config.json').write_text(
            '{"VeloxQAPIConfig": {"token": "from-json"}}',
        )
        load_config(tmp_path / 'veloxq_config.py')
        assert VeloxQAPIConfig.instance().token == 'from-json'
        assert any(
            'Collisions detected' in record.message
            for record in caplog.records
        )

    def test_broken_config_file_is_logged_and_skipped(self, tmp_path, caplog):
        (tmp_path / 'veloxq_config.py').write_text('raise RuntimeError("boom")\n')
        load_config(tmp_path / 'veloxq_config.py')
        assert any(
            'Exception while loading config file' in record.message
            for record in caplog.records
        )

    def test_broken_config_file_raises_when_configured(self, tmp_path):
        (tmp_path / 'veloxq_config.py').write_text('raise RuntimeError("boom")\n')
        config = VeloxQAPIConfig.instance()
        config.raise_config_file_errors = True
        with pytest.raises(RuntimeError, match='boom'):
            config.load_config_file(
                'veloxq_config.py', path=str(tmp_path),
            )


class TestGenerateConfigFile:
    def test_writes_all_configurable_traits(self, tmp_path: Path):
        target = tmp_path / 'generated_config.py'
        generate_py_config_file(target)
        text = target.read_text()
        for trait in ('token', 'url', 'multipart_upload_chunk_size'):
            assert f'c.VeloxQAPIConfig.{trait}' in text
