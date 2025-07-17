# VeloxQ SDK: Documentation & Usage Guide

This project provides a configurable Python client interface for submitting and managing quantum or classical computational jobs via the VeloxQ platform. Users can easily configure their environment, select solvers/backends, define problem instances in various formats, and retrieve results (including HDF5-based data). This guide covers usage from initial setup through job submission and retrieval.

---

## Table of Contents

- [VeloxQ SDK: Documentation \& Usage Guide](#veloxq-sdk-documentation--usage-guide)
  - [Table of Contents](#table-of-contents)
  - [1. Installation \& Setup](#1-installation--setup)
  - [2. Quickstart](#2-quickstart)
  - [3. Configuration](#3-configuration)
    - [3.1 Environment Variables](#31-environment-variables)
    - [3.2 File-Based Configuration](#32-file-based-configuration)
    - [3.3 Generating a Default Configuration](#33-generating-a-default-configuration)
    - [3.4 Live Updates to Configuration](#34-live-updates-to-configuration)
  - [4. Selecting Solvers \& Backends](#4-selecting-solvers--backends)
    - [4.1 Default Solver: VeloxQSolver](#41-default-solver-veloxqsolver)
    - [4.2 Setting Solver Parameters](#42-setting-solver-parameters)
    - [4.3 SBM Solver](#43-sbm-Solver)
    - [4.4 Backend Options](#44-backend-options)
  - [5. Defining Problems \& Files](#5-defining-problems--files)
    - [5.1 Managing Problems](#51-managing-problems)
    - [5.2 Creating Files from Different Sources](#52-creating-files-from-different-sources)
      - [5.2.1 From a Local File Path](#521-from-a-local-file-path)
      - [5.2.2 From Dictionaries of Biases and Couplings](#522-from-dictionaries-of-biases-and-couplings)
      - [5.2.3 From Biases and Couplings in Various Formats](#523-from-biases-and-couplings-in-various-formats)
      - [4.2.4 From Direct I/O Stream (In-Memory Data)](#424-from-direct-io-stream-in-memory-data)
      - [5.2.5 Using an Existing File Object](#525-using-an-existing-file-object)
    - [5.3 Uploading \& Overwriting Files](#53-uploading--overwriting-files)
    - [5.4 Associating with Problems](#54-associating-with-problems)
    - [5.5 Downloading Files](#55-downloading-files)
  - [6. Submitting Jobs](#6-submitting-jobs)
  - [7. Retrieving \& Managing Jobs](#7-retrieving--managing-jobs)
    - [7.1 Waiting for Completion](#71-waiting-for-completion)
    - [7.2 Listing Jobs](#72-listing-jobs)
      - [7.2.1 Filtering by Status or Creation Time](#721-filtering-by-status-or-creation-time)
    - [7.3 Retrieving Job by ID](#73-retrieving-job-by-id)
    - [7.4 Getting Job Logs](#74-getting-job-logs)
  - [8. Accessing Results](#8-accessing-results)
    - [8.1 Direct Access via `VeloxSampleSet`](#81-direct-access-via-veloxsampleset)
    - [8.2 Downloading the Result File](#82-downloading-the-result-file)

---

## 1. Installation & Setup

Install the VeloxQ API client as part of your Python environment. Ensure you have Python 3.8+:

```shell
git clone git@github.com:quantumz-io/veloxq_sdk.git
pip install .
```

---

## 2. Quickstart

The simplest approach is using `solver.sample(...)`, which:

1. Creates a `File` (see below) for your problem instance (biases and couplings defined as lists, NumPy arrays, dictionaries, file paths, etc.).
2. Automatically submits a job to the VeloxQ platform.
3. Waits until completion.
4. Returns the job result.

It accepts the same argument types as `File.from_instance`.

**Examples:**

**Submitting biases and couplings defined in memory:**

- **Using lists:**

  ```python
  from veloxq_sdk import VeloxQSolver

  solver = VeloxQSolver()

  biases = [1, -1, 0]
  couplings = [
      [0, -1, 0],
      [-1, 0, -1],
      [0, -1, 0]
  ]

  result = solver.sample(biases, couplings)  # Returns VeloxSampleSet object
  print(result)
  ```

- **Using NumPy arrays:**

  ```python
  import numpy as np
  from veloxq_sdk import VeloxQSolver

  solver = VeloxQSolver()

  biases = np.array([1, -1, 0])
  couplings = np.array([
      [0, -1, 0],
      [-1, 0, -1],
      [0, -1, 0]
  ])

  result = solver.sample(biases, couplings)
  print(result.first)  # get lowest energy/state
  ```

- **Using dictionaries (sparse data):**

  ```python
  from veloxq_sdk import VeloxQSolver

  solver = VeloxQSolver()

  biases = {0: 1.0, 2: -1.0}
  couplings = {(0, 1): -1.0, (1, 2): 0.5}

  result = solver.sample(biases=biases, couplings=couplings)
  print(result.energy)  # print energies
  ```

- **Using `dimod.BinaryQuadraticModel`**
  
  ```python
  import dimod
  from veloxq_sdk import VeloxQSolver

  bqm = dimod.BinaryQuadraticModel({0: 1.0, 2: -1.0}, {(0, 1): -1.0, (1, 2): 0.5}, 0, dimod.SPIN)
  solver = VeloxQSolver()
  result = solver.sample(bqm)
  print(result.sample)  # print all found states
  ```

**Submitting a problem defined in a file:**

```python
from veloxq_sdk import VeloxQSolver

solver = VeloxQSolver()

result = solver.sample("ising_model.h5")
print(result)
```

**Submitting an instance in dictionary format:**

```python
from veloxq_sdk import VeloxQSolver

solver = VeloxQSolver()

instance_data = {
    "biases": [1, -1],
    "couplings": [[0, -1], [-1, 0]]
}

result = solver.sample(instance_data)
print(result)
```

---

## 3. Configuration

The VeloxQ client uses a global singleton configuration via the `VeloxQAPIConfig` class. This configuration can be applied in three ways:

- **Environment variables**
- **File-based configuration (Python or JSON)**
- **Direct programmatic modifications**

Since `VeloxQAPIConfig` is a **singleton**, the entire Python process shares one configuration (URL, token, etc.). If you need multiple independent configurations, spawn multiple processes and configure each process individually.

> **Note:** The only configuration variable not set by default is the **token**. It **must be configured** for authentication on the VeloxQ API platform.

### 3.1 Environment Variables

Environment variables allow you to override configuration for the session. There are currently two variables:

- `VELOX_TOKEN`: Updates the token authentication.
- `VELOXQ_API_URL`: Updates the base URL used to connect to the API.

Example usage:

```shell
export VELOX_TOKEN="12345678-90ab-cdef-1234-567890abcdef"
```

When your Python code runs, these variables are automatically loaded. This configuration is used as the base, and extra configuration will be merged on top.

### 3.2 File-Based Configuration

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

### 3.3 Generating a Default Configuration

Developers can quickly generate a starter Python config file:

```python
from veloxq_sdk.config import generate_py_config_file

generate_py_config_file("veloxq_api_config.py")
```

The auto-generated file includes default attributes and docstrings for easy customization.

### 3.4 Live Updates to Configuration

Because the configuration is a singleton (`VeloxQAPIConfig`), changes are global to the running session. For example:

```python
from veloxq_sdk.config import VeloxQAPIConfig

api_config = VeloxQAPIConfig.instance()
api_config.token = "NEW_TOKEN_VALUE"
```

All subsequent calls to the VeloxQ API will reflect this change.

---

## 4. Selecting Solvers & Backends

### 4.1 Default Solver: VeloxQSolver

The primary solver in this package is `VeloxQSolver`. It inherits from a more generic `BaseSolver` class and comes preconfigured with:

- Default backend: `VeloxQH100_1` (representing an H100 GPU-based backend)
- Default parameters (see below)

Instantiation example:

```python
from veloxq_sdk import VeloxQSolver

solver = VeloxQSolver()
```

### 4.2 Setting Solver Parameters

`VeloxQParameters` defines:

- `num_rep` (default=4096) The number of repetitions to be executed.
- `num_steps` (default=5000) The number of steps to be executed.

Example:

**Configure after solver selected:**

```python
solver.parameters.num_rep = 2048
```

**Configure before selecting the solver:**

```python
params = VeloxQParameters(num_steps=4000)

solver1 = VeloxQSolver(parameters=params)
solver2 = VeloxQSolver(parameters=params, backend=VeloxQH100_2())
```

These parameters are transmitted to the VeloxQ API upon problem submission.

### 4.3 SBM Solver

The `SBMSolver` is a specialized solver designed to submit jobs to the VeloxQ platform using the Simulated Bifurcation Machine (SBM) algorithm (Goto *et al.*). It inherits from the `BaseSolver` class and provides additional parameters specific to the SBM algorithm.

> For more information regarding the SBM implementation check the original work from Goto *et al.*:
>  - Hayato Goto et al., “Combinatorial optimization by simulating adiabatic bifurcations in nonlinear Hamiltonian systems”. Sci. Adv.5, eaav2372(2019). DOI:10.1126/sciadv.aav2372
>  - Hayato Goto et al., “High-performance combinatorial optimization based on classical mechanics”. Sci. Adv.7, eabe7953(2021). DOI:10.1126/sciadv.abe7953
>  - Kanao, T., Goto, H. “Simulated bifurcation assisted by thermal fluctuation”. Commun Phys 5, 153 (2022). https://doi.org/10.1038/s42005-022-00929-9


**Key Attributes:**

- **Backend:** Defaults to `VeloxQH100_1`, but can be changed to other available backends.
- **Parameters:** Includes standard parameters like `num_rep`, `num_steps`, as well as SBM-specific parameters like `discrete_version` and `dt`.

#### 4.3.1 Instantiating the SBMSolver

```python
from veloxq_sdk import SBMSolver

solver = SBMSolver()
```

#### 4.3.2 SBM Solver Parameters

The `SBMParameters` class extends `VeloxQParameters` and adds SBM-specific parameters:

- `discrete_version (bool)`: Whether to use the discrete version of the SBM algorithm. Defaults to `False`.
- `dt (float)`: The time step for the SBM algorithm, which affects convergence speed and stability. Defaults to `1.0`.

Example of configuring SBM-specific parameters:

```python
solver.parameters.discrete_version = True
solver.parameters.dt = 0.5
```

### 4.4 Backend Options

Two common backends included in this SDK:

- `VeloxQH100_1`: Single GPU
- `VeloxQH100_2`: Dual GPUs

You can override a solver’s backend:

```python
from veloxq_sdk import VeloxQH100_2

solver.backend = VeloxQH100_2()
```

---

## 5. Defining Problems & Files

In VeloxQ, "problems" are logical groupings (e.g., "Experiment1" or "Undefined") that hold one or more "files." A "file" is the actual container for your data-for instance, Ising-model parameters, system configurations, or any other simulation input. This section describes how to manage these objects through the VeloxQ SDK.

### 5.1 Managing Problems

A `Problem` groups related files and can be created or retrieved by name:

1. **Create a new `Problem`:**

   ```python
   from veloxq_sdk.problems import Problem

   # Create a problem named "my_experiment":
   my_problem = Problem.create(name="my_experiment")
   print(my_problem.id, my_problem.name)
   ```

2. **Retrieve existing `Problem`s by name (supports partial match):**

   ```python
   problems = Problem.get_problems(name="my_experiment", limit=5)  # Filter problems containing name
   for p in problems:
       print(p.id, p.name)
   ```

3. **Access the default "undefined" `Problem`:**

   ```python
   default_problem = Problem.undefined()
   files = Problem.get_files(name="big_test", limit=5)  # Get files associated with problem
   print(files)
   ```

---

### 5.2 Creating Files from Different Sources

Files are where your actual data is stored. You can create them from several input types. Once a file is created and uploaded, it remains on the VeloxQ platform until deleted.

> **Note:** By default, if a file with the same name (within the same problem) already exists, the SDK will return that existing file unless you set `force=True` to overwrite it.

#### 5.2.1 From a Local File Path

Useful if you have an existing file in your filesystem (e.g., `.h5`, `.csv`, `.txt`, etc.).

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

#### 5.2.2 From Dictionaries of Biases and Couplings

Create a `File` directly from biases and couplings defined as dictionaries. This is especially useful for sparse Ising models.

```python
biases = {0: 1.0, 2: -1.0}  # Variable indices mapped to bias values
couplings = {(0, 1): -1.0, (1, 2): 0.5}  # Variable index pairs mapped to couplings values

file_obj = File.from_instance((biases, couplings), name="sparse_ising.h5")
```

Or using keyword arguments:

```python
file_obj = File.from_instance(biases=biases, couplings=couplings, name="sparse_ising.h5")
```

This internally generates a temporary HDF5 file and uploads it.

#### 5.2.3 From Biases and Couplings in Various Formats

You can create a `File` directly from `biases` and `couplings`. These can be provided as lists, NumPy arrays, or dictionaries.

**Example using lists:**

```python
biases = [1, 0, -2]
couplings = [
    [0,  1,  0],
    [1,  0, -1],
    [0, -1,  0]
]
file_obj = File.from_instance((biases, couplings))
```

**Example using NumPy arrays:**

```python
import numpy as np

biases = np.array([1, 0, -2])
couplings = np.array([
    [0,  1,  0],
    [1,  0, -1],
    [0, -1,  0]
])
file_obj = File.from_instance((biases, couplings))
```

**Example using dictionaries (sparse data):**

```python
biases = {0: 1.0, 2: -2.0}
couplings = {(0, 1): 1.0, (2, 1): -1.0}
file_obj = File.from_instance((biases, couplings))
```

Or using keyword arguments:

```python
file_obj = File.from_instance(biases=biases, couplings=couplings)
```

This internally generates a temporary HDF5 file and uploads it.

> **Note:**
> Accepted types for `biases` include:
> - List of floats
> - NumPy 1D arrays
> - Dictionaries mapping variable indices to floats
>
> Accepted types for `couplings` include:
> - List of lists (2D array) of floats
> - NumPy 2D arrays
> - Dictionaries mapping tuples of variable indices to floats

#### 4.2.4 From Direct I/O Stream (In-Memory Data)

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

#### 5.2.5 Using an Existing File Object

If you have already created/retrieved a `File` object, simply pass it directly:

```python
existing_file_obj = File.get_files(name="my_data.h5", limit=1)[0]
file_obj = File.from_instance(existing_file_obj)
# 'file_obj' points to the same underlying file
```

### 5.3 Uploading & Overwriting Files

Every method above that "creates" a `File` also performs an upload if the underlying data is not already in VeloxQ:

- When you call `from_instance(...)`, `from_path(...)`, `from_dict(...)`, etc., the file is uploaded automatically.
- If you re-use the same `name` without setting `force=True`, you’ll get the existing file object without uploading again.

**Example of explicitly forcing an overwrite:**

```python
file_obj = File.from_instance(
    "path/to/updated_data.csv",
    name="my_data.csv",
    force=True    # Force overwrite if "my_data.csv" already exists
)
```

### 5.4 Associating with Problems

To group files under a specific `Problem`, pass a `Problem` object to the creation method:

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

### 5.5 Downloading Files

1. **Retrieve a file by name:**

   ```python
   # Returns a list of matching files (max=5 in this example)
   file_list = File.get_files(name="my_data.csv", limit=5)
   for f in file_list:
       print(f.id, f.name, f.status, f.problem.name)
   ```

2. **Download the file content:**

   ```python
   # Suppose you have an existing File object
   with open("local_copy.h5", "wb") as outfile:
       file_obj.download(outfile)
   ```

---

## 6. Submitting Jobs

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

---

## 7. Retrieving & Managing Jobs

### 7.1 Waiting for Completion

If you have a `Job` object:

```python
job.wait_for_completion(timeout=300)  # 5 minutes
print(job.statistics)
```

Raises a `TimeoutError` if it doesn’t complete within the specified time.

### 7.2 Listing Jobs

Use `Job.get_jobs(...)` to obtain multiple jobs from the server:

```python
from veloxq_sdk.jobs import Job, JobStatus, PeriodFilter

jobs = Job.get_jobs(
    status=JobStatus.PENDING,
    created_at=PeriodFilter.TODAY,
    limit=50
)
```

#### 7.2.1 Filtering by Status or Creation Time

- `status` can be `CREATED`, `PENDING`, `RUNNING`, `COMPLETED`, or `FAILED`.
- `created_at` can be `TODAY`, `YESTERDAY`, `LAST_WEEK`, `LAST_MONTH`, `LAST_3_MONTHS`, `LAST_YEAR`, or `ALL`.

Returns up to `limit` jobs; default is 1000.

### 7.3 Retrieving Job by ID

If you know a job’s specific ID:

```python
job = Job.from_id("my_job_id_123")
print(job.status)
```

### 7.4 Getting Job Logs

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

---

## 8. Accessing Results

### 8.1 Direct Access via `VeloxSampleSet`

When a job completes, the `job.result` property returns a `VeloxSampleSet` object, which inherits all implementations from dimod's `SampleSet` class. A `SampleSet` object contains the samples and associated data, such as energies, variable values, and per-sample data.

> **Note:** See [dimod's documentation for `SampleSet`](https://docs.dwavequantum.com/en/latest/ocean/api_ref_dimod/sampleset.html#dimod.SampleSet>) for more information regarding extra usage and features.

#### Properties

- **`first`**: The lowest energy `Sample` object.

  **Example:**

  ```python
  print(job.result.first)  # lowest energy sample
  ```

- **`sample`**: A NumPy array containing the sample states. Each row corresponds to a sample, and each column corresponds to a variable.

  **Example:**

  ```python
  print(job.result.sample)  # Access the sample states
  ```

- **`energy`**: A NumPy array containing the energies of the samples. Each element corresponds to the energy of a sample.

  **Example:**

  ```python
  print(job.result.energy)  # Access the energies
  ```

- **`info`**: A dictionary containing additional information about the solver's result as a whole. This might include metadata such as timing information or solver-specific data.

  **Example:**

  ```python
  print(job.result.info)               # Additional information and metadata
  ```

#### Methods

- **`samples(n=None, sorted_by='energy')`**: Returns an iterable over the samples. By default, samples are returned in order of increasing energy.

  - **Parameters:**
    - `n` (int, optional): Maximum number of samples to return.
    - `sorted_by` (str or None, optional): Field to sort by. If `None`, samples are returned in record order.

  - **Example:**

    ```python
    for sample in job.result.samples():
        print(sample)
    ```

- **`data(fields=None, sorted_by='energy', name='Sample', reverse=False, sample_dict_cast=True, index=False)`**: Iterate over the data in the `SampleSet`, yielding named tuples containing the requested fields.

  - **Parameters:**
    - `fields` (list, optional): Fields to include in the yielded tuples. Defaults to all fields.
    - `sorted_by` (str or None, optional): Field to sort by.
    - `reverse` (bool, optional): If `True`, reverse the sort order.

  - **Example:**

    ```python
    for datum in job.result.data(['sample', 'energy']):
        print(datum.sample, datum.energy)
    ```

- **`filter(pred)`**: Return a new `SampleSet` containing only the samples for which the given predicate function returns `True`.

  - **Parameters:**
    - `pred`: A function that takes a data tuple and returns a boolean.

  - **Example:**

    ```python
    # Filter samples with energy less than -1.0
    filtered_sampleset = job.result.filter(lambda d: d.energy < -1.0)
    ```

- **`lowest(rtol=1.e-5, atol=1.e-8)`**: Return a new `SampleSet` containing only the samples with the lowest energy (within specified tolerances).

  - **Parameters:**
    - `rtol` (float, optional): Relative tolerance.
    - `atol` (float, optional): Absolute tolerance.

  - **Example:**

    ```python
    lowest_energy_samples = job.result.lowest()
    ```

- **`truncate(n, sorted_by='energy')`**: Create a new `SampleSet` containing at most `n` samples, sorted by the specified field.

  - **Parameters:**
    - `n` (int): Maximum number of samples.
    - `sorted_by` (str or None, optional): Field to sort by.

  - **Example:**

    ```python
    top_samples = job.result.truncate(10)
    ```

- **`to_pandas_dataframe(sample_column=False)`**: Convert the `SampleSet` to a Pandas DataFrame.

  - **Parameters:**
    - `sample_column` (bool, optional): If `True`, samples are stored as a single column of dictionaries.

  - **Example:**

    ```python
    df = job.result.to_pandas_dataframe()
    print(df.head())
    ```

---

**Example Usage:**

```python
# Accessing basic properties
print("Variables:", job.result.variables)
print("Variable type:", job.result.vartype)
print("Sample info:", job.result.info)

# get the lowest energy
lowest_sample = job.result.first
print("Lowest State:", lowest_sample)


# Filtering samples based on a condition
filtered_samples = job.result.filter(lambda d: d.energy < -1.0)

# Converting to a DataFrame for analysis
df = job.result.to_pandas_dataframe()
print(df.describe())
```

### 8.2 Downloading the Result File

To manually download to a custom location and access the hdf5 data.

```python
with open("my_results.hdf5", "wb") as f:
    job.download_result(f, chunk_size=1024*1024)

with h5py.File("my_result.hdf5", "r") as data:
    states = data["Spectrum/states"][:]
```

---
