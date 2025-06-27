# VeloxQ SDK: Documentation & Usage Guide

This project provides a configurable Python client interface for submitting and managing quantum or classical computational jobs via the VeloxQ platform. Users can easily configure their environment, select solvers/backends, define problem instances in varying formats, and retrieve results (including HDF5-based data). This guide covers usage from initial setup through job submission and retrieval.

---

## Table of Contents

1. [Installation & Setup](#installation--setup)  
2. [Configuration](#configuration)  
   - 2.1 [Environment Variables](#environment-variables)  
   - 2.2 [File-Based Configuration](#file-based-configuration)  
   - 2.3 [Generating a Default Configuration](#generating-a-default-configuration)  
   - 2.4 [Live Updates to Configuration](#live-updates-to-configuration)  
3. [Selecting Solvers & Backends](#selecting-solvers--backends)  
   - 3.1 [Default Solver: VeloxQSolver](#default-solver-veloxqsolver)  
   - 3.2 [Backend Options](#backend-options)  
   - 3.3 [Setting Solver Parameters](#setting-solver-parameters)  
4. [Defining Problems & Files](#defining-problems--files)  
   - 4.1 [Couplings and Biases as Dictionaries/Tuples](#couplings-and-biases-as-dictionariestuples)  
   - 4.2 [Using Local/Remote Files](#using-localremote-files)  
5. [Submitting Jobs](#submitting-jobs)  
   - 5.1 [One-Line Solve Workflow](#one-line-solve-workflow)  
   - 5.2 [Separate Submission](#separate-submission)  
6. [Retrieving & Managing Jobs](#retrieving--managing-jobs)  
   - 6.1 [Waiting for Completion](#waiting-for-completion)  
   - 6.2 [Listing Jobs](#listing-jobs)  
     - 6.2.1 [Filtering by Status or Creation Time](#filtering-by-status-or-creation-time)  
   - 6.3 [Retrieving Job by ID](#retrieving-job-by-id)  
   - 6.4 [Getting Job Logs](#getting-job-logs)  
7. [Accessing Results](#accessing-results)  
   - 7.1 [Direct Access via HDF5](#direct-access-via-hdf5)  
   - 7.2 [Downloading the Result File](#downloading-the-result-file)  

---

## 1. Installation & Setup

Install the VeloxQ API client as part of your Python environment (details may vary). Ensure you have Python 3.8+:

```shell
pip install .
```

---

## 2. Configuration

The VeloxQ client uses a global singleton configuration (via the `VeloxQAPIConfig` class). This configuration can be applied in three ways:

- Environment variables  
- File-based configuration (Python or JSON)  
- Direct programmatic modifications  

Since `VeloxQAPIConfig` is a **singleton**, the entire Python process shares one configuration (URL, token, etc.). If you need multiple independent configurations, you should spawn multiple processes and configure each process individually.


### 2.1 Environment Variables

Environment variables allow you to override configuration on the fly. They must use an uppercased prefix. By default, the prefix is derived from the client name: `VELOXQ_API_SDK`.

Example usage:

```shell
export VELOXQ_API_SDK__token="12345678-90ab-cdef-1234-567890abcdef"
export VELOXQ_API_SDK__url="https://api.veloxq.com"
```

When your Python code runs, these variables are automatically loaded. Therefore, this configuration is use as base and extra configuration will be merged on top.

### 2.2 File-Based Configuration

It's possible to load configuration from files in Python or JSON format. For instance:

```python
from veloxq_sdk.config import load_config

# JSON:
load_config("path/to/config.json")

# Python:
load_config("path/to/config.py")
```

Within a `.py` configuration file, you typically define a `c` object:

```python
c = get_config()
c.VeloxQAPIConfig.token = "12345678-90ab-cdef-1234-567890abcdef"
```

### 2.3 Generating a Default Configuration

Entitled developers can quickly generate a starter Python config file:

```python
from veloxq_sdk.config import generate_py_config_file

generate_py_config_file("veloxq_api_config.py")
```

The auto-generated file includes default attributes and docstrings for easy customization.

### 2.4 Live Updates to Configuration

Because the configuration is a singleton (`VeloxQAPIConfig`), changes are global to the running session. For example:

```python
from veloxq_sdk.config import VeloxQAPIConfig

api_config = VeloxQAPIConfig.instance()
api_config.token = "NEW_TOKEN_VALUE"
```

All subsequent calls to the VeloxQ API will reflect this change.

---

## 3. Selecting Solvers & Backends

### 3.1 Default Solver: VeloxQSolver

The primary solver in this package is `VeloxQSolver`. It inherits from a more generic `BaseSolver` class and comes preconfigured with:

- Default backend: `VeloxQH100_1` (representing an H100 GPU-based backend)
- Default parameters (see below)

Instantiation example:

```python
from veloxq_sdk import VeloxQSolver

solver = VeloxQSolver()
```

### 3.2 Backend Options

Two common backends included in this SDK:
- `VeloxQH100_1`: Single GPU  
- `VeloxQH100_2`: Dual GPUs  

You can override a solver’s backend:

```python
from veloxq_sdk import VeloxQH100_2

solver.backend = VeloxQH100_2()
```

### 3.3 Setting Solver Parameters

`VeloxQParameters` defines:
- `num_rep` (default=4096)
- `num_steps` (default=10000)
- `timeout` (default=30 seconds)

Example:

1. Configure after solver selected

    ```python
    solver.parameters.num_rep = 2048
    solver.parameters.timeout = 45
    ```

2. Configure before selecting the solver

    ```python
    params = VeloxQParameters(timeout=4000)

    solver1 = VeloxQSolver(parameters=params)
    solver2 = VeloxQSolver(parameters=params, backend=VeloxQH100_2())
    ```

These parameters are transmitted to the VeloxQ API upon problem submission.

---

## 4. Defining Problems & Files

In VeloxQ, "problems" are logical groupings (e.g., "Experiment1" or "Undefined") that hold one or more "files." A "file" is the actual container for your data — for instance, Ising-model parameters, system configurations, or any other simulation input. This section describes how to manage these objects through the VeloxQ SDK.

### 4.1 Managing Problems

A Problem groups related files and can be created or retrieved by name:

1. Create a new Problem:
   ```python
   from veloxq_sdk.api.problems import Problem
   
   # Create a problem named "my_experiment":
   my_problem = Problem.create(name="my_experiment")
   print(my_problem.id, my_problem.name)
   ```
   
2. Retrieve existing Problems by name (supports partial match):
   ```python
   problems = Problem.get_problems(name="my_experiment", limit=5)  # filter problems containing name
   for p in problems:
       print(p.id, p.name)
   ```
   
3. Access the default "undefined" Problem (used when no specific problem is supplied):
   ```python
   default_problem = Problem.undefined()
   files = Problem.get_files(name="big_test", limit=5)  # get files associated with problem
   print(files)
   ```

---

### 4.2 Creating Files from Different Sources

Files are where your actual data is stored. You can create them from several input types.  
Once a file is created and uploaded, it remains on the VeloxQ platform until deleted.

> NOTE: By default, if a file with the same name (within the same problem) already exists, the SDK will return that existing file unless you set "force=True" to overwrite it.  

Below are common flows for creating a File:

1. From a local file path:  
   Useful if you have an existing file in your filesystem (e.g., ".h5," ".csv," ".txt," etc.).

   ```python
   from veloxq_sdk import File
   
   # Suppose "my_problem" is a Problem instance
   file_obj = File.from_instance(
       "path/to/local_data.h5",
       name="my_data.h5",        # Optional; defaults to the file’s basename
       problem=my_problem,       # Optional; defaults to Problem.undefined()
       force=True                # Overwrite if a file with the same name exists
   )
   ```
   
2. From a dictionary (e.g., small Ising-model biases/couplings):
   ```python
   instance_data = {
       "biases": [1, -1],
       "coupling": [
           [0, -1],
           [-1, 0]
       ]
   }
   file_obj = File.from_instance(instance_data)  # name is generated from a hash
   ```
   This internally generates a temporary HDF5 file and uploads it.

3. From a tuple (biases, couplings):
   ```python
   biases = [1, 0, -2]
   couplings = [
       [0,  1,  0],
       [1,  0, -1],
       [0, -1,  0]
   ]
   file_obj = File.from_instance((biases, couplings))
   ```

4. From direct I/O stream (in-memory data):
   ```python
   import io

   # Suppose 'buffer' is a BytesIO object containing HDF5 or CSV data
   buffer = io.BytesIO(b"...")  
   file_obj = File.from_io(
       data=buffer,
       name="uploaded_data.h5",  # Will automatically append .h5 if omitted
       problem=my_problem
   )
   ```

5. Using an existing File object:
   If you have already created/retrieved a File object, simply pass it directly:
   ```python
   existing_file_obj = File.get_files(name="my_data.h5", limit=1)[0]
   file_obj = File.from_instance(existing_file_obj)
   # 'file_obj' points to the same underlying file
   ```

### 4.3 Uploading & Overwriting Files

Every method above that "creates" a File also performs an upload if the underlying data is not already in VeloxQ:

• When you call from_path(…), from_dict(…), etc., the file is uploaded automatically.  
• If you re-use the same "name" without setting force=True, you’ll get the existing file object without uploading again.  

Example of explicitly forcing an overwrite:
```python
file_obj = File.from_instance(
    "path/to/updated_data.csv",
    name="my_data.csv",
    force=True    # Force overwrite if "my_data.csv" already exists
)
```

### 4.4 Associating with Problems

To group files under a specific Problem, pass a Problem object to the creation method:
```python
my_problem = Problem.create("Experiment_Batch5")

file_obj = File.from_instance(
    "path/to/local_data.csv",
    problem=my_problem
)
assert file_obj.problem.id == my_problem.id
```

Or alternately:

```python
my_problem = Problem.create("Experiment_Batch5")

file_obj = my_problem.new_file(
    name="big_ising.h5",
    size=300000
)
with open("big_ising.h5", "rb") as f:
    file_obj.upload(f)

assert file_obj.problem.id == my_problem.id
```

This ensures that retrieving files for "Experiment_Batch5" will include "local_data.csv".

### 4.5 Downloading Files

1. Retrieve a file by name:

```python
# Returns a list of matching files (max=5 in this example)
file_list = File.get_files(name="my_data.csv", limit=5)
for f in file_list:
    print(f.id, f.name, f.status, f.problem.name)
```

2. Download the file content:

```python
# Suppose you have an existing File object
with open("local_copy.h5", "wb") as outfile:
    file_obj.download(outfile)
```

---

## 5. Submitting Jobs

### 5.1 One-Line Solve Workflow

The simplest approach is using `solver.sample(...)`, which:
1. Creates a `File` for your instance (dict, path, etc.).  
2. Automatically submits a job to the VeloxQ platform.  
3. Waits until completion.  
4. Returns the job result.

It uses the same argument types as `File.from_instance`.

Example:

Submitting a problem defined in memory:
```python
solver = VeloxQSolver()

instance_data = {
  "biases": [1, -1],
  "coupling": [[0, -1], [-1, 0]]
}

result = solver.sample(instance_data)  # returns JobResult object
print(result.data["Spectrum"]["energies"][:])
```

Or a problem defined in a file:

```python
solver = VeloxQSolver()

result = solver.sample("ising_model.h5")
print(result.data["Spectrum"]["L"][:])
```

### 5.2 Separate Submission

If you prefer non-blocking usage:

```python
file_obj = File.from_instance("problem.txt")
job = solver.submit(file_obj)  # returns a job instance

job_id = job.id  # save for later
```

```python
job = Job.from_id(job_id)  # get job from id
job.wait_for_completion()
result = job.result  # get the JobResult object
```

---

## 6. Retrieving & Managing Jobs

### 6.1 Waiting for Completion

If you have a `Job` object:

```python
job.wait_for_completion(timeout=300)  # 5 minutes
print(job.statistics)
```

It raises a `TimeoutError` if it doesn’t complete within the specified seconds.

### 6.2 Listing Jobs

Use `Job.get_jobs(...)` to obtain multiple jobs from the server:

```python
from veloxq_sdk.api.jobs import Job, JobStatus, PeriodFilter

jobs = Job.get_jobs(
    status=JobStatus.PENDING,
    created_at=PeriodFilter.TODAY,
    limit=50
)
```

#### 6.2.1 Filtering by Status or Creation Time

- `status` can be `CREATED`, `PENDING`, `RUNNING`, `COMPLETED`, or `FAILED`.  
- `created_at` can be `TODAY`, `YESTERDAY`, `LAST_WEEK`, `LAST_MONTH`, `LAST_3_MONTHS`, `LAST_YEAR`, `ALL`.

Returns upward of `limit` jobs, default is 1000.

### 6.3 Retrieving Job by ID

If you know a job’s specific ID:

```python
job = Job.from_id("my_job_id_123")
print(job.status)
```

### 6.4 Getting Job Logs

Logs can be filtered by category, time period, or message substring:

```python
from veloxq_sdk.api.jobs import LogCategory, TimePeriod

logs = job.get_job_logs(
    category=LogCategory.ERROR,
    time_period=TimePeriod.LAST_24_HOURS
)

for entry in logs:
    print(f"[{entry.timestamp}] {entry.category}: {entry.message}")
```

---

## 7. Accessing Results

### 7.1 Direct Access via HDF5

Upon job completion, `job.result` is a `JobResult` object, automatically caching the HDF5 file in a temporary directory.

```python
h5f = job.result.data

energies = h5f["Spectrum"]["energies"][:]  # read into a NumPy array
print(energies)
```

### 7.2 Downloading the Result File

To manually download to a custom location:

```python
with open("my_results.hdf5", "wb") as f:
    job.result.download(f, chunk_size=1024*1024)
```
