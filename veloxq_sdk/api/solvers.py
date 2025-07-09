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
from veloxq_sdk.api.core.base import BaseModel
from veloxq_sdk.api.jobs import Job, JobResult
from veloxq_sdk.api.problems import File, Problem

if t.TYPE_CHECKING:
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

    @t.overload
    def sample(
        self,
        instance: InstanceLike,
        *,
        name: str | None = None,
        problem: Problem | None = None,
        force: bool = False,
    ) -> JobResult:
        """Solve a problem instance using the solver.

        This method takes an instance of a problem (such as Ising model data or
        a local file), submits a job to the VeloxQ platform, waits for its completion,
        and finally returns the job result.

        Args:
            instance (InstanceLike): An instance of a problem to be solved.
            name (str | None): Optional name for the job. Defaults to None.
            problem (Problem | None): Optional problem instance to use. Defaults to None.
            force (bool): If True, forces the creation of a new file even if it already exists.
                Defaults to False.

        Returns:
            JobResult: An object that provides access to the completed job's results.

        Example:
            >>> solver = VeloxQSolver()
            >>> result = solver.sample('problem_1.txt')
            >>> print(result.data['Spectrum']['energies'][:])

        """

    @t.overload
    def sample(
        self,
        biases: BiasesType,
        coupling: CouplingsType,
        *,
        name: str | None = None,
        problem: Problem | None = None,
        force: bool = False,
    ) -> JobResult:
        """Solve a problem instance using the solver.

        This method takes an instance of a problem (such as Ising model data or
        a local file), submits a job to the VeloxQ platform, waits for its completion,
        and finally returns the job result.

        Args:
            biases (BiasesType): Biases for the problem instance.
            coupling (CouplingsType): Coupling matrices for the problem instance.
            name (str | None): Optional name for the job. Defaults to None.
            problem (Problem | None): Optional problem instance to use. Defaults to None.
            force (bool): If True, forces the creation of a new file even if it already exists.
                Defaults to False.

        Returns:
            JobResult: An object that provides access to the completed job's results.

        Example:
            >>> solver = VeloxQSolver()
            >>> h = np.array([1, -1])
            >>> J = np.array([[0, -1], [-1, 0]])
            >>> result = solver.sample(h, J)
            >>> print(result.data['Spectrum']['energies'][:])

        """

    def sample(
        self,
        *args,
        name: str | None = None,
        problem: Problem | None = None,
        force: bool = False,
        **kwargs,
    ) -> JobResult:
        """Solve a problem instance using the solver.

        This method takes an instance of a problem (such as Ising model data or
        a local file), submits a job to the VeloxQ platform, waits for its completion,
        and finally returns the job result.

        Args:
            *args: Positional arguments that can be either an instance of `InstanceLike`
                or a tuple of biases and coupling matrices.
            name (str | None): Optional name for the job. Defaults to None.
            problem (Problem | None): Optional problem instance to use. Defaults to None.
            force (bool): If True, forces the creation of a new file even if it already exists.
                Defaults to False.
            **kwargs: Can receive coupling and biases as keyword arguments if not provided
                as positional arguments.

        Returns:
            JobResult: An object that provides access to the completed job's results.

        Example:
            >>> solver = VeloxQSolver()
            >>> instance = {'biases': [1, -1], 'coupling': [[0, -1], [-1, 0]]}
            >>> result = solver.sample(instance)
            >>> print(result.data['Spectrum']['energies'][:])

        """
        if len(args) == 1:
            instance = args[0]
        elif len(args) == 2:
            instance = args
        elif len(args) != 0:
            msg = f'Expected 1 or 2 positional arguments, got {len(args)}.'
            raise ValueError(msg)
        else:
            instance = kwargs

        file = File.from_instance(instance, name=name, problem=problem, force=force)  # type: ignore[arg-type]
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
