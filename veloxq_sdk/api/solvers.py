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
    """Base class for all solvers."""

    parameters: VeloxQParameters
    backend: BaseBackend

    def solve(self,
        instance: InstanceLike,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        force: bool = False,
    ) -> JobResult:
        """Solve a problem instance using the solver."""
        file = File.from_instance(instance, name=name, problem=problem, force=force)
        job = self.submit(file)
        job.wait_for_completion()
        return job.result

    def submit(self, file: File) -> Job:
        """Submit a file to the solver."""
        job_body = {
            'problemId': file.problem.id,
            'solvers': [{
                'solverId': self.id,
                'backendId': self.backend.id,
                'files': [ { 'fileId': file.id } ],
                'parameters': self.parameters.model_dump(
                    mode='json', by_alias=True, exclude_unset=True,
                ),
            }],
        }
        result = self.http.post('jobs', json=job_body)
        return Job._from_response(result)[0]  # noqa: SLF001 # type: ignore[return-value]


class VeloxQParameters(PydanticBaseModel):
    """Parameters for the VeloxQ solver."""

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


class VeloxQ(BaseSolver):
    """The VeloxQ solver."""

    _id = '3bce1dfa-e7af-4040-a283-67cff253cf94'

    backend: BaseBackend = Field(
        default=VeloxQH100_1(),
        description='The backend to use for the VeloxQ solver.',
    )

    parameters: VeloxQParameters = Field(
        VeloxQParameters(),
        description='Parameters for the VeloxQ solver.',
    )
