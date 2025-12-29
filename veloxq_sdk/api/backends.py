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

class PLGridG200(BaseBackend):
    """PLGrid G200 backend for VeloxQ API.

    GPU_COUNT: 4
    """

    id: str = '461405a2-a7e4-403a-ad0f-66affa98c26a'
