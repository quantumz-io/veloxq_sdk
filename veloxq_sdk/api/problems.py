from __future__ import annotations

import hashlib
import logging
import typing as t
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryFile

import h5py
from numpy import dtype, ndarray
from pydantic import Field

from veloxq_sdk.api.base import BaseModel

InstanceLike = t.Union[
    'InstanceDict',
    'InstanceTuple',
    'File',
    Path,
    str,
]

BiasesType = t.Union[t.List[float], ndarray]
CouplingType = t.Union[t.List[t.List[float]], ndarray]

InstanceTuple = t.Tuple[BiasesType, CouplingType]

_logger = logging.getLogger(__name__)


class InstanceDict(t.TypedDict):
    """A dictionary type for instances."""

    biases: BiasesType
    coupling: CouplingType


class Problem(BaseModel):
    """A class representing a problem in the VeloxQ API."""
    name: str = Field(description="The name of the problem.")

    created_at: datetime = Field(description="The date and time when the problem was created.")
    updated_at: datetime = Field(description="The date and time when the problem was last updated.")

    def get_files(self, name: str | None = None, limit: int = 1000) -> list[File]:
        """Get all files associated with this problem."""
        params: dict[str, int | str] = {'_page': 1, '_limit': limit}
        if name:
            params['q'] = name

        response = self._http.get(f'problems/{self.id}/files',
                                    params=params)
        response.raise_for_status()
        data = response.json()['data']
        return [File.model_validate(item) for item in data]

    def new_file(self, name: str, size: int) -> File:
        """Create a new file for this problem."""
        return File.create(name=name, size=size, problem=self)

    @classmethod
    def undefined(cls) -> Problem:
        """Default Problem instance."""

        response = cls._http.get('problems',
                                 params={'_page': 1, '_limit': 1, 'q': 'undefined'})
        response.raise_for_status()
        data = response.json()['data']
        if data:
            return cls.model_validate(data[0])

        return cls.create(name='undefined')

    @classmethod
    def create(cls, name: str) -> Problem:
        """Create a new problem."""
        response = cls._http.post('problems', json={'name': name})
        response.raise_for_status()
        data = response.json()
        return cls.model_validate(data)

    @classmethod
    def get_problems(cls, name: str | None = None, limit: int = 1000) -> list[Problem]:
        """Get all user problems."""
        params: dict[str, int | str] = {'_page': 1, '_limit': limit}
        if name:
            params['q'] = name

        response = cls._http.get('problems', params=params)
        response.raise_for_status()
        data = response.json()['data']
        return [cls.model_validate(item) for item in data]

    @classmethod
    def from_id(cls, problem_id: int) -> Problem:
        """Create a Problem instance from an ID."""
        response = cls._http.get(f'problems/{problem_id}')
        response.raise_for_status()
        data = response.json()
        return cls.model_validate(data)


class File(BaseModel):
    """A class representing a file in the VeloxQ API."""
    name: str

    size: int = Field(
        description="The size of the file in bytes.",
    )
    uploaded_bytes: int = Field(
        description="The number of bytes that have been uploaded.",
    )
    problem: Problem = Field(
        description="The problem associated with this file.",
    )
    created_at: datetime = Field(
        description="The date and time when the file was created.",
    )
    updated_at: t.Optional[datetime] = Field(
        default=None,
        description="The date and time when the file was updated.",
    )
    status: str = Field(
        description="The status of the file upload.",
    )

    def upload(self, content: t.IO, chunk_size: int = 1024*1024):
        with self.http.open_ws(
            f'problems/{self.problem.id}/files/{self.id}/upload/ws',
        ) as ws:
            while data := content.read(chunk_size):
                ws.send(data)
            ws.send(b'')
        self.refresh()

    def download(self, file: t.BinaryIO, chunk_size: int = 1024*1024) -> None:
        """Download the file content."""
        download_url = self.http.get(
            f'problems/{self.problem.id}/files/{self.id}',
        )
        download_url.raise_for_status()
        with self.http.stream(
            'GET',
            download_url.text,
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes(chunk_size):
                file.write(chunk)

    def cancel(self) -> None:
        """Cancel the file upload."""
        response = self._http.delete(f'problems/{self.problem.id}/files/{self.id}/cancel')
        response.raise_for_status()
        self.refresh()

    def delete(self) -> None:
        """Delete the file."""
        response = self._http.delete(f'problems/{self.problem.id}/files/{self.id}')
        response.raise_for_status()

    def refresh(self) -> None:
        """Refresh the file data from the API."""
        response = self._http.get(f'problems/{self.problem.id}/files',
                                  params={'_page': 1, '_limit': 1, 'q': self.id})
        response.raise_for_status()
        data = response.json()['data'][0]
        self.model_update(data)

    @classmethod
    def create(cls, name: str, size: int, problem: Problem | None = None) -> File:
        """Create a new file."""
        problem = problem or Problem.undefined()
        response = cls._http.post(
            f'problems/{problem.id}/files/upload-request',
            json={
                'file_name': name,
                'size': size,
            },
        )
        response.raise_for_status()
        data = response.json()
        data['problem'] = problem
        return cls.model_validate(data)

    @classmethod
    def get_files(cls, name: str | None, limit: int = 1000) -> list[File]:
        """Get all user files."""
        params: dict[str, int | str] = {'_page': 1, '_limit': limit}
        if name:
            params['q'] = name

        response = cls._http.get('files',
                                 params=params)
        response.raise_for_status()
        data = response.json()['data']
        return [cls.model_validate(item) for item in data]

    @classmethod
    def from_id(cls, file_id: str) -> File:
        """Create a File instance from an ID."""
        file = cls.get_files(name=file_id, limit=1)
        if not file:
            msg = f'File with ID {file_id} not found.'
            raise ValueError(msg)
        return file[0]

    @classmethod
    def from_instance(
        cls,
        instance: InstanceLike,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        force: bool = False,
    ) -> File:
        """Create a File instance from an InstanceLike object."""
        if isinstance(instance, File):
            return instance
        if isinstance(instance, (Path, str)):
            return cls.from_path(
                path=instance,
                name=name,
                problem=problem,
                force=force,
            )
        if isinstance(instance, dict):
            return cls.from_dict(
                data=instance,
                name=name,
                problem=problem,
                force=force,
            )
        if isinstance(instance, tuple):
            return cls.from_tuple(
                data=instance,
                name=name,
                problem=problem,
                force=force,
            )

        msg = (
            f'Unsupported instance type: {type(instance)}. '
            'Expected a File, Path, str, dict, or tuple.'
        )
        raise TypeError(msg)

    @classmethod
    def from_dict(
        cls,
        data: InstanceDict,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        force: bool = False,
    ) -> File:
        """Create a File instance from a dictionary."""
        return cls.from_ising(
            biases=data['biases'],
            coupling=data['coupling'],
            name=name,
            problem=problem,
            force=force,
        )

    @classmethod
    def from_tuple(
        cls,
        data: InstanceTuple,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        force: bool = False,
    ) -> File:
        """Create a File instance from a tuple."""
        return cls.from_ising(
            biases=data[0],
            coupling=data[1],
            name=name,
            problem=problem,
            force=force,
        )

    @classmethod
    def from_ising(
        cls,
        biases: BiasesType,
        coupling: CouplingType,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        force: bool = False,
    ) -> File:
        """Create a File instance from an Ising model."""

        if name:
            if (ext_idx := name.find('.')) != -1:
                name = name[:ext_idx]
            name += '.h5'
            if not force and (existing_files := cls.get_files(name=name, limit=1)):
                return existing_files[0]

        with TemporaryFile() as temp_file:
            with h5py.File(temp_file, 'w') as h5file:
                h5file.create_dataset('/ising/biases', data=biases)
                h5file.create_dataset('/ising/couplings', data=coupling)
            temp_file.flush()

            temp_file_size = temp_file.tell()
            temp_file.seek(0)

            name = name or (cls._create_hash(temp_file) + '.h5')
            temp_file.seek(0)

            # TODO(hendrik): check if the file already exists under the problem
            # and return it if it does.

            new_file = cls.create(
                name=name,
                size=temp_file_size,
                problem=problem,
            )

            new_file.upload(temp_file)

        return new_file

    @classmethod
    def from_path(
        cls,
        path: Path | str,
        name: str | None,
        problem: Problem | None = None,
        *,
        force: bool = False,
    ) -> File:
        """Create a File instance from a file path.

        The name or path must contain the file extension.

        Uploads the file content to the API and returns a File instance.

        Args:
            path (Path | str): The path to the file.
            name (str | None): The name of the file. If None, the file's name will be used.
            problem (Problem | None): The problem associated with the file. If None, a default problem will be used.
            force (bool): If True, overwrite existing files with the same name.

        Returns:
            File: The created File instance.

        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f'File {path} does not exist.')
        name = name or path.name

        existing_files = cls.get_files(name=name, limit=1)
        if existing_files and not force:
            return existing_files[0]

        # TODO(hendrik): check if the file already exists under the problem
        # and return it if it does.

        new_file = cls.create(name=name,
                              size=path.stat().st_size,
                              problem=problem)

        with path.open('rb') as file_content:
            new_file.upload(file_content)
        return new_file

    @classmethod
    def from_io(
        cls,
        data: t.BinaryIO,
        name: str | None = None,
        extension: str = 'h5',
        problem: Problem | None = None,
        *,
        force: bool = False,
    ) -> File:
        """Create a File instance from a binary IO stream."""
        if not name:
            data.seek(0)
            name = cls._create_hash(data)

        if name.find('.') == -1:
            name += f'.{extension}'

        existing_files = cls.get_files(name=name, limit=1)
        if existing_files and not force:
            return existing_files[0]

        # TODO(hendrik): check if the file already exists under the problem
        # and return it if it does.

        new_file = cls.create(name=name,
                              size=data.seek(0, 2),
                              problem=problem)
        data.seek(0)
        new_file.upload(data)
        return new_file


    @classmethod
    def model_validate(
        cls, obj: dict[str, t.Any], *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: t.Any = None,
    ) -> File:
        obj['problem'] = obj.get('problem', Problem.from_id(obj['problemId']))
        return super().model_validate(obj, strict=strict,
                                      from_attributes=from_attributes,
                                      context=context)

    @staticmethod
    def _create_hash(
        file: t.BinaryIO,
        chunk_size: int = 1024 * 1024,
    ):
        """Create a hash of the file content."""
        hasher = hashlib.sha256()
        while chunk := file.read(chunk_size):
            hasher.update(chunk)
        return hasher.hexdigest()
