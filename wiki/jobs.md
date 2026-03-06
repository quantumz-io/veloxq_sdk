# Jobs

## 1. Submitting Jobs

If you prefer non-blocking usage:

```python
file_obj = File.from_instance("problem.txt")
job = solver.submit(file_obj)  # Returns a job instance

job_id = job.id  # Save for later
```

Later, you can retrieve and check the job:

```python
job = Job.from_id(job_id)  # Get job from ID
job.wait_for_completion()
result = job.result  # Get the VeloxSampleSet object
```

## 2. Retrieving & Managing Jobs

### 2.1 Waiting for Completion

If you have a `Job` object:

```python
job.wait_for_completion(timeout=300, refresh=True)  # refresh=True fetches latest metadata after finish
print(job.status)
print(job.statistics)
```

Raises a `TimeoutError` if it doesn’t complete within the specified time.

- `refresh=True` (default False) after the job finishes updates `status`, `statistics`, `timeline`, and `status_message`.
- Omit `timeout` to wait indefinitely.

### 2.2 Streaming Job Updates

Use `get_job_updates()` to receive real-time updates (via WebSocket) until the job finishes. The job object is kept in sync with each update.

```python
for update in job.get_job_updates(timeout=600):
    print(update.status, update.status_message)
    print(update.statistics)

print(job.status)       # job fields are updated in-place
print(job.timeline)
```

The generator stops automatically when the job completes. A `TimeoutError` is raised if `timeout` is exceeded.

### 2.3 Listing Jobs

Use `Job.get_jobs(...)` to obtain multiple jobs from the server:

```python
from veloxq_sdk.jobs import Job, JobStatus, PeriodFilter

jobs = Job.get_jobs(
    status=JobStatus.PENDING,
    created_at=PeriodFilter.TODAY,
    limit=50
)
```

#### 2.3.1 Filtering by Status or Creation Time

- `status` can be `CREATED`, `PENDING`, `RUNNING`, `COMPLETED`, or `FAILED`.
- `created_at` can be `TODAY`, `YESTERDAY`, `LAST_WEEK`, `LAST_MONTH`, `LAST_3_MONTHS`, `LAST_YEAR`, or `ALL`.

Returns up to `limit` jobs; default is 1000.

### 2.4 Retrieving Job by ID

If you know a job’s specific ID:

```python
job = Job.from_id("my_job_id_123")
print(job.status)
```

### 2.5 Getting Job Logs

Logs can be filtered by category, time period, or message substring:

```python
from veloxq_sdk.jobs import LogCategory, TimePeriod

logs = job.get_job_logs(
    category=LogCategory.ERROR,
    time_period=TimePeriod.LAST_24_HOURS
)

for entry in logs:
    print(f"[{entry.timestamp}] {entry.category}: {entry.message}")
```
