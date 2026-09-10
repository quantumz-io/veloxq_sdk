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

"""Atomic tests for veloxq_sdk.api.jobs."""

import io
import json
import time

import h5py
import numpy as np
import pytest

from veloxq_sdk.api.jobs import (
    Job,
    JobLogsRow,
    JobStatus,
    LogCategory,
    PeriodFilter,
    TimePeriod,
    VeloxSampleSet,
)
from veloxq_sdk.api.problems import File


def job_json(job_id: str = 'j1', status: str = 'running', **overrides) -> dict:
    payload = {
        'id': job_id,
        'createdAt': '2026-01-01T00:00:00Z',
        'updatedAt': '2026-01-01T00:00:00Z',
        'status': status,
    }
    payload.update(overrides)
    return payload


def update_json(*, finished: bool, status: str = 'running', **overrides) -> dict:
    payload = {
        'finished': finished,
        'status': status,
        'statusMessage': 'Job ended' if finished else 'Job running',
        'updatedAt': '2026-01-02T03:04:05Z',
        'statistics': {'usage_time': 1.5, 'total_cost': 0.25},
        'timeline': [
            {'name': 'created', 'value': '2026-01-01T00:00:00Z'},
            {'name': 'running', 'value': 0.5},
        ],
    }
    payload.update(overrides)
    return payload


def make_job(status: str = 'running', **overrides) -> Job:
    return Job.model_validate(job_json(status=status, **overrides))


def write_result_h5(path, *, states, energies, metadata, labels=None, extra=None):
    with h5py.File(path, 'w') as hdf:
        spectrum = hdf.require_group('Spectrum')
        spectrum.create_dataset('states', data=np.asarray(states, dtype=np.int8))
        spectrum.create_dataset('energies', data=np.asarray(energies))
        spectrum.create_dataset('metadata', data=json.dumps(metadata))
        if labels is not None:
            spectrum.create_dataset('labels', data=labels)
        for key, value in (extra or {}).items():
            spectrum.create_dataset(key, data=value)


class TestJobModel:
    def test_validates_camel_payload_with_file(self):
        job = make_job(
            file={
                'id': 'f1',
                'name': 'inst.h5',
                'size': 10,
                'uploadedBytes': 10,
                'createdAt': '2026-01-01T00:00:00Z',
                'status': 'completed',
            },
        )
        assert isinstance(job.file, File)
        assert job.file.name == 'inst.h5'

    def test_file_defaults_to_none(self):
        assert make_job().file is None

    def test_status_stored_as_value(self):
        assert make_job(status='completed').status == (
            JobStatus.COMPLETED.value
        )

    def test_logs_row_str(self):
        row = JobLogsRow.model_validate(
            {'category': 'INFO', 'message': 'hello'},
        )
        assert '[LogCategory.INFO] hello' in str(row) or 'INFO' in str(row)


class TestWaitForCompletion:
    def test_terminal_status_skips_websocket(self, api_config, monkeypatch):
        from veloxq_sdk.api.core.http import RestClient

        def forbidden(self, path):
            msg = 'open_ws must not be called for a terminal job'
            raise AssertionError(msg)

        monkeypatch.setattr(RestClient, 'open_ws', forbidden)
        for status in ('completed', 'failed', 'canceled'):
            make_job(status=status).wait_for_completion()

    def test_waits_until_finished(self, api_config, ws_factory):
        from conftest import FakeWS

        ws = FakeWS([
            json.dumps(update_json(finished=False)).encode(),
            json.dumps(update_json(finished=True, status='completed')).encode(),
        ])
        paths = ws_factory(ws)

        job = make_job()
        job.wait_for_completion()
        assert job.status == 'completed'
        assert paths == ['jobs/j1/status-updates']
        assert ws.recv_calls == 2

    def test_refresh_updates_fields(self, api_config, ws_factory):
        from conftest import FakeWS

        ws_factory(FakeWS([
            json.dumps(
                update_json(
                    finished=True,
                    status='completed',
                    status_message='Job ended',
                ),
            ).encode(),
        ]))

        job = make_job()
        job.wait_for_completion(refresh=True)
        assert job.status == 'completed'
        assert job.status_message == 'Job ended'
        assert job.statistics.usage_time == 1.5
        assert job.statistics.total_cost == 0.25
        assert [entry.name for entry in job.timeline] == [
            JobStatus.CREATED.value, JobStatus.RUNNING.value,
        ]
        assert job.updated_at.year == 2026

    def test_timeout_raises(self, api_config, ws_factory):
        from conftest import FakeWS

        def slow_unfinished():
            time.sleep(0.05)
            return json.dumps(update_json(finished=False)).encode()

        ws_factory(FakeWS([slow_unfinished, slow_unfinished]))
        job = make_job()
        with pytest.raises(TimeoutError, match='timed out'):
            job.wait_for_completion(timeout=0.01)


class TestGetJobUpdates:
    def test_yields_updates_and_mutates_job(self, api_config, ws_factory):
        from conftest import FakeWS

        ws_factory(FakeWS([
            json.dumps(update_json(finished=False)).encode(),
            json.dumps(
                update_json(
                    finished=True,
                    status='completed',
                    status_message='done',
                ),
            ).encode(),
        ]))

        job = make_job()
        updates = list(job.get_job_updates())
        assert [u.finished for u in updates] == [False, True]
        assert job.status == 'completed'
        assert job.status_message == 'done'
        assert job.statistics.usage_time == 1.5

    def test_timeout_raises(self, api_config, ws_factory):
        from conftest import FakeWS

        def slow_unfinished():
            time.sleep(0.05)
            return json.dumps(update_json(finished=False)).encode()

        ws_factory(FakeWS([slow_unfinished, slow_unfinished]))
        job = make_job()
        with pytest.raises(TimeoutError, match='timed out'):
            list(job.get_job_updates(timeout=0.01))


class TestJobEndpoints:
    def test_get_job_logs_params_and_parsing(self, mock_api):
        mock_api.add('GET', '/jobs/j1/logs', json=[
            {
                'timestamp': '2026-01-01T00:00:00Z',
                'category': 'ERROR',
                'message': 'boom',
            },
        ])
        logs = make_job().get_job_logs(
            category=LogCategory.ERROR,
            time_period=TimePeriod.LAST_HOUR,
            msg='boom',
        )
        assert logs[0].message == 'boom'
        params = mock_api.calls('GET', '/jobs/j1/logs')[0].url.params
        assert params['category'] == 'ERROR'
        assert params['time_period'] == 'lastHour'
        assert params['q'] == 'boom'

    def test_get_result_metadata(self, mock_api):
        mock_api.add('GET', '/jobs/j1/result_metadata', json={
            'type': 'default',
            'items': [{'name': 'energy', 'label': 'Energy', 'values': [1.0]}],
        })
        metadata = make_job().get_result_metadata()
        assert metadata.type == 'default'
        assert metadata.items[0].name == 'energy'

    def test_refresh(self, mock_api):
        mock_api.add('GET', '/jobs/j1', json=job_json(status='completed'))
        job = make_job()
        job.refresh()
        assert job.status == 'completed'

    def test_refresh_id_mismatch_raises(self, mock_api):
        mock_api.add('GET', '/jobs/j1', json=job_json(job_id='other'))
        with pytest.raises(ValueError, match='ID mismatch'):
            make_job().refresh()

    def test_from_id(self, mock_api):
        mock_api.add('GET', '/jobs/j1', json=job_json())
        assert Job.from_id('j1').id == 'j1'

    def test_get_jobs_filters(self, mock_api):
        mock_api.add('GET', '/jobs', json={'data': [job_json()]})
        jobs = Job.get_jobs(
            status=JobStatus.COMPLETED,
            created_at=PeriodFilter.LAST_WEEK,
            limit=5,
        )
        assert jobs[0].id == 'j1'
        params = mock_api.calls('GET', '/jobs')[0].url.params
        assert params['status'] == 'completed'
        assert params['createdAt'] == 'lastWeek'
        assert params['_limit'] == '5'


class TestDownloadResult:
    def test_streams_to_file(self, mock_api):
        mock_api.add('GET', '/jobs/j1/result', text='"https://blob.test/res"')
        mock_api.add('GET', '/res', content=b'result-bytes')
        buffer = io.BytesIO()
        make_job(status='completed').download_result(buffer)
        assert buffer.getvalue() == b'result-bytes'

    def test_refreshes_then_fails_if_not_completed(self, mock_api):
        mock_api.add('GET', '/jobs/j1', json=job_json(status='running'))
        with pytest.raises(RuntimeError, match='not completed'):
            make_job().download_result(io.BytesIO())
        assert mock_api.calls('GET', '/jobs/j1')

    def test_refresh_to_completed_allows_download(self, mock_api):
        mock_api.add('GET', '/jobs/j1', json=job_json(status='completed'))
        mock_api.add('GET', '/jobs/j1/result', text='"https://blob.test/res"')
        mock_api.add('GET', '/res', content=b'ok')
        buffer = io.BytesIO()
        make_job(status='running').download_result(buffer)
        assert buffer.getvalue() == b'ok'

    def test_temp_result_downloads_once(self, mock_api, monkeypatch, tmp_path):
        monkeypatch.setattr(
            'veloxq_sdk.api.jobs.gettempdir', lambda: str(tmp_path),
        )
        mock_api.add('GET', '/jobs/j1/result', text='"https://blob.test/res"')
        mock_api.add('GET', '/res', content=b'cached')

        job = make_job(status='completed')
        first = job._get_temp_result()
        assert first.read_bytes() == b'cached'
        requests_after_first = len(mock_api.requests)
        second = job._get_temp_result()
        assert second == first
        assert len(mock_api.requests) == requests_after_first


class TestSaveResult:
    def test_copies_cached_file(self, monkeypatch, tmp_path):
        cached = tmp_path / 'cached.hdf5'
        cached.write_bytes(b'result-payload')
        monkeypatch.setattr(Job, '_get_temp_result', lambda self: cached)

        target = tmp_path / 'saved.h5'
        make_job(status='completed').save_result(target)
        assert target.read_bytes() == b'result-payload'


class TestVeloxSampleSet:
    def test_from_result_with_labels_and_extras(self, tmp_path):
        path = tmp_path / 'result.h5'
        write_result_h5(
            path,
            states=[[1, -1], [1, -1], [-1, 1]],
            energies=[-1.0, -1.0, -1.0],
            metadata={'solver': 'veloxq'},
            labels=['a', 'b'],
            extra={'truncated': 1},
        )
        with h5py.File(path, 'r') as hdf:
            sampleset = VeloxSampleSet.from_result(hdf)

        assert set(sampleset.variables) == {'a', 'b'}
        assert sampleset.info['solver'] == 'veloxq'
        assert sampleset.info['truncated'] == 1
        # duplicate states are aggregated
        assert len(sampleset) == 2
        assert sorted(sampleset.record.num_occurrences.tolist()) == [1, 2]

    def test_energy_and_sample_properties(self, tmp_path):
        path = tmp_path / 'result.h5'
        write_result_h5(
            path,
            states=[[1, -1]],
            energies=[-2.5],
            metadata={},
        )
        with h5py.File(path, 'r') as hdf:
            sampleset = VeloxSampleSet.from_result(hdf)
        assert sampleset.energy.tolist() == [-2.5]
        assert sampleset.sample.tolist() == [[1, -1]]

    def test_result_property_uses_cached_file(self, monkeypatch, tmp_path):
        path = tmp_path / 'result.h5'
        write_result_h5(
            path,
            states=[[1, -1]],
            energies=[-1.0],
            metadata={},
        )
        monkeypatch.setattr(Job, '_get_temp_result', lambda self: path)
        job = make_job(status='completed')
        assert job.result.energy.tolist() == [-1.0]
        # cached_property: second access does not re-read
        monkeypatch.setattr(
            Job,
            '_get_temp_result',
            lambda self: (_ for _ in ()).throw(AssertionError('re-read')),
        )
        assert job.result.energy.tolist() == [-1.0]
