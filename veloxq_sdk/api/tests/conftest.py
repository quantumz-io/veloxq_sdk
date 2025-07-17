import typing as t

from httpx import HTTPStatusError
import pytest

from veloxq_sdk.api.problems import Problem, File
from veloxq_sdk.api.jobs import Job
from veloxq_sdk.api.solvers import VeloxQParameters, VeloxQSolver

from veloxq_sdk.api.tests.data.instances import INSTANCE_DIMOD


@pytest.fixture
def problem_files():
    try:
        problem = Problem.create(name='test_problem_files')
    except HTTPStatusError:
        problem = Problem.get_problems(name='test_problem_files')[0]
    try:
        yield problem
    finally:
        ...
        # problem.delete()


@pytest.fixture
def problem():
    try:
        problem = Problem.create(name='test_problem')
    except HTTPStatusError:
        problem = Problem.get_problems(name='test_problem')[0]
    try:
        yield problem
    finally:
        ...
        # problem.delete()


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
