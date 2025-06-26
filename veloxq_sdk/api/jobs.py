from __future__ import annotations

import json
import time
import typing as t
from datetime import datetime
from enum import Enum
from pathlib import Path
from tempfile import gettempdir

import h5py
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from veloxq_sdk.api.base import BaseModel


class LogCategory(Enum):
    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    PROGRESS = "PROGRESS"


class PeriodFilter(Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_WEEK = "lastWeek"
    LAST_MONTH = "lastMonth"
    LAST_3_MONTHS = "last3Months"
    LAST_YEAR = "lastYear"
    ALL = "all"


class TimePeriod(Enum):
    allTime = "allTime"
    lastHour = "lastHour"
    last12Hours = "last12Hours"
    last24Hours = "last24Hours"
    last3Days = "last3Days"
    lastWeek = "lastWeek"
    lastMonth = "lastMonth"


class JobStatus(Enum):
    """An enumeration representing the status of a job."""

    CREATED = 'created'
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


class JobResultType(Enum):
    MATRIX = "matrix"
    DEFAULT = "default"
    PARALLEL_TEMPERING = "parallelTempering"


class JobTimelineValue(PydanticBaseModel):
    name: JobStatus
    value: datetime | float


class JobStatistics(PydanticBaseModel):
    usage_time: float = Field(default=0.0, description="Usage time in hours")
    pending_time: float = Field(default=0.0, description="Pending time in hours")
    running_time: float = Field(default=0.0, description="Running time in hours")
    total_cost: float = Field(default=0.0, description="Total cost in dollars")
    solver_cost: float = Field(default=0.0, description="Backend cost per hour")
    backend_cost: float = Field(default=0.0, description="Backend cost per hour")
    total_backend_cost: float = Field(default=0.0, description="Total backend cost in dollars")
    total_usage_cost: float = Field(default=0.0, description="Total usage cost in dollars")


class JobResultDataItem(PydanticBaseModel):
    name: str
    label: str
    values: list[float | str] = []


class JobResultData(PydanticBaseModel):
    type: JobResultType
    items: list[JobResultDataItem] = []


class JobParameterSchema(PydanticBaseModel):
    name: str
    value: t.Any


class JobLogsRow(PydanticBaseModel):
    timestamp: datetime | None = None
    category: LogCategory
    message: str

    def __str__(self) -> str:
        return f'{self.timestamp} [{self.category.value}] {self.message}'


class Job(BaseModel):
    """A class representing a job in the VeloxQ API."""

    number: int = Field(alias='short_id', description='The job number.')
    created_at: datetime = Field(
        description='The date and time when the job was created.',
    )
    updated_at: datetime = Field(
        description='The date and time when the job was last updated.',
    )
    status: JobStatus = Field(
        description='The current status of the job.',
    )

    statistics: JobStatistics = Field(
        default_factory=JobStatistics,
        description='Statistics about the job execution.',
    )
    timeline: list[JobTimelineValue] = Field(
        default_factory=list,
        description='Timeline of the job status changes.',
    )
    results_statistics: t.Optional[JobResultData] = Field(
        alias='results',
        default=None,
        description='Statistics about the results of the job execution.',
    )

    def __str__(self) -> str:
        return f'Job(number={self.number}, status={self.status})'

    def wait_for_completion(self, timeout: float | None = None) -> None:
        """Wait for the job to complete.

        Args:
            timeout (float | None): The maximum time to wait for completion in seconds.
                If None, it will wait indefinitely.

        Raises:
            TimeoutError: If the job does not complete within the specified timeout.

        """
        start_time = time.monotonic()
        with self.http.open_ws(
            f'jobs/{self.id}/status-updates',
        ) as ws:
            waiting = True
            while waiting:
                if timeout and (time.monotonic() - start_time) > timeout:
                    msg = (f'Waiting for Job {self.id} completion timed'
                        f' out after {timeout} seconds.')
                    raise TimeoutError(msg)
                message = json.loads(ws.recv())
                waiting = not message['finished']

    def get_job_logs(
        self,
        category: LogCategory | None = None,
        time_period: TimePeriod = TimePeriod.allTime,
        msg: str | None = None,
    ) -> list[JobLogsRow]:
        """Get the logs of the job.

        Args:
            category (category | None): Filter logs by category.
            time_period (time_period): Filter logs by time period.
            msg (str | None): Filter logs by message content.

        Returns:
            list[JobLogsRow]: A list of log entries for the job.

        """
        params: dict[str, str] = {'time_period': time_period.value}
        if category:
            params['category'] = category.value
        if msg:
            params['q'] = msg

        response = self.http.get(f'jobs/{self.id}/logs', params=params)
        response.raise_for_status()
        data = response.json()
        return [JobLogsRow.model_validate(item) for item in data]

    @property
    def result(self) -> JobResult:
        """Get the result of the job.

        Returns:
            JobResult: The result of the job.

        Raises:
            ValueError: If the job has not completed successfully.

        """
        self.refresh()
        if self.status != 'completed':
            msg = f'Job {self.id} has not completed successfully.'
            raise RuntimeError(msg)

        return JobResult(id=self.id)

    def refresh(self) -> None:
        """Refresh the job data from the API."""
        self._update_from_response(self.http.get(f'jobs/{self.id}'))

    @classmethod
    def get_jobs(
        cls,
        status: JobStatus | None = None,
        created_at: PeriodFilter | None = None,
        limit: int = 1000,
    ) -> list[Job]:
        """Get all jobs.

        Args:
            status (JobStatus | None): Filter jobs by status.
            limit (int): Maximum number of jobs to return.

        Returns:
            list[Job]: A list of jobs.

        """
        params: dict[str, int | str] = {'_page': 1, '_limit': limit}
        if status:
            params['status'] = status.value
        if created_at:
            params['createdAt'] = created_at.value

        response = cls._http.get('jobs', params=params)
        response.raise_for_status()
        data = response.json()
        return [cls.model_validate(item) for item in data]

    @classmethod
    def from_id(cls, job_id: str) -> Job:
        """Get a job by its ID."""
        response = cls._http.get(f'jobs/{job_id}')
        response.raise_for_status()
        return cls.model_validate(response.json())


class JobResult(BaseModel):
    """A class representing the result of a job in the VeloxQ API."""

    @property
    def data(self) -> h5py.File:
        """Get the hdf5 opened file containing the job result."""
        if not hasattr(self, '_data'):
            self._data = h5py.File(self._get_tempfile(), 'r')

        return self._data

    def __del__(self) -> None:
        """Ensure the hdf5 file is closed when the instance is deleted."""
        if hasattr(self, '_data'):
            self._data.close()

    def _get_tempfile(self) -> Path:
        """Get the temporary file where the job result is stored.

        If the file does not exist or is empty, it will download the result.

        Returns:
            Path: The path to the temporary file containing the job result.

        """
        temp_file = (Path(gettempdir()) / self.id).with_suffix('.hdf5')
        if temp_file.exists() and temp_file.stat().st_size > 0:
            return temp_file

        with temp_file.open('wb') as f:
            self.download(f)

        return temp_file

    def download(self, file: t.BinaryIO, chunk_size: int = 1024*1024) -> None:
        """Download the result of the job to a file.

        Args:
            file (t.BinaryIO): The file to write the result to.
            chunk_size (int): The size of each chunk to read from the response.

        """
        with self.http.stream(
            'GET',
            f'jobs/{self.id}/result/download',
            params={'type': 'hdf5'},
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes(chunk_size):
                file.write(chunk)
