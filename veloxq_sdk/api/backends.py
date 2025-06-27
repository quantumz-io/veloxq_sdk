from veloxq_sdk.api.base import BaseModel


class BaseBackend(BaseModel):
    """Base class for all backends."""


class VeloxQH100_1(BaseBackend):
    id: str = 'a87c8e0c-c883-4d6a-8495-6cd55e95ed96'


class VeloxQH100_2(BaseBackend):
    id: str = '1095cf2d-a3a0-4125-9615-45f2884e1aec'
