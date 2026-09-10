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

from veloxq_sdk.api.core.base import BaseModel


class BaseBackend(BaseModel):
    """Base class for all backends."""


class VeloxQH100_1(BaseBackend):
    """VeloxQ H100 backend for VeloxQ API.

    GPU_COUNT: 1
    """

    id: str = 'a87c8e0c-c883-4d6a-8495-6cd55e95ed96'


class VeloxQH100_2(BaseBackend):
    """VeloxQ H100 backend for VeloxQ API.

    GPU_COUNT: 2
    """

    id: str = '1095cf2d-a3a0-4125-9615-45f2884e1aec'

class PLGridGH200(BaseBackend):
    """PLGrid GH200 backend for VeloxQ API.

    GPU_COUNT: 4
    """

    id: str = '461405a2-a7e4-403a-ad0f-66affa98c26a'
