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
import dimod
from dimod.serialization import coo
from veloxq_sdk import VeloxQSolver, File, PLGridGH200

# load_config(".config.py")  # optional if you prefer file-based configuration

with open("some_problem_coo.txt") as fd:
	bqm = coo.load(fd, vartype=dimod.SPIN)

file_obj = File.from_bqm(bqm)

solver = VeloxQSolver(backend=PLGridGH200())

job = solver.submit(file_obj)

job.wait_for_completion()

with open("result.h5", "wb") as f:
	job.download_result(f)

```

Run the script with your token available to the SDK, for example:

```shell
export VELOX_TOKEN=<token>
python example.py
```

>For more details on the SDK usage, see [Defining Problems & Files](problems-and-files.md), [Submitting Jobs](jobs.md), and [Accessing Results](results.md).
