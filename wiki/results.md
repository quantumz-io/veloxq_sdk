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

## 2. Downloading the Result File

To manually download to a custom location and access the hdf5 data.

```python
with open("my_results.hdf5", "wb") as f:
    job.download_result(f, chunk_size=1024*1024)

with h5py.File("my_result.hdf5", "r") as data:
    states = data["Spectrum/states"][:]
```
