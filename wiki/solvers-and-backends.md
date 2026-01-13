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
