"""VeloxQ SDK for Python."""

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

import warnings

from veloxq_sdk.backends import (
    VeloxQH100_1,
    VeloxQH100_2,
    PLGridGH200,
)
from veloxq_sdk.jobs import Job
from veloxq_sdk.problems import File, Problem
from veloxq_sdk.solvers import (
    VeloxQParameters,
    VeloxQSolver,
    SBMParameters,
    SBMSolver,
)

try:
    from veloxq_sdk._version import __version__
except ImportError:
    warnings.warn(
        "veloxq_sdk._version module not found. "
        "This may happen if the package is not installed properly. "
        "Using default version '0.0.0+unknown'.",
        ImportWarning,
        stacklevel=2,
    )
    __version__ = "0.0.0+unknown"

__all__ = [
    'File',
    'Job',
    'Problem',
    'VeloxQH100_1',
    'VeloxQH100_2',
    'PLGridGH200',
    'VeloxQParameters',
    'VeloxQSolver',
    'SBMParameters',
    'SBMSolver',
]
