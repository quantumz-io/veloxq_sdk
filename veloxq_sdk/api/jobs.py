"""VeloxQ API Jobs Module.

This module provides classes and methods to manage jobs in the VeloxQ API. It includes
functionality for creating, retrieving, monitoring, and managing job results, logs, and
associated metadata.
"""
from __future__ import annotations

import json
import time
import typing as t
from datetime import datetime
from enum import Enum
from functools import cached_property
from pathlib import Path
from tempfile import gettempdir

import h5py
from pydantic import Field

from veloxq_sdk.api.core.base import BaseModel, BasePydanticModel


class LogCategory(Enum):
    """Enumerate all possible categories for job logs.

    Attributes:
        INFO (str): Informational messages.
        NOTICE (str): Notice messages.
        WARNING (str): Warning messages indicating potential issues.
        ERROR (str): Error messages for failed operations.
        CRITICAL (str): Critical errors needing immediate attention.
        PROGRESS (str): Progress messages to indicate status updates or stages.

    """

    INFO = 'INFO'
    NOTICE = 'NOTICE'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'
    PROGRESS = 'PROGRESS'


class PeriodFilter(Enum):
    """Enumerate possible date filters for retrieving jobs.

    Attributes:
        TODAY (str): Filter to today’s jobs.
        YESTERDAY (str): Filter to jobs created yesterday.
        LAST_WEEK (str): Filter to jobs created in the last week.
        LAST_MONTH (str): Filter to jobs created in the last month.
        LAST_3_MONTHS (str): Filter to jobs created in the last three months.
        LAST_YEAR (str): Filter to jobs created in the last year.
        ALL (str): No date filter (all jobs).

    """

    TODAY = 'today'
    YESTERDAY = 'yesterday'
    LAST_WEEK = 'lastWeek'
    LAST_MONTH = 'lastMonth'
    LAST_3_MONTHS = 'last3Months'
    LAST_YEAR = 'lastYear'
    ALL = 'all'


class TimePeriod(Enum):
    """Enumerate different time periods for filtering job logs.

    Attributes:
        allTime (str): No time filter, retrieves logs from all time.
        lastHour (str): Logs from the last hour.
        last12Hours (str): Logs from the last 12 hours.
        last24Hours (str): Logs from the last 24 hours.
        last3Days (str): Logs from the last three days.
        lastWeek (str): Logs from the last week.
        lastMonth (str): Logs from the last month.

    """

    ALL_TIME = 'allTime'
    LAST_HOUR = 'lastHour'
    LAST_12_HOURS = 'last12Hours'
    LAST_24_HOURS = 'last24Hours'
    LAST_3_DAYS = 'last3Days'
    LAST_WEEK = 'lastWeek'
    LAST_MONTH = 'lastMonth'


class JobStatus(Enum):
    """Enumerate job statuses.

    Attributes:
        CREATED (str): The job has been created but not yet queued or running.
        PENDING (str): The job is in line waiting to be processed.
        RUNNING (str): The job is actively being processed.
        COMPLETED (str): The job finished successfully.
        FAILED (str): The job encountered an error and did not complete successfully.

    """

    CREATED = 'created'
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


class JobResultType(Enum):
    """Enumerate result types for a job's outcome.

    Attributes:
        MATRIX (str): Indicates matrix-type result data.
        DEFAULT (str): Indicates a default or generic result type.
        PARALLEL_TEMPERING (str): Indicates a result produced by a parallel tempering method.

    """

    MATRIX = 'matrix'
    DEFAULT = 'default'
    PARALLEL_TEMPERING = 'parallelTempering'


class JobTimelineValue(BasePydanticModel):
    """Represents a single value on the job timeline.

    Attributes:
        name (JobStatus): Status name.
        value (Union[datetime, float]): Timestamp (if event time) or duration in hours (if aggregated).

    """

    name: JobStatus
    value: t.Union[datetime, float] = Field(description='Timestamp or duration in hours')


class JobStatistics(BasePydanticModel):
    """Statistical information about a job's execution.

    Attributes:
        usage_time (float): Amount of usage time in hours.
        pending_time (float): Time spent in pending state.
        running_time (float): Time spent running.
        total_cost (float): Total cost in dollars.
        solver_cost (float): The solver's hourly cost.
        backend_cost (float): The backend's hourly cost.
        total_backend_cost (float): The total backend cost in dollars.
        total_usage_cost (float): The total usage cost in dollars.

    """

    usage_time: float = Field(default=0.0, description='Usage time in hours')
    pending_time: float = Field(default=0.0, description='Pending time in hours')
    running_time: float = Field(default=0.0, description='Running time in hours')
    total_cost: float = Field(default=0.0, description='Total cost in dollars')
    solver_cost: float = Field(default=0.0, description='Backend cost per hour')
    backend_cost: float = Field(default=0.0, description='Backend cost per hour')
    total_backend_cost: float = Field(default=0.0, description='Total backend cost in dollars')
    total_usage_cost: float = Field(default=0.0, description='Total usage cost in dollars')


class JobResultDataItem(BasePydanticModel):
    """Data item within a job result metadata, including name, label, and values.

    Attributes:
        name (str): The data item's name.
        label (str): A human-readable label.
        values (List[Union[float, str]]): One or more data points.

    """

    name: str
    label: str
    values: t.List[t.Union[float, str]] = []


class JobResultData(BasePydanticModel):
    """metadata about the results of a job execution.

    Attributes:
        type (JobResultType): Indicator of how the result data is structured.
        items (List[JobResultDataItem]): A list of result data items.

    """

    type: JobResultType
    items: t.List[JobResultDataItem] = []


class JobParameterSchema(BasePydanticModel):
    """Schema for solver's paramteres used (name and value).

    Attributes:
        name (str): The parameter name.
        value (Any): The parameter value, which can be any serializable type.

    """

    name: str
    value: t.Any


class JobLogsRow(BasePydanticModel):
    """Represents a job log entry.

    Attributes:
        timestamp (Optional[datetime]): When the log entry was recorded.
        category (LogCategory): The category of the log message.
        message (str): The text of the log message.

    """

    timestamp: t.Optional[datetime] = None
    category: LogCategory
    message: str

    def __str__(self) -> str:
        return f'{self.timestamp} [{self.category}] {self.message}'


class Job(BaseModel):
    """A class representing a job in the VeloxQ API platform.

    Attributes:
        number (int): The job's short ID displayed (alias for 'shortId').
        created_at (datetime): The date/time when the job was created.
        updated_at (datetime): The date/time when the job was last updated.
        status (JobStatus): The current status of the job (e.g., RUNNING, COMPLETED).
        statistics (JobStatistics): Execution statistics (time usage, cost, etc.).
        timeline (List[JobTimelineValue]): A chronological list of status changes.
        result_metadata (Optional[JobResultData]): Metadata about job results if available.

    """

    number: int = Field(alias='shortId', description='The job number.')
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
    timeline: t.List[JobTimelineValue] = Field(
        default_factory=list,
        description='Timeline of the job status changes.',
    )
    result_metadata: t.Optional[JobResultData] = Field(
        alias='results',
        default=None,
        description='Metadata about the results of the job execution.',
    )

    def wait_for_completion(self, timeout: float | None = None) -> None:
        """Wait for the job to complete.

        Args:
            timeout (float | None): Maximum time in seconds to wait for completion.
                                    If None, wait indefinitely.

        Raises:
            TimeoutError: If the job does not complete by 'timeout' seconds.

        """
        start_time = time.monotonic()
        with self.http.open_ws(f'jobs/{self.id}/status-updates') as ws:
            waiting = True
            while waiting:
                if timeout and (time.monotonic() - start_time) > timeout:
                    msg = (
                        f'Waiting for Job {self.id} completion timed '
                        f'out after {timeout} seconds.'
                    )
                    raise TimeoutError(msg)
                message = json.loads(ws.recv())
                waiting = not message['finished']
        self.refresh()

    def get_job_logs(
        self,
        category: LogCategory | None = None,
        time_period: TimePeriod = TimePeriod.ALL_TIME,
        msg: str | None = None,
    ) -> list[JobLogsRow]:
        """Retrieve the logs of this job.

        Args:
            category (LogCategory | None): If provided, filters logs by this category.
            time_period (TimePeriod): Restricts logs to a specific time window (default ALL_TIME).
            msg (str | None): If provided, filters logs by message substring.

        Returns:
            list[JobLogsRow]: The job's logs matching the filters.

        Usage:
            ```python
            job = Job.from_id('job123')
            logs = job.get_job_logs(category=LogCategory.ERROR, time_period=TimePeriod.LAST_HOUR)
            for log in logs:
                print(log)
            ```

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

    @cached_property
    def result(self) -> JobResult:
        """Get the result of the job.

        Returns:
            JobResult: The job's result accessor.

        Raises:
            RuntimeError: If the job status is not 'completed'.

        """
        self.refresh()
        if self.status != JobStatus.COMPLETED.value:
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
        """Get a list of jobs from the server.

        Args:
            status (JobStatus | None): Filter jobs by this status if provided.
            created_at (PeriodFilter | None): Filter jobs by creation date (TODAY, YESTERDAY, etc.).
            limit (int): Maximum number of jobs to return (default 1000).

        Returns:
            list[Job]: A list of Job objects matching the filters.

        """
        params: dict[str, int | str] = {'_page': 1, '_limit': limit}
        if status:
            params['status'] = status.value
        if created_at:
            params['createdAt'] = created_at.value

        response = cls._http.get('jobs', params=params)
        response.raise_for_status()
        data = response.json()['data']
        return [cls.model_validate(item) for item in data]

    @classmethod
    def from_id(cls, job_id: str) -> "Job":
        """Get a Job by its ID.

        Args:
            job_id (str): The ID of the job to retrieve.

        Returns:
            Job: The matching job object.

        """
        response = cls._http.get(f'jobs/{job_id}')
        response.raise_for_status()
        return cls.model_validate(response.json())


class JobResult(BaseModel):
    """Job result Accessor.

    Provides HDF5-based download and local caching for easy access.

    Usage for downloading:
        ```python
        job = Job.from_id('job123')
        result = job.result  # Access the job's result
        with open('result.hdf5', 'wb') as f:
            result.download(f)  # Download the result to a file
        ```
    Usage to access data directly:
        ```python
        job = Job.from_id('job123')
        # Access the energies from the result
        energies = job.result.data['Spectrum']['energies']
        plt.plot(np.asarray(energies))
        plt.show()
        ```
    """

    @property
    def data(self) -> h5py.File:
        """HDF5 result file object.

        Retrieve an opened HDF5 file containing the job's result.
        Downloads the file to a temporary location if not already cached.

        Returns:
            h5py.File: The results in HDF5 format.

        """
        if not hasattr(self, '_data'):
            self._data = h5py.File(self._get_tempfile(), 'r')
        return self._data

    def __del__(self) -> None:
        """Close the HDF5 file object if it exists."""
        if hasattr(self, '_data'):
            self._data.close()

    def _get_tempfile(self) -> Path:
        """Get the temporary file path for the job result.

        Return the local Path object pointing to the cached job result. If the file is
        missing or has zero length, the result is downloaded.

        Returns:
            Path: Cached HDF5 file containing the job's result.

        """
        temp_file = (Path(gettempdir()) / self.id).with_suffix('.hdf5')
        if temp_file.exists() and temp_file.stat().st_size > 0:
            return temp_file

        with temp_file.open('wb') as f:
            self.download(f)
        return temp_file

    def download(self, file: t.BinaryIO, chunk_size: int = 1024 * 1024) -> None:
        """Download the result.

        Args:
            file (t.BinaryIO): The destination file-like object to write the content to.
            chunk_size (int): The size (in bytes) of each chunk read from the response. 
                Default is 1 MB.

        """
        with self.http.stream(
            'GET',
            f'jobs/{self.id}/result/download',
            params={'type': 'hdf5'},
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes(chunk_size):
                file.write(chunk)
