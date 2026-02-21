# PLGrid Backends

PLGrid users with eligible grants can run the VeloxQ Solver on PLGrid infrastructure via VeloxQ backends. You need an active PLGrid account (see https://portal.plgrid.pl/) and it must be linked to your VeloxQ platform account.

## Connect Your PLGrid Account

1. Open https://web.veloxq.com/login and choose **Login with PLGrid**.
2. After linking, generate an API key in https://web.veloxq.com/user/settings if you do not already have one.
3. Provide the token to the SDK (e.g., set the `VELOX_TOKEN` environment variable). See [configuration.md](configuration.md) for alternative configuration options.

## Supported Backends

- `PLGridGH200` PLGrid 4x NVIDIA GH200 

## Example: Submit a BQM to PLGrid

The example below loads a SPIN BQM from a COO file, submits it to the PLGrid backend, waits for completion, and downloads the result file.

```python
from urllib import request

import dimod
from dimod.serialization import coo
from veloxq_sdk import VeloxQSolver, File, PLGridGH200

# optional if you prefer file-based configuration; see https://github.com/quantumz-io/veloxq_sdk/wiki/configuration
# from veloxq_sdk.config import load_config
# load_config("config.py")

# Download the example problem file or use your own
request.urlretrieve("https://raw.githubusercontent.com/quantumz-io/veloxq_sdk/main/examples/P2_CBFM-P.txt", "P2_CBFM-P.txt")

# Load BQM from txt problem
with open("P2_CBFM-P.txt") as fd:
    bqm = coo.load(fd, vartype=dimod.SPIN)

# Create a file obj to run the solver
file_obj = File.from_bqm(bqm)

# Select the solver with the PLGrid GH200 backend
solver = VeloxQSolver(backend=PLGridGH200())

# Run the solver and get the job
job = solver.submit(file_obj)

job.wait_for_completion()

# Print results
print(job.result)

# Save job result
with open("result.h5", "wb") as f:
    job.download_result(f)
```

Run the script with your token available to the SDK, for example:

```shell
export VELOX_TOKEN=<token>
python example.py
```

## Accesing the Job results

In order to get the **energy** value and spins **states** for each sample from your submited problem, you must access the saved HDF5 result file and read it's `Spectrum/energies` and `Spectrum/states` datasets, or simply use the *SampleSet* returned from `job.result` with `job.result.energy` and `job.result.sample`.

```py
# Accessing energy and states from HDF5 result file
import h5py

with h5py.File("result.h5", "r") as data:
    energies = data["Spectrum/energies"][:]
    states = data["Spectrum/states"][:]

print("Energies:", energies)
print("States:", states)
```

>For more details on the SDK usage, see [Defining Problems & Files](problems-and-files.md), [Submitting Jobs](jobs.md), and [Accessing Results](results.md).
