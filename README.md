# VeloxQ SDK: README

This project provides a configurable Python API to interact with the VeloxQ platform, designed to provide users with a **powerful**, **robust** and **user-friendly** interface to upload and solve complex
optimization problems using an extensive list of physics-inspired and metaheuristic algorithms.

Find additional guides on configuration, jobs, solvers and result files in the [VeloxQ SDK Wiki](https://github.com/quantumz-io/veloxq_sdk/wiki).

---

## Installation & Setup

Install the VeloxQ API client as part of your Python environment. Ensure you have Python 3.8+:

```shell
pip install git+https://github.com/quantumz-io/veloxq_sdk.git
```

> **NOTE:** It is recomended to install this package in a dedicated python environment to prevent any dependency problems.

---

## Quickstart

Before executing any code from the API make sure that you have a proper **API key** configured. The easiest way to load the api key is using the environment variables:

```shell
export VELOX_TOKEN="12345678-90ab-cdef-1234-567890abcdef"
```

Then to solve your problem, the simplest approach is using `solver.sample(...)`, which:

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
