import tempfile
from pathlib import Path

import numpy as np
import pytest
from httpx import HTTPStatusError, codes

from veloxq_sdk.api.problems import File, Problem
from veloxq_sdk.api.tests.data.instances import (
    INSTANCE_DIMOD,
    INSTANCE_H5,
    INSTANCES,
    INSTANCES_DICT,
    INSTANCES_TUPLE,
    check_h5_file,
)


def test_create_delete_problem():
    problem_name = 'test_create_delete_problem'

    problem = Problem.create(name=problem_name)

    assert problem.name == problem_name

    problem.delete()

    with pytest.raises(HTTPStatusError,
                       check= lambda e: e.response.status_code == codes.NOT_FOUND):
        Problem.from_id(problem.id)


def test_create_file(problem):
    # Create a file associated with the test problem
    file_name = 'test_file.txt'
    file_size = 1024  # 1KB dummy size for the file
    file = File.create(name=file_name, size=file_size, problem=problem)

    assert file.name == file_name
    assert file.size == file_size

    exising_files = problem.get_files(name=file_name)
    assert len(exising_files) == 1
    assert file.id == exising_files[0].id

    file.delete()


def test_upload_download_file(problem):
    # Create a temporary file with random content
    file_content = np.random.default_rng().random(1024)  # 1KB of random bytes

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(file_content)

    file_name = 'uploaded_test_file.txt'

    uploaded_file = File.from_path(path=Path(temp_file.name),
                                    name=file_name,
                                    problem=problem)

    Path(temp_file.name).unlink()

    existing_files = problem.get_files(name=file_name)
    assert len(existing_files) == 1

    with tempfile.NamedTemporaryFile() as downloaded_file:
        uploaded_file.download(downloaded_file)  # type: ignore[arg-type]
        downloaded_file.seek(0)
        content = downloaded_file.read()
        assert content == file_content

    uploaded_file.delete()


def test_file_from_path(problem):
    file_instance = File.from_path(path=INSTANCE_H5,
                                   name='test_instance.h5',
                                   problem=problem)

    assert file_instance.name == 'test_instance.h5'
    assert file_instance.size == file_instance.uploaded_bytes == INSTANCE_H5.stat().st_size
    assert file_instance.status == 'completed'

    check_h5_file(file_instance)

    file_instance.delete()


def test_file_from_bqm(problem):
    file_instance = File.from_bqm(bqm=INSTANCE_DIMOD, problem=problem)

    assert file_instance.size == file_instance.uploaded_bytes
    assert file_instance.status == 'completed'

    check_h5_file(file_instance)

    file_instance.delete()


@pytest.mark.parametrize(
    ('biases', 'couplings'),
    INSTANCES_TUPLE,
)
def test_from_ising(biases, couplings, problem):
    file_instance = File.from_ising(biases=biases, couplings=couplings, problem=problem)

    check_h5_file(file_instance)

    file_instance.delete()


@pytest.mark.parametrize(
    'tuple',
    INSTANCES_TUPLE
)
def test_from_ising_tuple(tuple, problem):
    file_instance = File.from_tuple(tuple, problem=problem)

    check_h5_file(file_instance)

    file_instance.delete()


@pytest.mark.parametrize(
    'dict',
    INSTANCES_DICT,
)
def test_from_instance_dict(dict, problem):
    file_instance = File.from_dict(data=dict, problem=problem)

    check_h5_file(file_instance)

    file_instance.delete()


@pytest.mark.parametrize(
    'instance',
    INSTANCES,
)
def test_from_instance(instance, problem):
    # force is false
    file_instance = File.from_instance(instance, problem=problem)

    check_h5_file(file_instance)

    # check that no duplicate file is created and no re-upload is done
    new_file_instance = File.from_instance(instance, problem=problem)
    assert new_file_instance.id == file_instance.id

    existing_files = problem.get_files()
    assert len(existing_files) == 1

    file_instance.delete()


