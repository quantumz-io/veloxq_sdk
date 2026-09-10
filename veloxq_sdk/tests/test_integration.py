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

"""Integration tests against the live VeloxQ API.

These tests need credentials and network access:

- ``VELOX_TOKEN`` (required): API token; without it the module is skipped.
- ``VELOXQ_API_URL`` (optional): overrides the default API URL.
- ``VELOXQ_SSL_NO_VERIFY`` (optional): set to any non-empty value to
  disable TLS verification (self-hosted deployments).

Every artifact created here carries a unique ``sdk-it-*`` name and is
deleted again in the same test.
"""

import io
import os
import uuid

import httpx
import numpy as np
import pytest

from veloxq_sdk.api.jobs import Job, JobStatus
from veloxq_sdk.api.problems import File
from veloxq_sdk.api.solvers import VeloxQParameters, VeloxQSolver
from veloxq_sdk.config import VeloxQAPIConfig

SOLVE_TIMEOUT = 600  # seconds to wait for a live job to complete

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get('VELOX_TOKEN'),
        reason='VELOX_TOKEN is not set',
    ),
]


@pytest.fixture(autouse=True)
def live_config() -> VeloxQAPIConfig:
    config = VeloxQAPIConfig.instance()
    config.token = os.environ['VELOX_TOKEN']
    if url := os.environ.get('VELOXQ_API_URL'):
        config.url = url
    if os.environ.get('VELOXQ_SSL_NO_VERIFY'):
        config.ssl_context = False
    return config


def unique_name(extension: str) -> str:
    return f'sdk-it-{uuid.uuid4().hex}.{extension}'


def delete_and_assert_gone(file: File) -> None:
    file.delete()
    with pytest.raises(httpx.HTTPStatusError):
        File.from_id(file.id)


class TestFileLifecycle:
    def test_websocket_upload_download_delete(self):
        payload = os.urandom(64 * 1024)
        file = File.from_io(io.BytesIO(payload), name=unique_name('txt'))
        try:
            assert file.size == len(payload)
            assert file.is_temporary

            downloaded = io.BytesIO()
            file.download(downloaded)
            assert downloaded.getvalue() == payload
        finally:
            delete_and_assert_gone(file)

    def test_direct_upload_download_delete(self, tmp_path):
        payload = os.urandom(64 * 1024)
        path = tmp_path / unique_name('txt')
        path.write_bytes(payload)

        file = File.from_path(path)
        try:
            assert file.size == len(payload)

            downloaded = io.BytesIO()
            file.download(downloaded)
            assert downloaded.getvalue() == payload
        finally:
            delete_and_assert_gone(file)

    def test_direct_chunked_upload_download_delete(self, live_config, tmp_path):
        # Force the multipart plan for a small payload.
        live_config.max_single_upload_size = 1024
        payload = os.urandom(64 * 1024)
        path = tmp_path / unique_name('txt')
        path.write_bytes(payload)

        uploader = File.create_direct(name=path.name, size=len(payload))
        assert isinstance(uploader, File._PreassignedChunkUploader)

        file = uploader.upload(path)
        try:
            downloaded = io.BytesIO()
            file.download(downloaded)
            assert downloaded.getvalue() == payload
        finally:
            delete_and_assert_gone(file)


class TestJobListing:
    def test_get_jobs_and_from_id_roundtrip(self):
        jobs = Job.get_jobs(limit=5)
        if not jobs:
            pytest.skip('account has no jobs to list')
        job = Job.from_id(jobs[0].id)
        assert job.id == jobs[0].id
        assert job.status in {status.value for status in JobStatus}


class TestResultMetadata:
    @pytest.mark.xfail(
        reason='the live jobs/{id}/result_metadata endpoint hangs until '
               'the client read timeout',
        strict=False,
        raises=httpx.ReadTimeout,
    )
    def test_result_metadata_of_completed_job(self):
        jobs = Job.get_jobs(status=JobStatus.COMPLETED, limit=1)
        if not jobs:
            pytest.skip('account has no completed jobs')
        metadata = jobs[0].get_result_metadata()
        assert metadata.items is not None


class TestSolveEndToEnd:
    def test_two_spin_antiferromagnet(self, tmp_path):
        # h = 0, J_01 = 1: the ground states are the two anti-aligned
        # configurations, whatever energy convention the solver uses.
        biases = np.zeros(2)
        couplings = np.array([[0.0, 1.0], [1.0, 0.0]])

        file = File.from_ising(biases, couplings, name=unique_name('h5'))
        try:
            solver = VeloxQSolver(
                parameters=VeloxQParameters(num_rep=128, num_steps=500),
            )
            job = solver.submit(file)
            job.wait_for_completion(timeout=SOLVE_TIMEOUT, refresh=True)

            assert job.status == JobStatus.COMPLETED.value
            assert job.statistics.usage_time >= 0
            assert job.timeline

            result = job.result
            assert len(result.energy) > 0
            best = result.first.sample
            spins = list(best.values())
            assert sorted(spins) == [-1, 1]

            logs = job.get_job_logs()
            assert isinstance(logs, list)

            result_path = tmp_path / 'result.h5'
            job.save_result(result_path)
            assert result_path.stat().st_size > 0
        finally:
            delete_and_assert_gone(file)
