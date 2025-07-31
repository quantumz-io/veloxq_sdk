import typing as t
import datetime as dt
from tempfile import TemporaryFile

from httpx import HTTPStatusError, codes
import h5py
import pytest


from veloxq_sdk.api.solvers import VeloxQSolver
from veloxq_sdk.api.jobs import Job, JobStatus, Job, PeriodFilter

from veloxq_sdk.api.tests.data.instances import check_result_h5


def test_job(job: Job) -> None:
    """Test the Job fixture."""
    assert job.id is not None
    assert job.status in {JobStatus.CREATED, JobStatus.PENDING, JobStatus.COMPLETED}

    # Check that the job can be refreshed
    job.wait_for_completion(timeout=3600)

    assert job.status == JobStatus.COMPLETED

    assert job.timeline[0].name == JobStatus.CREATED
    assert job.timeline[-1].name == JobStatus.COMPLETED

    assert job.created_at < job.updated_at < dt.datetime.now(tz=job.created_at.tzinfo)

    assert job.statistics.usage_time > 0
    assert job.statistics.pending_time >= 0
    assert job.statistics.running_time > 0
    assert job.statistics.total_cost > 0
    assert job.statistics.solver_cost > 0
    assert job.statistics.backend_cost > 0
    assert job.statistics.total_backend_cost > 0
    assert job.statistics.total_usage_cost > 0

    job_logs = job.get_job_logs()
    assert len(job_logs) > 0

    with TemporaryFile() as buffer:
        job.download_result(file=buffer)
        buffer.flush()
        buffer.seek(0)
        with h5py.File(buffer, 'r') as result_file:
            check_result_h5(result_file)


def test_get_jobs(file):
    """Test the get_jobs method."""
    timestamp = dt.datetime.now()
    job1 = VeloxQSolver().submit(file)
    job2 = VeloxQSolver().submit(file)

    assert job1.created_at > timestamp.astimezone(job1.created_at.tzinfo)
    assert job2.created_at > timestamp.astimezone(job2.created_at.tzinfo)

    jobs = Job.get_jobs(created_at=PeriodFilter.TODAY)

    current_jobs = list(filter(lambda j: j.id in {job1.id, job2.id}, jobs))
    assert len(current_jobs) == 2

    assert job1.id == Job.from_id(job1.id).id

    job1.wait_for_completion(timeout=3600)
    job2.wait_for_completion(timeout=3600)

    # job1.delete()
    # job2.delete()

    # with pytest.raises(HTTPStatusError, check=lambda e: e.response.status_code == codes.NOT_FOUND):
    #     Job.from_id(job1.id)

    # with pytest.raises(HTTPStatusError, check=lambda e: e.response.status_code == codes.NOT_FOUND):
    #     Job.from_id(job2.id)
