# Accessing Results

## 1. Direct Access via `VeloxSampleSet`

When a job completes, the `job.result` property returns a `VeloxSampleSet` object, which inherits all implementations from dimod's `SampleSet` class. A `SampleSet` object contains the samples and associated data, such as energies, variable values, and per-sample data.

> **Note:** See [dimod's documentation for `SampleSet`](https://docs.dwavequantum.com/en/latest/ocean/api_ref_dimod/sampleset.html#dimod.SampleSet>) for more information regarding extra usage and features.

### 1.1 Properties

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

### 1.2 Methods

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

## 2. HDF5 Result

### 2.1 Downloading the Result File

To save the HDF5 result to a custom location and access the data.

```python
job.save_result("result.hdf5")

with h5py.File("result.hdf5", "r") as data:
    states = data["Spectrum/states"][:]
```

Or you can directly download the result to a file-like object:

```python
with open("result.hdf5", "wb") as f:
    job.download_result(f, chunk_size=1024*1024)
```

### 2.2 HDF5 Result Structure

Result files downloaded from PLGrid backends are HDF5 files with a `Spectrum` group containing the sampled solutions and metadata:

- `Spectrum/energies` (`float32`, shape `(num_samples,)`): energy value for each sample.
- `Spectrum/states` (`int8`, shape `(num_samples, num_variables)`): spin states for each sample, using ±1 encoding.
- `Spectrum/L` (`int64`): number of variables in the submitted problem.
- `Spectrum/num_batches` (`int64`): number of solver batches executed.
- `Spectrum/num_rep` (`int64`): number of repetitions performed.
- `Spectrum/metadata` (`bytes`): solver metadata (implementation-specific).

Example: read the lowest-energy sample directly from the downloaded result file.

```python
import h5py
import numpy as np

with h5py.File("result.h5", "r") as data:
    energies = data["Spectrum/energies"][:]
    states = data["Spectrum/states"][:]
    idx = int(np.argmin(energies))
    best_energy = energies[idx]
    best_state = states[idx]

    print("Best energy:", best_energy)
    print("State:", best_state)
```
