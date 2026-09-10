# Copyright 2025-2026 QUANTUMZ.IO sp. z o.o.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from tqdm import tqdm

from veloxq_sdk import File, VeloxQH100_1, VeloxQParameters, VeloxQSolver, Job
from veloxq_sdk.config import load_config

load_config("config.py")

N = 50

# random dense couplings for Max-Cut
J = np.random.randn(N, N)
J = (J + J.T) / 2
np.fill_diagonal(J, 0)

biases = np.zeros(N)
couplings = J

instance_file = File.from_ising(biases, couplings)

solver = VeloxQSolver(
    backend=VeloxQH100_1(),
    parameters=VeloxQParameters(
        num_rep=100,
        num_steps=1000
    )
)

jobs = []
for i in tqdm(range(10), desc="Submitting jobs"):
    print(f"Job {i+1}/10")
    job = solver.submit(instance_file)
    print(f"  - Job ID: {job.id}")
    jobs.append(job)

pool = ThreadPoolExecutor(max_workers=10)

def get_job_result(job: Job) -> Job:
    job.wait_for_completion()
    return job

futures = [pool.submit(get_job_result, job) for job in jobs]

for future in tqdm(as_completed(futures), total=len(futures), desc="Retrieving results"):
    try:
        job = future.result()
    except Exception as e:
        print(f"Job failed with exception: {e}")
    else:
        print(f"Job {job.id} took {job.updated_at - job.created_at}")
