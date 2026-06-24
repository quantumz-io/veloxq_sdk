"""VeloxQ API Solvers Module.

This module provides classes and methods for creating and managing solver instances
in the VeloxQ API. Solvers are responsible for submitting problem instances to a
specified backend, monitoring job execution, and finally retrieving results.

"""
from __future__ import annotations

import typing as t

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from dimod import BinaryQuadraticModel, SampleSet

from veloxq_sdk.api.backends import BaseBackend, VeloxQH100_1
from veloxq_sdk.api.core.base import BaseModel
from veloxq_sdk.api.jobs import Job
from veloxq_sdk.api.problems import File, Problem

if t.TYPE_CHECKING:
    from veloxq_sdk.api.jobs import VeloxSampleSet
    from veloxq_sdk.api.problems import (
        BiasesType,
        CouplingsType,
        InstanceLike,
    )


class BaseSolver(BaseModel):
    """Base class for all solvers in the VeloxQ API.

    This class provides common functionality for solvers, including:
    - Storing solver parameters.
    - Storing the backend to be used.
    - Submitting problem instances and waiting for job completion.

    Attributes:
        parameters (VeloxQParameters): The parameter configuration for this solver.
        backend (BaseBackend): The backend instance to which the solver will submit jobs.

    """

    parameters: VeloxQParameters
    backend: BaseBackend

    def sample(
        self,
        bqm: BinaryQuadraticModel,
        init_state: SampleSet | None = None,
        **kwargs: t.Any,
    ) -> VeloxSampleSet:
        # file = File.from_instance(instance, name=name, problem=problem, init_state=init_state, force=force)  # type: ignore[arg-type]
        # job = self.submit(file)
        # job.wait_for_completion()
        spin = bqm.spin
        return Job.launch_ws(
            self.id,
            self.backend.id,
            spin.linear,
            spin.quadratic,
            self.parameters.model_dump(),
            init_state=init_state,
        )

    def submit(self, file: File) -> Job:
        """Submit a file to this solver on the VeloxQ platform.

        Args:
            file (File): The file representing the problem instance to be solved.

        Returns:
            Job: The submitted job object that can be monitored for status updates
            and queried for results.

        """
        job_body = {
            'problemId': file.problem_id,
            'solvers': [{
                'solverId': self.id,
                'backendId': self.backend.id,
                'files': [{'fileId': file.id}],
                'parameters': self.parameters.model_dump(
                    mode='json',
                ),
            }],
        }
        response = self.http.post('jobs', json=job_body)
        return Job._from_list_response(response)[0]


class VeloxQParameters(PydanticBaseModel):
    """Parameters for the VeloxQ solver.

    This model defines the configuration parameters used by the VeloxQ solver. These
    include the number of repetitions, the number of steps, and a timeout for solver
    execution.

    Attributes:
        num_rep (int): The number of repetitions to be executed.
        num_steps (int): The number of steps to be executed.
        timeout (int): The solver's timeout in seconds.

    """

    num_rep: int = Field(
        default=4096,
        description='The number of repetitions to be executed.',
    )
    num_steps: int = Field(
        default=5000,
        description='The number of steps to be executed.',
    )


class VeloxQSolver(BaseSolver):
    """A specialized solver using the VeloxQ.

    The `VeloxQSolver` class is designed to submit jobs to the VeloxQ platform
    using a specific backend. The solver parameters can be customized
    through the `VeloxQParameters` model.

    Attributes:
        id (str): A unique identifier for this solver on the VeloxQ platform.
        backend (BaseBackend): The backend to use for the VeloxQ solver. Defaults to `VeloxQH100_1`.
        parameters (VeloxQParameters): The parameters controlling solver execution.

    """

    id: str = '3bce1dfa-e7af-4040-a283-67cff253cf94'
    backend: BaseBackend = Field(
        default=VeloxQH100_1(),
        description='The backend to use for the VeloxQ solver.',
    )
    parameters: VeloxQParameters = Field(
        default_factory=VeloxQParameters,
        description='Parameters for the VeloxQ solver.',
    )


class SBMParameters(VeloxQParameters):
    """Parameters for the SBM solver.

    This model defines the configuration parameters used by the SBM solver.
    These include the number of repetitions, the number of steps, and a timeout for
    solver execution, as well as additional parameters specific to the SBM algorithm.

    Attributes:
        num_rep (int): The number of repetitions to be executed.
        num_steps (int): The number of steps to be executed.
        discrete_version (bool): Whether to use the discrete version of the SBM algorithm.
        dt (float): The time step for the SBM algorithm.

    """

    discrete_version: bool = Field(
        default=False,
        description='Whether to use the discrete version of the SBM algorithm for solving NP-hard problems.',
    )
    dt: float = Field(
        default=1.0,
        description='The time step for the SBM algorithm, which affects the convergence speed and stability of the solution for NP-hard problems.',
    )


class SBMSolver(BaseSolver):
    """A specialized solver for the SBM (Simulated Bifurcation Machine).

    The `SBMSolver` class is designed to submit jobs to the VeloxQ platform
    using a specific backend for solving with Simulated Bifurcation Machine algorithm.

    Attributes:
        id (str): A unique identifier for this solver on the VeloxQ platform.
        backend (BaseBackend): The backend to use for the VeloxQ SBM solver. Defaults to `VeloxQH100_1`.
        parameters (SBMParameters): The parameters controlling solver execution.

    """

    id: str = '524c60b7-424e-4e12-b155-d7b79a2bc007'
    backend: BaseBackend = Field(
        default=VeloxQH100_1(),
        description='The backend to use for the VeloxQ SBM solver.',
    )
    parameters: SBMParameters = Field(
        default_factory=SBMParameters,
        description='Parameters for the SBM solver.',
    )
