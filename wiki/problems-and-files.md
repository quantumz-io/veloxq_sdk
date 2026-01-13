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

> **Note:** By default, if a file with the same name (within the same problem) already exists, the SDK will return that existing file unless you set `force=True` to overwrite it.

### 2.1 From a Local File Path

Different file formats (e.g., `.h5`, `.csv`, `.txt`, etc.) can be used to define the Ising model, each offering unique characteristics for representing dense or sparse data.

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

HDF5 offers hierarchical, flexible data storage for diverse dataset sizes and types, with separate encoding formats for dense and sparse data.
Each file must contain an `Ising` group with a `couplings` dataset for **dense** matrices or a `J_coo` group with `I`, `J`, and `V` datasets for **sparse** COO (Coordinate vectors) matrices, and a optional `biases` dataset, when not present biases are read where entries are `J = I` for both symmetric and triangular matrices.

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

### 2.4 From Direct I/O Stream (In-Memory Data)

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

### 2.5 Using an Existing File Object

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
