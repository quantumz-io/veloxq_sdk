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

"""Atomic tests for veloxq_sdk.api.problems."""

from __future__ import annotations

import hashlib
import io
import json

import h5py
import httpx
import numpy as np
import pytest
from dimod import BinaryQuadraticModel
from dimod.sampleset import SampleSet

from veloxq_sdk.api.problems import File, Problem, _is_azure_blob_url


def file_json(
    file_id: str = 'f1',
    name: str = 'data.h5',
    size: int = 10,
    uploaded_bytes: int = 0,
    problem_id: str | None = None,
    status: str = 'pending',
) -> dict:
    return {
        'id': file_id,
        'name': name,
        'size': size,
        'uploadedBytes': uploaded_bytes,
        'problemId': problem_id,
        'createdAt': '2026-01-01T00:00:00Z',
        'updatedAt': '2026-01-01T00:00:00Z',
        'status': status,
    }


def problem_json(problem_id: str = 'p1', name: str = 'prob') -> dict:
    return {
        'id': problem_id,
        'name': name,
        'createdAt': '2026-01-01T00:00:00Z',
        'updatedAt': '2026-01-01T00:00:00Z',
    }


FUTURE = '2099-01-01T00:00:00Z'
PAST = '2000-01-01T00:00:00Z'


def _ok_put(recorded: list):
    """A fake httpx.put that records calls and returns an ETagged 200."""

    def put(url, *, content=b'', headers=None, timeout=None):
        recorded.append(
            {'url': url, 'content': content, 'headers': headers or {}},
        )
        return httpx.Response(
            200,
            headers={'ETag': f'etag-{len(recorded)}'},
            request=httpx.Request('PUT', url),
        )

    return put


class TestNormalizeIsingInputs:
    def test_dict_inputs(self):
        normalized = File._normalize_ising_inputs(
            {'a': 1.0, 'b': -2.0}, {('a', 'b'): 0.5},
        )
        assert normalized['size'] == 2
        assert list(normalized['labels']) == ['a', 'b']
        assert normalized['biases'].tolist() == [1.0, -2.0]
        entries = set(
            zip(
                normalized['rows'].tolist(),
                normalized['cols'].tolist(),
                normalized['values'].tolist(),
            ),
        )
        assert entries == {(1, 2, 0.5), (2, 1, 0.5)}

    def test_array_inputs_extract_nonzeros(self):
        couplings = np.array([[0.0, 2.0], [2.0, 0.0]])
        normalized = File._normalize_ising_inputs([0.5, -0.5], couplings)
        entries = set(
            zip(normalized['rows'].tolist(), normalized['cols'].tolist()),
        )
        assert entries == {(1, 2), (2, 1)}

    def test_column_major_order(self):
        couplings = {('a', 'b'): 1.0, ('a', 'c'): 2.0, ('b', 'c'): 3.0}
        normalized = File._normalize_ising_inputs(
            {'a': 0, 'b': 0, 'c': 0}, couplings,
        )
        cols = normalized['cols'].tolist()
        rows = normalized['rows'].tolist()
        assert cols == sorted(cols)
        # within a column, rows ascend
        for c in set(cols):
            in_col = [r for r, cc in zip(rows, cols) if cc == c]
            assert in_col == sorted(in_col)

    def test_diagonal_key_forms(self):
        one_elem = File._normalize_ising_inputs({0: 0.0}, {(0,): 2.0})
        pair_elem = File._normalize_ising_inputs({0: 0.0}, {(0, 0): 2.0})
        for normalized in (one_elem, pair_elem):
            assert normalized['rows'].tolist() == [1]
            assert normalized['cols'].tolist() == [1]
            assert normalized['values'].tolist() == [2.0]

    def test_couplings_extend_biases_with_zeros(self):
        normalized = File._normalize_ising_inputs({}, {('x', 'y'): 1.0})
        assert normalized['size'] == 2
        assert normalized['biases'].tolist() == [0.0, 0.0]

    def test_symmetric_mismatch_raises(self):
        couplings = np.array([[0.0, 1.0], [2.0, 0.0]])
        with pytest.raises(ValueError, match='mismatched values'):
            File._normalize_ising_inputs([0.0, 0.0], couplings)

    def test_symmetric_duplicate_consistent_ok(self):
        normalized = File._normalize_ising_inputs(
            {0: 0.0, 1: 0.0}, {(0, 1): 1.0, (1, 0): 1.0},
        )
        assert len(normalized['values']) == 2

    def test_empty_instance_raises(self):
        with pytest.raises(ValueError, match='Empty instance'):
            File._normalize_ising_inputs({}, {})

    def test_bad_shapes_raise(self):
        with pytest.raises(TypeError, match='one-dimensional'):
            File._normalize_ising_inputs(np.zeros((2, 2)), {})
        with pytest.raises(TypeError, match='square'):
            File._normalize_ising_inputs([0.0], np.zeros((1, 2)))
        with pytest.raises(TypeError, match='Unsupported bias type'):
            File._normalize_ising_inputs('nope', {})
        with pytest.raises(TypeError, match='Unsupported coupling type'):
            File._normalize_ising_inputs({0: 1.0}, 'nope')

    def test_long_coupling_key_raises(self):
        with pytest.raises(ValueError, match='1 or 2 elements'):
            File._normalize_ising_inputs({0: 0.0}, {(0, 1, 2): 1.0})

    def test_offset_is_carried(self):
        normalized = File._normalize_ising_inputs({0: 1.0}, {}, offset=2.5)
        assert normalized['offset'] == 2.5

    def test_single_element_key_extends_biases(self):
        normalized = File._normalize_ising_inputs({}, {('z',): 1.0})
        assert list(normalized['labels']) == ['z']
        assert normalized['biases'].tolist() == [0.0]

    def test_select_shared_dtype_empty_defaults_to_float32(self):
        dtype = File._select_shared_dtype(
            np.array([]), np.array([]), integral=True,
        )
        assert dtype == np.dtype(np.float32)

    @pytest.mark.parametrize(
        ('biases', 'couplings', 'expected'),
        [
            ({0: 1, 1: 2}, {(0, 1): 3}, np.uint8),
            ({0: -1, 1: 2}, {(0, 1): 3}, np.int8),
            ({0: 1, 1: 300}, {(0, 1): 3}, np.uint16),
            ({0: 0.5, 1: 2.0}, {(0, 1): 3.0}, np.float32),
            ({0: 1e39, 1: 0.0}, {(0, 1): 1.0}, np.float64),
        ],
    )
    def test_shared_dtype_selection(self, biases, couplings, expected):
        normalized = File._normalize_ising_inputs(biases, couplings)
        assert normalized['values'].dtype == np.dtype(expected)
        assert normalized['biases'].dtype == np.dtype(expected)


class TestWriteIsingHdf5:
    def _write(self, tmp_path, biases, couplings, **kwargs):
        path = tmp_path / 'instance.h5'
        # h5py needs a read/write handle, like the NamedTemporaryFile used
        # in from_ising.
        with path.open('wb+') as f:
            File._write_ising_hdf5(f, biases, couplings, **kwargs)
        return path

    def test_sparse_layout(self, tmp_path):
        path = self._write(
            tmp_path, {'a': 1.0, 'b': -1.0}, {('a', 'b'): 0.5}, offset=1.5,
        )
        with h5py.File(path, 'r') as hdf:
            ising = hdf['Ising']
            assert ising.attrs['sparsity'] == 'sparse'
            assert ising.attrs['type'] == 'BinaryQuadraticModel'
            assert ising.attrs['var_type'] == 'SPIN'
            assert ising.attrs['offset'] == 1.5
            assert ising['L'][()] == 2
            assert ising['biases'][:].tolist() == [1.0, -1.0]
            assert [
                label.decode() if isinstance(label, bytes) else label
                for label in ising['labels'].asstr()[:]
            ] == ['a', 'b']
            couplings = ising['couplings']
            assert couplings.attrs['type'] == 'SparseMatrixCSC'
            assert couplings['dims'][:].tolist() == [2, 2]
            triplets = set(
                zip(
                    couplings['I'][:].tolist(),
                    couplings['J'][:].tolist(),
                    couplings['V'][:].tolist(),
                ),
            )
            assert triplets == {(1, 2, 0.5), (2, 1, 0.5)}

    def test_dense_layout(self, tmp_path):
        # 2x2 with both diagonals and the off-diagonal pair filled: no zeros.
        path = self._write(
            tmp_path,
            {0: 0.0, 1: 0.0},
            {(0, 0): 1.0, (1, 1): 2.0, (0, 1): 3.0},
        )
        with h5py.File(path, 'r') as hdf:
            ising = hdf['Ising']
            assert ising.attrs['sparsity'] == 'dense'
            dense = ising['couplings'][:]
            assert dense.tolist() == [[1.0, 3.0], [3.0, 2.0]]

    def test_init_state_spectrum(self, tmp_path):
        states = np.array([[1, -1], [-1, 1]], dtype=np.int8)
        init_state = SampleSet.from_samples(
            states, energy=[-1.0, -1.0], vartype='SPIN',
        )
        path = self._write(
            tmp_path,
            {0: 0.0, 1: 0.0},
            {(0, 1): 1.0},
            init_state=init_state,
        )
        with h5py.File(path, 'r') as hdf:
            spectrum = hdf['Spectrum']
            assert spectrum['L'][()] == 2
            assert spectrum['num_rep'][()] == 2
            assert spectrum['energies'].dtype == np.float32
            assert spectrum['states'].dtype == np.int8
            assert spectrum['states'][:].tolist() == states.tolist()

    def test_large_sparse_instance_is_chunked(self, tmp_path):
        # >1000 variables and triplets: biases, labels, and I/J/V get chunks.
        n = 1500
        chain = {(i, i + 1): 1.0 for i in range(n - 1)}
        path = self._write(tmp_path, np.zeros(n), chain)
        with h5py.File(path, 'r') as hdf:
            ising = hdf['Ising']
            assert ising.attrs['sparsity'] == 'sparse'
            for dataset in ('biases', 'labels'):
                assert ising[dataset].chunks is not None
            for dataset in ('I', 'J', 'V'):
                assert ising['couplings'][dataset].chunks is not None

    def test_large_dense_instance_is_chunked(self, tmp_path):
        # A fully-coupled instance with >1000 variables lands in the dense
        # branch with chunked storage.
        n = 1050
        path = self._write(tmp_path, np.zeros(n), np.ones((n, n)))
        with h5py.File(path, 'r') as hdf:
            ising = hdf['Ising']
            assert ising.attrs['sparsity'] == 'dense'
            assert ising['couplings'].chunks is not None

    def test_large_init_state_is_chunked(self, tmp_path):
        num_rep = 1500
        states = np.tile([1, -1], (num_rep, 1)).astype(np.int8)
        init_state = SampleSet.from_samples(
            states, energy=np.zeros(num_rep), vartype='SPIN',
        )
        path = self._write(
            tmp_path,
            {0: 0.0, 1: 0.0},
            {(0, 1): 1.0},
            init_state=init_state,
        )
        with h5py.File(path, 'r') as hdf:
            spectrum = hdf['Spectrum']
            assert spectrum['energies'].chunks is not None
            assert spectrum['states'].chunks is not None

    def test_init_state_size_mismatch_raises(self, tmp_path):
        init_state = SampleSet.from_samples(
            np.array([[1, -1, 1]], dtype=np.int8),
            energy=[0.0],
            vartype='SPIN',
        )
        with pytest.raises(TypeError, match='consistent size'):
            self._write(
                tmp_path,
                {0: 0.0, 1: 0.0},
                {(0, 1): 1.0},
                init_state=init_state,
            )


class TestHelpers:
    def test_create_hash_matches_sha256(self):
        payload = b'some content' * 100
        assert (
            File._create_hash(io.BytesIO(payload))
            == hashlib.sha256(payload).hexdigest()
        )

    @pytest.mark.parametrize(
        ('url', 'expected'),
        [
            ('https://acct.blob.core.windows.net/c/b', True),
            ('https://storage.googleapis.com/b', False),
            ('https://api.test/files', False),
        ],
    )
    def test_is_azure_blob_url(self, url, expected):
        assert _is_azure_blob_url(url) is expected

    def test_temporary_endpoint_selection(self):
        temp_file = File.model_validate(file_json())
        assert temp_file.is_temporary
        assert temp_file._direct_complete_endpoint == (
            '/files/f1/direct/complete'
        )
        owned = File.model_validate(file_json(problem_id='p1'))
        assert not owned.is_temporary
        assert owned._direct_complete_endpoint == (
            '/problems/p1/files/f1/direct/complete'
        )


class TestFileEndpoints:
    def test_create_temporary(self, mock_api):
        mock_api.add('POST', '/files/upload-request', json=file_json())
        file = File.create(name='data.h5', size=10)
        assert file.id == 'f1'
        request = mock_api.calls('POST', '/files/upload-request')[0]
        assert json.loads(request.content) == {
            'file_name': 'data.h5', 'size': 10, 'force': False,
        }

    def test_create_with_problem(self, mock_api):
        mock_api.add(
            'POST',
            '/problems/p1/files/upload-request',
            json=file_json(problem_id='p1'),
        )
        problem = Problem.model_validate(problem_json())
        file = File.create(name='data.h5', size=10, problem=problem)
        assert file.problem_id == 'p1'

    def test_create_direct_single(self, api_config, mock_api):
        mock_api.add(
            'POST',
            '/files/direct',
            json={
                'file': file_json(),
                'uploadUrl': 'https://blob.test/u',
                'expiresAt': FUTURE,
            },
        )
        uploader = File.create_direct(name='data.h5', size=10)
        assert isinstance(uploader, File._PreassignedUploader)
        request = mock_api.calls('POST', '/files/direct')[0]
        assert json.loads(request.content)['num_chunks'] == 0

    def test_create_direct_with_problem_endpoint(self, mock_api):
        mock_api.add(
            'POST',
            '/problems/p1/files/direct',
            json={
                'file': file_json(problem_id='p1'),
                'uploadUrl': 'https://blob.test/u',
                'expiresAt': FUTURE,
            },
        )
        problem = Problem.model_validate(problem_json())
        uploader = File.create_direct(name='data.h5', size=10, problem=problem)
        assert uploader.file.problem_id == 'p1'

    def test_create_direct_multipart_chunk_count(self, api_config, mock_api):
        api_config.max_single_upload_size = 16 * 1024 * 1024
        size = 40 * 1024 * 1024  # 40 MB: one full 32 MB chunk + remainder
        mock_api.add(
            'POST',
            '/files/direct',
            json={
                'file': file_json(size=size),
                'chunks': [
                    {
                        'partNumber': 1,
                        'uploadUrl': 'https://blob.test/c1',
                        'expiresAt': FUTURE,
                    },
                    {
                        'partNumber': 2,
                        'uploadUrl': 'https://blob.test/c2',
                        'expiresAt': FUTURE,
                    },
                ],
            },
        )
        uploader = File.create_direct(name='data.h5', size=size)
        assert isinstance(uploader, File._PreassignedChunkUploader)
        request = mock_api.calls('POST', '/files/direct')[0]
        assert json.loads(request.content)['num_chunks'] == 2

    def test_get_file_temporary_params_and_miss(self, mock_api):
        def handler(request):
            assert request.url.params['name'] == 'data.h5'
            assert request.url.params['no_problem'] == 'true'
            assert request.url.params['_limit'] == '1'
            return httpx.Response(200, json={'data': []})

        mock_api.add_handler('GET', '/files', handler)
        assert File.get_file('data.h5') is None

    def test_get_file_scoped_to_problem(self, mock_api):
        mock_api.add(
            'GET',
            '/problems/p1/files',
            json={'data': [file_json(problem_id='p1')]},
        )
        problem = Problem.model_validate(problem_json())
        file = File.get_file('data.h5', problem=problem)
        assert file is not None
        assert file.problem_id == 'p1'

    def test_get_files_exact_vs_query(self, mock_api):
        mock_api.add('GET', '/files', json={'data': []})
        File.get_files('data.h5', exact=True)
        File.get_files('data')
        exact_request, fuzzy_request = mock_api.calls('GET', '/files')
        assert exact_request.url.params['name'] == 'data.h5'
        assert 'q' not in exact_request.url.params
        assert fuzzy_request.url.params['q'] == 'data'
        assert 'name' not in fuzzy_request.url.params

    def test_from_id(self, mock_api):
        mock_api.add('GET', '/files/f1', json=file_json())
        assert File.from_id('f1').id == 'f1'

    def test_delete(self, mock_api):
        mock_api.add('DELETE', '/files/f1', json={})
        File.model_validate(file_json()).delete()
        assert mock_api.calls('DELETE', '/files/f1')

    def test_download_strips_quotes_and_streams(self, mock_api):
        mock_api.add(
            'GET', '/files/f1/download', text='"https://blob.test/payload"',
        )
        mock_api.add('GET', '/payload', content=b'abc123')
        buffer = io.BytesIO()
        File.model_validate(file_json()).download(buffer)
        assert buffer.getvalue() == b'abc123'

    def test_download_problem_file_endpoint(self, mock_api):
        mock_api.add('GET', '/problems/p1/files/f1', text='"https://blob.test/p"')
        mock_api.add('GET', '/p', content=b'x')
        buffer = io.BytesIO()
        File.model_validate(file_json(problem_id='p1')).download(buffer)
        assert buffer.getvalue() == b'x'


class TestWebSocketUpload:
    def test_upload_chunks_and_final_empty_frame(self, mock_api, ws_factory):
        from conftest import FakeWS

        ws = FakeWS()
        paths = ws_factory(ws)
        mock_api.add('GET', '/files/f1', json=file_json(uploaded_bytes=2500))

        seen = []
        file = File.model_validate(file_json(size=2500))
        file.upload(
            io.BytesIO(b'x' * 2500), chunk_size=1024, upload_callback=seen.append,
        )

        assert paths == ['files/f1/upload/ws']
        assert [len(chunk) for chunk in ws.sent] == [1024, 1024, 452, 0]
        assert ws.recv_calls == 3  # one ack per non-empty chunk
        assert sum(seen) == 2500
        assert file.uploaded_bytes == 2500  # refreshed from the API

    def test_upload_problem_file_endpoint(self, mock_api, ws_factory):
        from conftest import FakeWS

        paths = ws_factory(FakeWS())
        mock_api.add('GET', '/files/f1', json=file_json(problem_id='p1'))
        file = File.model_validate(file_json(problem_id='p1'))
        file.upload(io.BytesIO(b'x'))
        assert paths == ['problems/p1/files/f1/upload/ws']

    def test_upload_error_cancels_and_reraises(self, mock_api, ws_factory):
        from conftest import FakeWS

        class ExplodingWS(FakeWS):
            def send(self, data):
                msg = 'connection lost'
                raise RuntimeError(msg)

        ws_factory(ExplodingWS())
        mock_api.add('DELETE', '/files/f1/cancel', json={})
        mock_api.add('GET', '/files/f1', json=file_json(status='canceled'))

        file = File.model_validate(file_json())
        with pytest.raises(RuntimeError, match='connection lost'):
            file.upload(io.BytesIO(b'data'))
        assert mock_api.calls('DELETE', '/files/f1/cancel')
        assert file.status == 'canceled'

    def test_upload_error_survives_failed_cancel(
        self, mock_api, ws_factory, caplog,
    ):
        from conftest import FakeWS

        class ExplodingWS(FakeWS):
            def send(self, data):
                msg = 'connection lost'
                raise RuntimeError(msg)

        ws_factory(ExplodingWS())
        mock_api.add(
            'DELETE',
            '/files/f1/cancel',
            json={'message': 'cannot cancel'},
            status_code=500,
        )

        file = File.model_validate(file_json())
        # the original upload error propagates, not the cancel failure
        with pytest.raises(RuntimeError, match='connection lost'):
            file.upload(io.BytesIO(b'data'))
        assert any(
            'Failed to cancel upload' in record.message
            for record in caplog.records
        )


class TestDirectUpload:
    def _single_uploader(self, upload_url='https://blob.test/u', expires=FUTURE):
        return File._uploader.validate_python({
            'file': file_json(),
            'uploadUrl': upload_url,
            'expiresAt': expires,
        })

    def test_single_upload(self, mock_api, monkeypatch, tmp_path):
        puts = []
        monkeypatch.setattr(httpx, 'put', _ok_put(puts))
        mock_api.add(
            'POST',
            '/files/f1/direct/complete',
            json=file_json(uploaded_bytes=4, status='completed'),
        )
        path = tmp_path / 'payload.bin'
        path.write_bytes(b'data')

        seen = []
        uploader = self._single_uploader()
        file = uploader.upload(path, callback=seen.append)

        assert puts[0]['content'] == b'data'
        assert 'x-ms-blob-type' not in puts[0]['headers']
        assert seen == [4]
        assert file.status == 'completed'

    def test_single_upload_azure_header(self, mock_api, monkeypatch, tmp_path):
        puts = []
        monkeypatch.setattr(httpx, 'put', _ok_put(puts))
        mock_api.add('POST', '/files/f1/direct/complete', json=file_json())
        path = tmp_path / 'payload.bin'
        path.write_bytes(b'data')

        uploader = self._single_uploader(
            upload_url='https://acct.blob.core.windows.net/c/b',
        )
        uploader.upload(path)
        assert puts[0]['headers']['x-ms-blob-type'] == 'BlockBlob'

    def test_single_upload_expired_cancels(self, mock_api, monkeypatch, tmp_path):
        monkeypatch.setattr(httpx, 'put', _ok_put([]))
        mock_api.add('DELETE', '/files/f1/cancel', json={})
        mock_api.add('GET', '/files/f1', json=file_json(status='canceled'))
        path = tmp_path / 'payload.bin'
        path.write_bytes(b'data')

        uploader = self._single_uploader(expires=PAST)
        with pytest.raises(ValueError, match='expired'):
            uploader.upload(path)
        assert mock_api.calls('DELETE', '/files/f1/cancel')

    def _chunked_uploader(self, size, chunks):
        return File._uploader.validate_python({
            'file': file_json(size=size),
            'chunks': chunks,
        })

    def test_upload_part_offsets_and_etag(self, api_config, monkeypatch, tmp_path):
        chunk_size = 16 * 1024 * 1024
        api_config.multipart_upload_chunk_size = chunk_size
        size = chunk_size + 1024  # two parts: 16 MB + 1 KB
        path = tmp_path / 'payload.bin'
        payload = np.arange(size % 251, dtype=np.uint8).tobytes()
        path.write_bytes(b'a' * chunk_size + b'b' * 1024)
        del payload

        puts = []
        monkeypatch.setattr(httpx, 'put', _ok_put(puts))
        uploader = self._chunked_uploader(size, [
            {'partNumber': 1, 'uploadUrl': 'https://blob.test/c1', 'expiresAt': FUTURE},
            {'partNumber': 2, 'uploadUrl': 'https://blob.test/c2', 'expiresAt': FUTURE},
        ])

        part_1, len_1 = uploader.upload_part(path, uploader.chunks[0])
        part_2, len_2 = uploader.upload_part(path, uploader.chunks[1])

        assert (len_1, len_2) == (chunk_size, 1024)
        assert puts[0]['content'] == b'a' * chunk_size
        assert puts[1]['content'] == b'b' * 1024
        assert part_1 == {'part_number': 1, 'etag': 'etag-1'}
        assert part_2 == {'part_number': 2, 'etag': 'etag-2'}

    def test_upload_part_expired_raises(self, api_config, tmp_path):
        path = tmp_path / 'payload.bin'
        path.write_bytes(b'data')
        uploader = self._chunked_uploader(4, [
            {'partNumber': 1, 'uploadUrl': 'https://blob.test/c1', 'expiresAt': PAST},
        ])
        with pytest.raises(ValueError, match='expired'):
            uploader.upload_part(path, uploader.chunks[0])

    def test_chunked_upload_completes_with_parts(
        self, api_config, mock_api, monkeypatch, tmp_path,
    ):
        chunk_size = 16 * 1024 * 1024
        api_config.multipart_upload_chunk_size = chunk_size
        size = chunk_size + 512
        path = tmp_path / 'payload.bin'
        path.write_bytes(b'a' * chunk_size + b'b' * 512)

        puts = []
        monkeypatch.setattr(httpx, 'put', _ok_put(puts))
        mock_api.add(
            'POST',
            '/files/f1/direct/complete',
            json=file_json(size=size, uploaded_bytes=size, status='completed'),
        )
        uploader = self._chunked_uploader(size, [
            {'partNumber': 1, 'uploadUrl': 'https://blob.test/c1', 'expiresAt': FUTURE},
            {'partNumber': 2, 'uploadUrl': 'https://blob.test/c2', 'expiresAt': FUTURE},
        ])
        seen = []
        file = uploader.upload(path, callback=seen.append)

        assert sorted(seen) == [512, chunk_size]
        assert file.status == 'completed'
        complete = mock_api.calls('POST', '/files/f1/direct/complete')[0]
        parts = json.loads(complete.content)['parts']
        assert {p['part_number'] for p in parts} == {1, 2}

    def test_chunked_upload_error_cancels(
        self, api_config, mock_api, monkeypatch, tmp_path,
    ):
        def failing_put(url, **kwargs):
            msg = 'blob refused'
            raise ConnectionError(msg)

        monkeypatch.setattr(httpx, 'put', failing_put)
        mock_api.add('DELETE', '/files/f1/cancel', json={})
        mock_api.add('GET', '/files/f1', json=file_json(status='canceled'))
        path = tmp_path / 'payload.bin'
        path.write_bytes(b'data')

        uploader = self._chunked_uploader(4, [
            {'partNumber': 1, 'uploadUrl': 'https://blob.test/c1', 'expiresAt': FUTURE},
        ])
        with pytest.raises(ConnectionError, match='blob refused'):
            uploader.upload(path)
        assert mock_api.calls('DELETE', '/files/f1/cancel')


class TestFromConstructors:
    def test_from_instance_passthrough(self, api_config):
        file = File.model_validate(file_json())
        assert File.from_instance(file) is file

    def test_from_instance_dispatch(self, monkeypatch):
        calls = {}
        monkeypatch.setattr(
            File,
            'from_path',
            classmethod(lambda cls, **kw: calls.setdefault('path', kw)),
        )
        monkeypatch.setattr(
            File,
            'from_dict',
            classmethod(lambda cls, **kw: calls.setdefault('dict', kw)),
        )
        monkeypatch.setattr(
            File,
            'from_tuple',
            classmethod(lambda cls, **kw: calls.setdefault('tuple', kw)),
        )
        monkeypatch.setattr(
            File,
            'from_bqm',
            classmethod(lambda cls, **kw: calls.setdefault('bqm', kw)),
        )

        File.from_instance('some/path.h5')
        File.from_instance({'biases': [0.0], 'couplings': [[0.0]]})
        File.from_instance(([0.0], [[0.0]]))
        File.from_instance(BinaryQuadraticModel.from_ising({0: 1.0}, {}))
        assert set(calls) == {'path', 'dict', 'tuple', 'bqm'}
        assert calls['path']['path'] == 'some/path.h5'

    def test_from_instance_unsupported_type_raises(self):
        with pytest.raises(TypeError, match='Unsupported instance type'):
            File.from_instance(42)

    def test_from_instance_warns_when_init_state_is_dropped(
        self, monkeypatch, caplog,
    ):
        monkeypatch.setattr(
            File, 'from_path', classmethod(lambda cls, **kw: 'ignored'),
        )
        init_state = SampleSet.from_samples(
            np.array([[1]], dtype=np.int8), energy=[0.0], vartype='SPIN',
        )

        file = File.model_validate(file_json())
        assert File.from_instance(file, init_state=init_state) is file
        File.from_instance('inst.h5', init_state=init_state)
        dropped = [
            record.message
            for record in caplog.records
            if 'Cannot pass initial state' in record.message
        ]
        assert len(dropped) == 2

    def test_from_dict_and_tuple_forward_to_from_ising(self, monkeypatch):
        seen = []
        monkeypatch.setattr(
            File,
            'from_ising',
            classmethod(lambda cls, **kw: seen.append(kw)),
        )
        File.from_dict({'biases': [1.0], 'couplings': [[0.0]]})
        File.from_tuple(([2.0], [[0.0]]))
        assert seen[0]['biases'] == [1.0]
        assert seen[1]['biases'] == [2.0]

    def test_from_bqm_converts_to_spin_with_offset(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            File,
            'from_ising',
            classmethod(lambda cls, **kw: seen.update(kw)),
        )
        bqm = BinaryQuadraticModel.from_qubo({(0, 0): -1.0, (0, 1): 2.0})
        File.from_bqm(bqm)
        spin = bqm.spin
        assert seen['offset'] == spin.offset
        assert dict(seen['biases']) == dict(spin.linear)

    def test_from_path_missing_file_raises(self, api_config):
        with pytest.raises(FileNotFoundError):
            File.from_path('/does/not/exist.h5')

    def test_from_path_uploads_when_missing(self, mock_api, monkeypatch, tmp_path):
        puts = []
        monkeypatch.setattr(httpx, 'put', _ok_put(puts))
        path = tmp_path / 'data.h5'
        path.write_bytes(b'content')

        mock_api.add('GET', '/files', json={'data': []})
        mock_api.add(
            'POST',
            '/files/direct',
            json={
                'file': file_json(name='data.h5', size=7),
                'uploadUrl': 'https://blob.test/u',
                'expiresAt': FUTURE,
            },
        )
        mock_api.add(
            'POST',
            '/files/f1/direct/complete',
            json=file_json(name='data.h5', size=7, status='completed'),
        )

        file = File.from_path(path)
        assert file.status == 'completed'
        assert puts[0]['content'] == b'content'

    def test_from_path_returns_existing_file(self, mock_api, tmp_path):
        path = tmp_path / 'data.h5'
        path.write_bytes(b'content')
        mock_api.add('GET', '/files', json={'data': [file_json(name='data.h5')]})
        file = File.from_path(path)
        assert file.id == 'f1'
        # only the existence lookup, no upload initiation
        assert len(mock_api.requests) == 1

    def test_from_io_uses_hash_name_and_ws_upload(self, mock_api, ws_factory):
        from conftest import FakeWS

        payload = b'binary blob'
        digest = hashlib.sha256(payload).hexdigest()
        expected_name = f'{digest}.h5'

        mock_api.add('GET', '/files', json={'data': []})
        mock_api.add(
            'POST',
            '/files/upload-request',
            json=file_json(name=expected_name, size=len(payload)),
        )
        mock_api.add('GET', '/files/f1', json=file_json(name=expected_name))
        ws = FakeWS()
        ws_factory(ws)

        file = File.from_io(io.BytesIO(payload))
        create_request = mock_api.calls('POST', '/files/upload-request')[0]
        body = json.loads(create_request.content)
        assert body['file_name'] == expected_name
        assert body['size'] == len(payload)
        assert b''.join(ws.sent) == payload
        assert file.name == expected_name

    def test_from_io_appends_extension(self, mock_api, ws_factory):
        from conftest import FakeWS

        mock_api.add('GET', '/files', json={'data': []})
        mock_api.add(
            'POST', '/files/upload-request', json=file_json(name='raw.bin'),
        )
        mock_api.add('GET', '/files/f1', json=file_json(name='raw.bin'))
        ws_factory(FakeWS())

        File.from_io(io.BytesIO(b'x'), name='raw', extension='bin')
        body = json.loads(
            mock_api.calls('POST', '/files/upload-request')[0].content,
        )
        assert body['file_name'] == 'raw.bin'

    def test_from_io_returns_existing_file(self, mock_api):
        payload = b'known content'
        digest = hashlib.sha256(payload).hexdigest()
        existing = file_json(name=f'{digest}.h5')
        mock_api.add('GET', '/files', json={'data': [existing]})

        file = File.from_io(io.BytesIO(payload))
        assert file.name == f'{digest}.h5'
        # only the existence lookup, no create/upload
        assert len(mock_api.requests) == 1

    def test_from_ising_hash_named_file_short_circuits(self, mock_api):
        # No explicit name: the file is serialized, hash-named, found on the
        # server, and returned without any upload.
        def files_handler(request):
            name = request.url.params['name']
            return httpx.Response(
                200, json={'data': [file_json(name=name)]},
            )

        mock_api.add_handler('GET', '/files', files_handler)
        file = File.from_ising({'a': 1.0}, {})
        assert file.name.endswith('.h5')
        assert len(mock_api.requests) == 1

    def test_from_ising_normalizes_name_and_short_circuits(self, mock_api):
        mock_api.add(
            'GET', '/files', json={'data': [file_json(name='inst.h5')]},
        )
        file = File.from_ising([1.0, -1.0], [[0.0, 1.0], [1.0, 0.0]], name='inst.txt')
        assert file.name == 'inst.h5'
        lookup = mock_api.calls('GET', '/files')[0]
        assert lookup.url.params['name'] == 'inst.h5'
        assert len(mock_api.requests) == 1

    def test_from_ising_uploads_valid_hdf5(self, mock_api, monkeypatch):
        puts = []
        monkeypatch.setattr(httpx, 'put', _ok_put(puts))
        mock_api.add('GET', '/files', json={'data': []})

        def direct_handler(request):
            body = json.loads(request.content)
            return httpx.Response(200, json={
                'file': file_json(name=body['file_name'], size=body['size']),
                'uploadUrl': 'https://blob.test/u',
                'expiresAt': FUTURE,
            })

        mock_api.add_handler('POST', '/files/direct', direct_handler)
        mock_api.add(
            'POST',
            '/files/f1/direct/complete',
            json=file_json(status='completed'),
        )

        file = File.from_ising({'a': 1.0, 'b': -1.0}, {('a', 'b'): 0.5})
        assert file.status == 'completed'

        uploaded = puts[0]['content']
        with h5py.File(io.BytesIO(uploaded), 'r') as hdf:
            assert hdf['Ising']['L'][()] == 2
        # the generated name is the SHA-256 of the serialized HDF5 payload
        direct_body = json.loads(mock_api.calls('POST', '/files/direct')[0].content)
        assert direct_body['file_name'] == (
            hashlib.sha256(uploaded).hexdigest() + '.h5'
        )


class TestProblem:
    def test_create(self, mock_api):
        mock_api.add('POST', '/problems', json=problem_json())
        problem = Problem.create('prob')
        assert problem.name == 'prob'
        assert json.loads(
            mock_api.calls('POST', '/problems')[0].content,
        ) == {'name': 'prob'}

    def test_get_problems_query_param(self, mock_api):
        mock_api.add('GET', '/problems', json={'data': [problem_json()]})
        problems = Problem.get_problems(name='pro')
        assert problems[0].id == 'p1'
        assert mock_api.calls('GET', '/problems')[0].url.params['q'] == 'pro'

    def test_from_id(self, mock_api):
        mock_api.add('GET', '/problems/p1', json=problem_json())
        assert Problem.from_id('p1').id == 'p1'

    def test_get_files(self, mock_api):
        mock_api.add(
            'GET',
            '/problems/p1/files',
            json={'data': [file_json(problem_id='p1')]},
        )
        problem = Problem.model_validate(problem_json())
        files = problem.get_files(name='data.h5', exact=True)
        assert files[0].problem_id == 'p1'
        request = mock_api.calls('GET', '/problems/p1/files')[0]
        assert request.url.params['name'] == 'data.h5'

    def test_get_files_fuzzy_query_param(self, mock_api):
        mock_api.add('GET', '/problems/p1/files', json={'data': []})
        problem = Problem.model_validate(problem_json())
        problem.get_files(name='data')
        request = mock_api.calls('GET', '/problems/p1/files')[0]
        assert request.url.params['q'] == 'data'
        assert 'name' not in request.url.params

    def test_new_file(self, mock_api):
        mock_api.add(
            'POST',
            '/problems/p1/files/upload-request',
            json=file_json(problem_id='p1'),
        )
        problem = Problem.model_validate(problem_json())
        file = problem.new_file('data.h5', size=10)
        assert file.problem_id == 'p1'
