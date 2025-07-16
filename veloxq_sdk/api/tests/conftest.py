import typing as t

import pytest

from veloxq_sdk.api.problems import Problem, File
from veloxq_sdk.api.jobs import Job
from veloxq_sdk.api.solvers import VeloxQSolver

from veloxq_sdk.api.tests.data.instances import INSTANCE_DIMOD


@pytest.fixture
def problem():
    problem = Problem.create(name='test_problem')
    try:
        yield problem
    finally:
        problem.delete()


@pytest.fixture
def file(problem: Problem) -> t.Iterator[File]:
    file = File.from_instance(INSTANCE_DIMOD, problem=problem)
    try:
        yield file
    finally:
        file.delete()


@pytest.fixture
def job(file: File) -> t.Iterator[Job]:
    """Fixture to provide a Job instance for tests."""
    job = VeloxQSolver().submit(file)
    try:
        yield job
    finally:
        job.delete()
