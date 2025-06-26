from __future__ import annotations

import typing as t

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from veloxq_sdk.http import ClientMixin

if t.TYPE_CHECKING:
    from httpx import Response


class BaseModel(PydanticBaseModel, ClientMixin):
    """Base model for all API models."""

    _id: str = Field(
        alias='id',
        description='Unique identifier for the model instance.',
    )

    class Config:
        """Configuration for the Pydantic model."""

        extra = 'forbid'  # Disallow extra fields
        allow_population_by_field_name = True  # Allow population by field name
        use_enum_values = True
        validate_by_name=True
        validate_by_alias=True

    @classmethod
    def _from_response(cls, response: Response) -> BaseModel | list[BaseModel]:
        """Create a model instance from an HTTP response."""
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return [cls.model_validate(item) for item in data]
        return cls.model_validate(data)

    def _update_from_response(self, response: Response) -> BaseModel:
        """Update the model instance from an HTTP response."""
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            msg = 'Response contains a list, expected a single object.'
            raise TypeError(msg)
        return self.model_update(data)

    def model_update(self, data: dict) -> BaseModel:
        """Update the model instance with new data."""
        update = self.model_dump(mode='json')
        update.update(data)
        for k,v in self.model_validate(update).model_dump(exclude_defaults=True).items():
            setattr(self, k, v)
        return self

    @property
    def id(self) -> str:
        """Get the unique identifier of the solver."""
        return self._id

