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

"""Atomic tests for veloxq_sdk.api.solvers."""

import json

import pytest

from veloxq_sdk.api.backends import VeloxQH100_1, VeloxQH100_2
from veloxq_sdk.api.problems import File
from veloxq_sdk.api.solvers import (
    BaseSolver,
    SBMParameters,
    SBMSolver,
    VeloxQParameters,
    VeloxQSolver,
)

from .test_jobs import job_json
from .test_problems import file_json


class _FakeJob:
    def __init__(self):
        self.waited = False
        self.result = object()

    def wait_for_completion(self):
        self.waited = True


@pytest.fixture
def sample_probe(monkeypatch):
    """Capture what solver.sample forwards to File.from_instance/submit."""
    captured = {}

    def fake_from_instance(cls, instance, **kwargs):
        captured['instance'] = instance
        captured.update(kwargs)
        return 'the-file'

    fake_job = _FakeJob()

    def fake_submit(self, file):
        captured['submitted'] = file
        return fake_job

    monkeypatch.setattr(File, 'from_instance', classmethod(fake_from_instance))
    monkeypatch.setattr(BaseSolver, 'submit', fake_submit)
    captured['job'] = fake_job
    return captured


class TestSampleDispatch:
    def test_single_positional_instance(self, sample_probe):
        solver = VeloxQSolver()
        result = solver.sample('inst.h5', name='run')
        assert sample_probe['instance'] == 'inst.h5'
        assert sample_probe['name'] == 'run'
        assert sample_probe['submitted'] == 'the-file'
        assert sample_probe['job'].waited
        assert result is sample_probe['job'].result

    def test_two_positionals_become_tuple(self, sample_probe):
        VeloxQSolver().sample([1.0], [[0.0]])
        assert sample_probe['instance'] == ([1.0], [[0.0]])

    def test_kwargs_become_instance_dict(self, sample_probe):
        VeloxQSolver().sample(biases=[1.0], couplings=[[0.0]])
        assert sample_probe['instance'] == {
            'biases': [1.0], 'couplings': [[0.0]],
        }

    def test_three_positionals_raise(self, sample_probe):
        with pytest.raises(ValueError, match='1 or 2 positional arguments'):
            VeloxQSolver().sample(1, 2, 3)


class TestSubmit:
    def test_posts_job_body(self, mock_api):
        mock_api.add('POST', '/jobs', json=[job_json()])
        solver = VeloxQSolver(
            backend=VeloxQH100_2(),
            parameters=VeloxQParameters(num_rep=8, num_steps=100),
        )
        file = File.model_validate(file_json(problem_id='p1'))

        job = solver.submit(file)
        assert job.id == 'j1'

        body = json.loads(mock_api.calls('POST', '/jobs')[0].content)
        assert body['problemId'] == 'p1'
        (entry,) = body['solvers']
        assert entry['solverId'] == solver.id
        assert entry['backendId'] == VeloxQH100_2().id
        assert entry['files'] == [{'fileId': 'f1'}]
        assert entry['parameters'] == {'num_rep': 8, 'num_steps': 100}

    def test_temporary_file_submits_null_problem(self, mock_api):
        mock_api.add('POST', '/jobs', json=[job_json()])
        VeloxQSolver().submit(File.model_validate(file_json()))
        body = json.loads(mock_api.calls('POST', '/jobs')[0].content)
        assert body['problemId'] is None


class TestDefaults:
    def test_veloxq_solver_defaults(self):
        solver = VeloxQSolver()
        assert solver.backend.id == VeloxQH100_1().id
        assert solver.parameters.num_rep == 4096
        assert solver.parameters.num_steps == 5000

    def test_sbm_solver_defaults(self):
        solver = SBMSolver()
        assert solver.id != VeloxQSolver().id
        assert isinstance(solver.parameters, SBMParameters)
        assert solver.parameters.discrete_version is False
        assert solver.parameters.dt == 1.0

    def test_sbm_parameters_extend_veloxq_parameters(self):
        parameters = SBMParameters(num_rep=2, dt=0.5)
        dumped = parameters.model_dump(mode='json')
        assert dumped['num_rep'] == 2
        assert dumped['dt'] == 0.5
        assert 'discrete_version' in dumped
