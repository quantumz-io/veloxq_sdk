
import pytest

from veloxq_sdk.api.backends import (
    VeloxQH100_1,
    VeloxQH100_2,
)
from veloxq_sdk.api.jobs import Job
from veloxq_sdk.api.solvers import (
    SBMSolver,
    VeloxQSolver,
)
from veloxq_sdk.api.tests.data.instances import (
    INSTANCE_DIMOD,
    INSTANCES,
    check_result,
)


@pytest.mark.parametrize('solver', [VeloxQSolver, SBMSolver])
@pytest.mark.parametrize('backend', [VeloxQH100_1, VeloxQH100_2])
def test_solvers(solver, backend):
    solver_instance = solver(backend=backend)
    result = solver_instance.sample(INSTANCE_DIMOD)

    assert result.record.num_occurrences[0] == solver_instance.parameters.num_rep

    check_result(result)

    job = Job.from_id(result.info['job_id'])
    job.delete()


@pytest.mark.parametrize(
    'instance',
    INSTANCES,
)
def test_sample(instance):
    solver = VeloxQSolver()
    result = solver.sample(instance=instance)

    assert result.record.num_occurrences[0] == solver.parameters.num_rep

    check_result(result)

    job = Job.from_id(result.info['job_id'])
    job.delete()
