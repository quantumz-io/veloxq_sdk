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

"""Atomic tests for veloxq_sdk.api.core.base."""

import typing as t

import httpx
import pytest
from pydantic import ValidationError

from veloxq_sdk.api.core.base import (
    BaseModel,
    BasePydanticModel,
    build_adapters,
)


@build_adapters
class Widget(BaseModel):
    display_name: str = ''
    count: int = 0


def _response(payload: t.Any, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request('GET', 'https://api.test/widgets'),
    )


class TestValidation:
    def test_populates_by_camel_alias(self):
        widget = Widget.model_validate({'id': 'w1', 'displayName': 'spam'})
        assert widget.display_name == 'spam'

    def test_populates_by_field_name(self):
        widget = Widget.model_validate({'id': 'w1', 'display_name': 'spam'})
        assert widget.display_name == 'spam'

    def test_extra_keys_are_ignored(self):
        widget = Widget.model_validate({'id': 'w1', 'unknownKey': 1})
        assert widget.id == 'w1'

    def test_id_is_required(self):
        with pytest.raises(ValidationError):
            Widget.model_validate({'display_name': 'no id'})

    def test_id_is_frozen(self):
        widget = Widget(id='w1')
        with pytest.raises(ValidationError):
            widget.id = 'w2'


class TestResponseParsing:
    def test_from_response(self):
        widget = Widget._from_response(_response({'id': 'w1', 'count': 3}))
        assert (widget.id, widget.count) == ('w1', 3)

    def test_from_list_response(self):
        widgets = Widget._from_list_response(
            _response([{'id': 'w1'}, {'id': 'w2'}]),
        )
        assert [w.id for w in widgets] == ['w1', 'w2']

    def test_from_paginated_response(self):
        widgets = Widget._from_paginated_response(
            _response({'data': [{'id': 'w1'}], 'total': 1}),
        )
        assert [w.id for w in widgets] == ['w1']

    def test_error_response_raises(self):
        with pytest.raises(httpx.HTTPStatusError):
            Widget._from_response(_response({'message': 'nope'}, 404))

    def test_update_from_response(self):
        widget = Widget(id='w1', count=1)
        widget._update_from_response(_response({'id': 'w1', 'count': 5}))
        assert widget.count == 5


class TestModelUpdate:
    def test_updates_all_fields_but_id(self):
        widget = Widget(id='w1', display_name='old', count=1)
        widget.model_update_json(Widget(id='w1', display_name='new', count=2))
        assert (widget.display_name, widget.count) == ('new', 2)
        assert widget.id == 'w1'

    def test_fields_filter_limits_update(self):
        widget = Widget(id='w1', display_name='old', count=1)
        widget.model_update_json(
            Widget(id='w1', display_name='new', count=2),
            fields=['count'],
        )
        assert (widget.display_name, widget.count) == ('old', 2)

    def test_id_mismatch_raises(self):
        widget = Widget(id='w1')
        with pytest.raises(ValueError, match='ID mismatch'):
            widget.model_update_json(Widget(id='w2'))

    def test_plain_model_update_has_no_id_guard(self):
        class Note(BasePydanticModel):
            body: str = ''

        note = Note(body='a')
        note.model_update_json(Note(body='b'))
        assert note.body == 'b'

    def test_plain_model_update_fields_filter(self):
        class Note(BasePydanticModel):
            body: str = ''
            title: str = ''

        note = Note(body='a', title='old')
        note.model_update_json(Note(body='b', title='new'), fields=['body'])
        assert (note.body, note.title) == ('b', 'old')


class TestAdapters:
    def test_build_adapters_populates_class(self):
        assert Widget.adapters.list.validate_python([{'id': 'w1'}])[0].id == 'w1'
        paginated = Widget.adapters.paginated.validate_python(
            {'data': [{'id': 'w2'}]},
        )
        assert paginated['data'][0].id == 'w2'
