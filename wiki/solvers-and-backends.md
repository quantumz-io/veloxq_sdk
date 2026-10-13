# Selecting Solvers & Backends

## 1. Default Solver: VeloxQSolver

The primary solver in this package is `VeloxQSolver`. It inherits from a more generic `BaseSolver` class and comes preconfigured with:

- Default backend: `VeloxQH100_1` (representing an H100 GPU-based backend)
- Default parameters (see below)

Instantiation example:

```python
from veloxq_sdk import VeloxQSolver

solver = VeloxQSolver()
```

## 2. Setting Solver Parameters

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

## 3. SBM Solver

The `SBMSolver` is a specialized solver designed to submit jobs to the VeloxQ platform using the Simulated Bifurcation Machine (SBM) algorithm (Goto *et al.*). It inherits from the `BaseSolver` class and provides additional parameters specific to the SBM algorithm.

> For more information regarding the SBM implementation check the original work from Goto *et al.*:
>  - Hayato Goto et al., “Combinatorial optimization by simulating adiabatic bifurcations in nonlinear Hamiltonian systems”. Sci. Adv.5, eaav2372(2019). DOI:10.1126/sciadv.aav2372
>  - Hayato Goto et al., “High-performance combinatorial optimization based on classical mechanics”. Sci. Adv.7, eabe7953(2021). DOI:10.1126/sciadv.abe7953
>  - Kanao, T., Goto, H. “Simulated bifurcation assisted by thermal fluctuation”. Commun Phys 5, 153 (2022). https://doi.org/10.1038/s42005-022-00929-9

**Key Attributes:**

- **Backend:** Defaults to `VeloxQH100_1`, but can be changed to other available backends.
- **Parameters:** Includes standard parameters like `num_rep`, `num_steps`, as well as SBM-specific parameters like `discrete_version` and `dt`.

### 3.1 Instantiating the SBMSolver

```python
from veloxq_sdk import SBMSolver

solver = SBMSolver()
```

### 3.2 SBM Solver Parameters

The `SBMParameters` class extends `VeloxQParameters` and adds SBM-specific parameters:

- `discrete_version (bool)`: Whether to use the discrete version of the SBM algorithm. Defaults to `False`.
- `dt (float)`: The time step for the SBM algorithm, which affects convergence speed and stability. Defaults to `1.0`.

Example of configuring SBM-specific parameters:

```python
solver.parameters.discrete_version = True
solver.parameters.dt = 0.5
```

## 4. Backend Options

Two common backends included in this SDK:

- `VeloxQH100_1`: Single GPU
- `VeloxQH100_2`: Dual GPUs

You can override a solver’s backend:

```python
from veloxq_sdk import VeloxQH100_2

solver.backend = VeloxQH100_2()
```

## 5. Submitting a Model to a Solver

Every solver offers two entry points. `sample` is blocking: it creates the file, submits the job, waits for completion, and returns the result as a `VeloxSampleSet`. `submit` takes an existing `File` and returns the `Job` without waiting (see [Jobs](jobs.md#1-submitting-jobs)).

`sample` accepts the same inputs as `File.from_instance`: a file path, a `File`, a `(biases, couplings)` tuple, a dictionary with `"biases"` and `"couplings"` keys, keyword arguments `biases=` and `couplings=`, or a `dimod.BinaryQuadraticModel`. Its keyword arguments are:

- `vartype`: the variable domain of in-memory data, `"SPIN"` (Ising, the default) or `"BINARY"` (QUBO). A `BinaryQuadraticModel` is converted to this domain when it differs from its own. A file path or `File` keeps the domain stored in it, and `vartype` is ignored with a warning.
- `init_state`: an optional `dimod.SampleSet` of initial states in the model's domain.
- `name`, `problem`, `force`: file naming, grouping, and overwrite behavior, as in `File.from_instance`.

```python
import numpy as np
from veloxq_sdk import VeloxQSolver

solver = VeloxQSolver()

# Ising: spins in {-1, +1}
h = np.array([1.0, -1.0, 0.0])
J = np.array([[0, -1, 0], [-1, 0, -1], [0, -1, 0]])
result = solver.sample(h, J)
print(result.vartype)  # Vartype.SPIN

# QUBO: bits in {0, 1}
q = np.array([1.0, 1.0, 1.0])
Q = np.array([[0, -2, 0], [-2, 0, -2], [0, -2, 0]])
result = solver.sample(q, Q, vartype="BINARY")
print(result.vartype)  # Vartype.BINARY
print(result.first)    # Sample(sample={0: 1, 1: 1, 2: 1}, energy=-1.0, ...)
```

The result is in the submitted domain. To carry an energy offset with plain arrays, build the file first with `File.from_ising(...)` or `File.from_qubo(...)` and pass it to `sample` or `submit`. See [Variable Domain and Offset](problems-and-files.md#24-variable-domain-and-offset-ising-and-qubo).
