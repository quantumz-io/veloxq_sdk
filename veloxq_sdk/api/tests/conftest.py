import typing as t
import uuid

import pytest
from httpx import HTTPStatusError

from veloxq_sdk.api.jobs import Job
from veloxq_sdk.api.problems import File, Problem
from veloxq_sdk.api.solvers import VeloxQParameters, VeloxQSolver
from veloxq_sdk.api.tests.data.instances import INSTANCE_DIMOD


@pytest.fixture(scope='session')
def session_id() -> str:
    """Fixture to provide a unique session ID for the test run."""
    return str(uuid.uuid4())


@pytest.fixture(scope='session')
def problem_files(session_id: str) -> t.Iterator[Problem]:
    problem = Problem.create(name=f'test_problem_files-{session_id}')
    try:
        yield problem
    finally:
        problem.delete()


@pytest.fixture(scope='session')
def problem(session_id: str) -> t.Iterator[Problem]:
    problem = Problem.create(name=f'test_problem_jobs-{session_id}')
    try:
        yield problem
    finally:
        problem.delete()


@pytest.fixture
def file() -> t.Iterator[File]:
    file = File.from_instance(INSTANCE_DIMOD)
    try:
        yield file
    finally:
        ...
        # file.delete()


@pytest.fixture
def job(file: File) -> t.Iterator[Job]:
    """Fixture to provide a Job instance for tests."""
    job = VeloxQSolver(parameters=VeloxQParameters(num_rep=100)).submit(file)
    try:
        yield job
    finally:
        ...
        # job.delete()
