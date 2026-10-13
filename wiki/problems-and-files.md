# Defining Problems & Files

## 1. Managing Problems

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

## 2. Creating Files from Different Sources

Files are where your actual data is stored. You can create them from several input types. Once a file is created and uploaded, it remains on the VeloxQ platform until deleted.

A file holds one binary quadratic model: linear terms (`biases`), quadratic terms (`couplings`), a variable domain, and a constant energy offset. The domain is either **SPIN**, an Ising model with variables in {-1, +1}, or **BINARY**, a QUBO with variables in {0, 1}. Section 2.4 describes how to choose the domain and carry an offset.

> **Note:** By default, if a file with the same name (within the same problem) already exists, the SDK will return that existing file unless you set `force=True` to overwrite it.

### 2.1 From a Local File Path

Different file formats (e.g., `.h5`, `.csv`, `.txt`, etc.) can be used to define the model, each offering unique characteristics for representing dense or sparse data. Only the self-describing HDF5 layout of section 2.1.1 can carry a variable domain and an offset. Every other format describes an Ising model with zero offset.

```python
from veloxq_sdk import File

# Suppose "my_problem" is a Problem instance
file_obj = File.from_instance(
    "path/to/local_data.h5",  # Other formats also supported e.g., .csv, .mtx, .dat, .csv
    name="my_data.h5",        # Optional; defaults to the file’s basename
    problem=my_problem,        # Optional; defaults to Problem.undefined()
    force=True                # Overwrite if a file with the same name exists
)
```

Below are the supported formats:

#### 2.1.1 HDF5 Format

HDF5 offers hierarchical, flexible data storage for diverse dataset sizes and types, with separate encoding formats for dense and sparse data. The platform reads two layouts of the `Ising` group.

**Minimal layout.** The group holds a `couplings` dataset for **dense** matrices or a `J_coo` group with `I`, `J`, and `V` datasets for **sparse** COO (Coordinate vectors) matrices, and an optional `biases` dataset. When `biases` is absent the biases are read from the entries where `J = I`, for both symmetric and triangular matrices. A group written this way is always read as an Ising model with spins in {-1, +1} and zero offset.

1) Dense format:
    ```py
    import h5py
    import numpy as np

    # Dense representation
    with h5py.File('example_dense.h5', 'w') as f:
        group = f.create_group("Ising")
        group.create_dataset("couplings", data=np.array([[0, 0.5, 0.25], [0.5, 0, 0.75], [0.25, 0.75, 0]]))
        group.create_dataset("biases", data=np.array([0.1, 0.2, 0.3]))
    ```
2) Sparse format:
    ```py
    import h5py
    import numpy as np

    # Sparse representation
    with h5py.File('example_sparse.h5', 'w') as f:
        group = f.create_group("Ising/J_coo")
        group.create_dataset("I", data=np.array([1, 2, 3]))
        group.create_dataset("J", data=np.array([2, 3, 1]))
        group.create_dataset("V", data=np.array([0.5, 0.75, 0.25]))
        group.parent.create_dataset("biases", data=np.array([0.1, 0.2, 0.3]))  # biases dataset is defined in the `Ising` group
    ```

**Self-describing layout.** This is the layout the SDK writes for every in-memory model (sections 2.2 to 2.4). It carries the variable domain and the offset, so it is the only file format that can hold a QUBO. The `Ising` group name is kept for both domains and is only a label. The group contains:

- Attributes `type = "BinaryQuadraticModel"`, `var_type = "SPIN"` or `"BINARY"`, and `sparsity = "dense"` or `"sparse"`.
- `L`: scalar, the number of variables.
- `biases`: vector of length `L` with the linear terms.
- `couplings`: for `sparsity = "dense"`, an `L x L` dataset. For `sparsity = "sparse"`, a group with attribute `type = "SparseMatrixCSC"` and datasets `I`, `J`, `V`, and `dims = [L, L]`. Indices are 1-based, every entry is stored in both triangles, and entries are sorted by column and then by row.
- `offset`: optional scalar dataset with the constant energy term. An absent dataset means zero. The solver ignores an `offset` attribute.
- `labels`: optional vector of variable names.

The couplings must be symmetric with a zero diagonal. Linear terms belong in `biases`, including the diagonal of a QUBO matrix.

```py
import h5py
import numpy as np

# E(x) = x0 + x1 + x2 - 2 x0 x1 - 2 x1 x2 + 0.5, with x in {0, 1}
with h5py.File('example_qubo.h5', 'w') as f:
    group = f.create_group("Ising")
    group.attrs["type"] = "BinaryQuadraticModel"
    group.attrs["var_type"] = "BINARY"
    group.attrs["sparsity"] = "dense"
    group.create_dataset("L", data=3)
    group.create_dataset("biases", data=np.array([1.0, 1.0, 1.0]))
    group.create_dataset("couplings", data=np.array([[0, -2, 0], [-2, 0, -2], [0, -2, 0]], dtype=float))
    group.create_dataset("offset", data=0.5)
```

`File.from_ising(...)` and `File.from_qubo(...)` write exactly this layout, so the simplest way to produce such a file is to let the SDK do it.

#### 2.1.2 MAT Format

MAT files (native to MATLAB), similarly to HDF5 format, encodes the Ising model using either dense matrices labeled `couplings` or sparse matrices using coordinate format vectors `I`, `J`, and `V`, as well as an optional `biases` vector. 

1) Dense format:
  ```matlab
  % Dense representation
  couplings = [0 0.5 0.25; 0.5 0 0.75; 0.25 0.75 0];
  biases = [0.1; 0.2; 0.3];
  save('example_dense.mat', 'couplings', 'biases');
  ```

2) Sparse format:
  ```matlab
  % Sparse COO representation
  I = [1; 2; 3];
  J = [2; 3; 1];
  V = [0.5; 0.75; 0.25];
  save('example_sparse.mat', 'I', 'J', 'V', 'biases');
  ```


#### 2.1.3 MTX Format

Matrix Market (MTX) format, differently from MAT and HDF5 format, encodes **Maximum Weighted Matching** problems using a coordinate format. The MTX format can include a header defining the Matrix Market format and comments starting with `%`. After the header and comments, the first non-commented line must specify the **matrix dimensions** and **non-zero element count** sperated by space, while the followings must specify the non-zero entries, with a triplet defining the **row**, **column**, and **value** (optional, defaults to `1`).

```mtx
%%MatrixMarket matrix coordinate real general
% rows cols non-zero-elements
% i j val
3 3 4
1 2 0.5
2 3 1.5
1 1
3 2 0.75
```

#### 2.1.4 DAT Format
The DAT text file format specifically encodes dense matrices of **Traveling Salesman Problem (TSP)** case descriptions. The file structure starts with the first line containing a **single integer**, which specifies the **dimension** of the two subsequent square matrices written in the following lines: the **flow matrix** and the **distance matrix**.

```dat
2
1 2
3 4
5 6
7 8
```

#### 2.1.5 CSV or plain text Format

The CSV format, or any other plain text, stores a Ising model matrix in a COO sparse format. The `I`, `J` and `V` vectors of the sparse matrix are stored as separate columns using space as delimiter and `#` as comment marker. The biases are infered from the entries where `J = I`.

```plaintext
# node1 node2 weight
1 2 0.5
2 3 0.75
3 1 0.25
```

### 2.2 From Dictionaries of Biases and Couplings

Create a `File` directly from biases and couplings defined as dictionaries. This is especially useful for sparse models.

```python
biases = {0: 1.0, 2: -1.0}  # Variable indices mapped to bias values
couplings = {(0, 1): -1.0, (1, 2): 0.5}  # Variable index pairs mapped to couplings values

file_obj = File.from_instance((biases, couplings), name="sparse_ising.h5")
```

Or using `File.from_dict`:

```python
file_obj = File.from_dict({"biases": biases, "couplings": couplings}, name="sparse_ising.h5")
```

The keyword form `biases=..., couplings=...` is accepted by `solver.sample`, not by `File.from_instance`. See [Submitting a Model to a Solver](solvers-and-backends.md#5-submitting-a-model-to-a-solver).

This internally generates a temporary HDF5 file and uploads it.

### 2.3 From Biases and Couplings in Various Formats

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

Or using `File.from_dict`:

```python
file_obj = File.from_dict({"biases": biases, "couplings": couplings})
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

### 2.4 Variable Domain and Offset: Ising and QUBO

Every model has a variable domain, called `vartype` after the dimod convention:

- `"SPIN"`: an Ising model. Variables are spins `s_i` in {-1, +1} and the energy is

  ```text
  E(s) = sum_i h_i s_i + sum_{i<j} J_ij s_i s_j + offset
  ```

- `"BINARY"`: a QUBO. Variables are bits `x_i` in {0, 1} and the energy is

  ```text
  E(x) = sum_i q_i x_i + sum_{i<j} Q_ij x_i x_j + offset
  ```

The `biases` hold `h` or `q` and the `couplings` hold `J` or `Q`. The solver works in the domain the file declares, and the result comes back in that same domain: spin states and Ising energies for `SPIN`, 0/1 states and QUBO energies for `BINARY`. See [Accessing Results](results.md#1-direct-access-via-veloxsampleset).

#### 2.4.1 Choosing the domain

The dictionary and tuple forms of sections 2.2 and 2.3 default to `SPIN`. Pass `vartype="BINARY"` to submit the same arrays as a QUBO. The dictionary form can also carry a `"vartype"` key. `vartype` accepts the strings `"SPIN"` and `"BINARY"` or the constants `dimod.SPIN` and `dimod.BINARY`.

```python
import numpy as np
from veloxq_sdk import File

q = np.array([1.0, 1.0, 1.0])
Q = np.array([
    [0, -2, 0],
    [-2, 0, -2],
    [0, -2, 0],
])

file_obj = File.from_instance((q, Q), vartype="BINARY")
file_obj = File.from_instance({"biases": q, "couplings": Q, "vartype": "BINARY"})
file_obj = File.from_dict({"biases": q, "couplings": Q}, vartype="BINARY")
file_obj = File.from_tuple((q, Q), vartype="BINARY")
```

When the dictionary has a `"vartype"` key and the `vartype` argument is also given, the two must agree. A conflict raises a `ValueError`.

The explicit constructors fix the domain by name and take the offset directly:

```python
file_obj = File.from_ising(h, J, offset=0.5)  # SPIN
file_obj = File.from_qubo(q, Q, offset=0.5)   # BINARY
```

`vartype` applies to in-memory data only. A `File` object or a file path already fixes the domain through its content, so passing `vartype` with either is ignored and logged as a warning.

#### 2.4.2 Diagonal couplings

A coupling on the diagonal, written as `(i, i)` or `(i,)` in a dictionary or as `couplings[i, i]` in a matrix, is folded the way dimod folds it:

- In a QUBO it is a linear term, because `x_i * x_i == x_i`, so it is added to the bias of `i`. A full QUBO matrix can therefore be passed as `couplings` with empty `biases`.
- In an Ising model it is a constant, because `s_i * s_i == 1`, so it is added to the offset.

```python
# The diagonal of Q is the linear part: same model as the example above.
Q_full = np.array([
    [1, -2, 0],
    [-2, 1, -2],
    [0, -2, 1],
])
file_obj = File.from_qubo([], Q_full)
```

Off-diagonal couplings must be symmetric. When both `(i, j)` and `(j, i)` are given with different values, a `ValueError` is raised.

#### 2.4.3 The offset

The offset is a constant added to every energy. It is stored in the file and the solver adds it to the energies it reports, so the result energies match the model's energy function. Each input form carries it differently:

| Input | Offset |
| --- | --- |
| tuple, dictionary, or keyword arguments | zero, plus any folded Ising diagonal |
| `File.from_ising(...)` / `File.from_qubo(...)` | the `offset` argument |
| `dimod.BinaryQuadraticModel` | `bqm.offset` |
| HDF5 file in the self-describing layout | the `offset` dataset |
| any other file format | zero |

To attach a non-zero offset to plain arrays, use `File.from_ising`, `File.from_qubo`, or a `BinaryQuadraticModel`.

#### 2.4.4 dimod models

A `dimod.BinaryQuadraticModel` is uploaded in its own `vartype` with its offset, so the energies the solver reports equal `bqm.energies(result.sample)`. Pass `vartype` to convert it before uploading:

```python
import dimod
from veloxq_sdk import File

bqm = dimod.BinaryQuadraticModel.from_qubo(
    {(0, 0): 1.0, (1, 1): 1.0, (2, 2): 1.0, (0, 1): -2.0, (1, 2): -2.0},
    offset=0.5,
)

file_obj = File.from_instance(bqm)                  # keeps bqm.vartype (BINARY)
file_obj = File.from_instance(bqm, vartype="SPIN")  # uploads bqm.change_vartype("SPIN")
file_obj = File.from_bqm(bqm)                       # explicit constructor
```

Converting the domain changes the biases, couplings, and offset together, so the energy of every configuration is preserved.

#### 2.4.5 Initial states

An initial state passed through `init_state` is a `dimod.SampleSet` whose `vartype` must match the model's. A mismatch raises a `ValueError`. Convert it first with `init_state.change_vartype("BINARY")` or `init_state.change_vartype("SPIN")`.

```python
import dimod

init_state = dimod.SampleSet.from_samples(
    [[1, 1, 1], [0, 0, 0]], vartype="BINARY", energy=[-1.0, 0.0],
)
file_obj = File.from_qubo(q, Q, init_state=init_state)
```

### 2.5 From Direct I/O Stream (In-Memory Data)

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

### 2.6 Using an Existing File Object

If you have already created/retrieved a `File` object, simply pass it directly:

```python
existing_file_obj = File.get_files(name="my_data.h5", limit=1)[0]
file_obj = File.from_instance(existing_file_obj)
# 'file_obj' points to the same underlying file
```

## 3. Uploading & Overwriting Files

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

## 4. Associating with Problems

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

## 5. Downloading Files

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
