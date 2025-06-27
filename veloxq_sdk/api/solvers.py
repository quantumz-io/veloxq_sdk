"""VeloxQ API Solvers Module.

This module provides classes and methods for creating and managing solver instances
in the VeloxQ API. Solvers are responsible for submitting problem instances to a
specified backend, monitoring job execution, and finally retrieving results.

"""
from __future__ import annotations

import typing as t

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from veloxq_sdk.api.backends import BaseBackend, VeloxQH100_1
from veloxq_sdk.api.base import BaseModel
from veloxq_sdk.api.jobs import Job, JobResult
from veloxq_sdk.api.problems import File, Problem

if t.TYPE_CHECKING:
    from veloxq_sdk.api.problems import InstanceLike


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

    def solve(
        self,
        instance: InstanceLike,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        force: bool = False,
    ) -> JobResult:
        """Solve a problem instance using the solver.

        This method takes an instance of a problem (such as Ising model data or
        a local file), submits a job to the VeloxQ platform, waits for its completion,
        and finally returns the job result.

        Args:
            instance (InstanceLike):
                The problem representation, which can be:
                    - File object.
                    - file path (str or Path).
                    - dict following the InstanceDict specification.
                    - tuple of (biases, coupling).

            name (str | None):
                Optional name to assign to the file on the platform.

            problem (Problem | None):
                Optional Problem object. Uses "undefined" by default.

            force (bool):
                If True, overwrite any existing file with the same name.

        Returns:
            JobResult: An object that provides access to the completed job's results.

        Example:
            >>> solver = VeloxQSolver()
            >>> instance = {'biases': [1, -1], 'coupling': [[0, -1], [-1, 0]]}
            >>> result = solver.solve(instance)
            >>> print(result.data['Spectrum']['energies'][:])

        """
        file = File.from_instance(instance, name=name, problem=problem, force=force)
        job = self.submit(file)
        job.wait_for_completion()
        return job.result

    def submit(self, file: File) -> Job:
        """Submit a file to this solver on the VeloxQ platform.

        Args:
            file (File): The file representing the problem instance to be solved.

        Returns:
            Job: The submitted job object that can be monitored for status updates
            and queried for results.

        """
        job_body = {
            'problemId': file.problem.id,
            'solvers': [{
                'solverId': self.id,
                'backendId': self.backend.id,
                'files': [{'fileId': file.id}],
                'parameters': self.parameters.model_dump(
                    mode='json',
                ),
            }],
        }
        result = self.http.post('jobs', json=job_body)
        return Job._from_response(result)[0]  # noqa: SLF001 # type: ignore[return-value]


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
        default=10000,
        description='The number of steps to be executed.',
    )
    timeout: int = Field(
        default=30,
        description='The timeout for the solver in seconds.',
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
