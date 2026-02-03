from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, TypeAdapter
from pydantic.alias_generators import to_camel
from typing_extensions import Self, TypedDict

from veloxq_sdk.api.core.http import ClientMixin

if t.TYPE_CHECKING:
    from httpx import Response

_T = t.TypeVar('_T', bound='BasePydanticModel')


class PaginatedResponse(TypedDict, t.Generic[_T]):
    """TypedDict for paginated API responses."""

    data: list[_T]


class Adapters(t.Generic[_T]):
    """Container for TypeAdapters for different response types."""

    list: TypeAdapter[list[_T]]
    paginated: TypeAdapter[PaginatedResponse[_T]]


def build_adapters(cls: type[_T]) -> type[_T]:
    """Class decorator to build TypeAdapters for a Pydantic model."""
    cls.adapters = Adapters()
    cls.adapters.list = TypeAdapter(list[cls])
    cls.adapters.paginated = TypeAdapter(PaginatedResponse[cls])
    return cls


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

    adapters: t.ClassVar[Adapters[Self]] = None

    @classmethod
    def _from_response(
        cls,
        response: Response,
    ) -> Self:
        """Create a model instance from an HTTP response."""
        response.raise_for_status()
        return cls.model_validate_json(response.content)

    @classmethod
    def _from_list_response(
        cls,
        response: Response,
    ) -> list[Self]:
        """Create a list of model instances from an HTTP response."""
        response.raise_for_status()
        return cls.adapters.list.validate_json(response.content)

    @classmethod
    def _from_paginated_response(
        cls,
        response: Response,
    ) -> list[Self]:
        """Create a list of model instances from a paginated HTTP response."""
        response.raise_for_status()
        return cls.adapters.paginated.validate_json(response.content)['data']

    def _update_from_response(
        self,
        response: Response,
        *,
        fields: t.Iterable[str] | None = None,
    ) -> Self:
        """Update the model instance from an HTTP response."""
        response.raise_for_status()
        return self.model_update_json(
            self.model_validate_json(response.content),
            fields=fields,
        )

    def model_update_json(
        self,
        model: BasePydanticModel,
        *,
        fields: t.Iterable[str] | None = None,
    ) -> Self:
        """Update the model instance with new data."""
        fields = set(fields or [])
        for k in type(self).model_fields:
            if fields and k not in fields:
                continue
            setattr(self, k, getattr(model, k))
        return self


class BaseModel(BasePydanticModel, ClientMixin):
    """Base model for all API models."""

    id: str = Field(
        frozen=True,
        description='Unique identifier for the model instance.',
    )

    def model_update_json(
        self,
        model: BaseModel,
        *,
        fields: t.Iterable[str] | None = None,
    ) -> Self:
        """Update the model instance with new data."""
        if model.id != self.id:
            msg = f'ID mismatch: {model.id} != {self.id}'
            raise ValueError(msg)
        fields = set(fields or [])
        for k in type(self).model_fields:
            if k == 'id' or (fields and k not in fields):
                continue
            setattr(self, k, getattr(model, k))
        return self
