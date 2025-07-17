
import pytest

from veloxq_sdk.api.backends import (
    VeloxQH100_1,
    VeloxQH100_2,
)
from veloxq_sdk.api.solvers import (
    SBMParameters,
    SBMSolver,
    VeloxQParameters,
    VeloxQSolver,
)
from veloxq_sdk.api.tests.data.instances import (
    INSTANCE_DIMOD,
    INSTANCES,
    check_result,
)


@pytest.mark.parametrize(('solver', 'parameter'), [
    (VeloxQSolver, VeloxQParameters(num_rep=10)),
    (SBMSolver, SBMParameters(num_rep=10)),
])
@pytest.mark.parametrize('backend', [VeloxQH100_1, VeloxQH100_2])
def test_solvers(solver, parameter, backend, problem):
    solver_instance = solver(parameter=parameter, backend=backend)
    result = solver_instance.sample(INSTANCE_DIMOD, problem=problem)

    assert result.record.num_occurrences[0] == solver_instance.parameters.num_rep

    check_result(result)

    job = Job.from_id(result.info['job_id'])
    job.delete()


@pytest.mark.parametrize(
    'instance',
    INSTANCES,
)
def test_sample(instance, problem):
    solver = VeloxQSolver(parameters=VeloxQParameters(num_rep=10))
    result = solver.sample(instance=instance, problem=problem)

    assert result.record.num_occurrences[0] == solver.parameters.num_rep

    check_result(result)

    job = Job.from_id(result.info['job_id'])
    job.delete()
