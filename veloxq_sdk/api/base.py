from __future__ import annotations

import typing as t

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field
from pydantic.alias_generators import to_camel

from veloxq_sdk.http import ClientMixin

if t.TYPE_CHECKING:
    from httpx import Response


class BasePydanticModel(PydanticBaseModel):
    """Base class for Pydantic models with custom configuration."""

    class Config:
        """Configuration for the Pydantic model."""

        extra = 'ignore'
        alias_generator = to_camel
        populate_by_name = True  # Allow population by field name
        use_enum_values = True
        validate_by_name = True
        validate_by_alias = True


class BaseModel(BasePydanticModel, ClientMixin):
    """Base model for all API models."""

    id: str = Field(
        frozen=True,
        description='Unique identifier for the model instance.',
    )

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
        if data['id'] != self.id:
            msg = f'ID mismatch: {data["id"]} != {self.id}'
            raise ValueError(msg)
        update = self.model_dump(mode='json')
        update.update(data)
        updated_model = self.model_validate(update)
        for k in updated_model.model_fields:
            if k == 'id':
                continue
            setattr(self, k, getattr(updated_model, k))
        return self
