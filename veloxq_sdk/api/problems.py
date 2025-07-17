"""VeloxQ API Problems Module.

This module provides classes and methods for interacting with the VeloxQ API, focusing on
Problem and File entities. These classes enable creating, retrieving, uploading, downloading,
and managing files and problems within the VeloxQ platform.
"""
from __future__ import annotations

import hashlib
import logging
import typing as t
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryFile

import httpx
import h5py
import numpy as np
from dimod import BinaryQuadraticModel
from dimod.views.quadratic import Linear, Quadratic
from pydantic import Field

from veloxq_sdk.api.core.base import BaseModel

InstanceLike = t.Union[
    'InstanceDict',
    'InstanceTuple',
    'File',
    Path,
    str,
    BinaryQuadraticModel,
]

BiasType = t.Union[float, np.floating]
CouplingType = BiasType

BiasesType = t.Union[
    t.List[BiasType],
    np.ndarray,
    t.Dict[int, BiasType],
    Linear,
]
CouplingsType = t.Union[
    t.List[t.List[CouplingType]],
    np.ndarray,
    t.Dict[t.Tuple[int, int], CouplingType],
    Quadratic,
]

InstanceTuple = t.Tuple[BiasesType, CouplingsType]


class InstanceDict(t.TypedDict):
    """A dictionary type for Ising-model instances.

    Attributes:
        biases (BiasesType): A list or NumPy array of float values 
            representing the bias terms in an Ising model.
        couplings (CouplingType): A nested list or NumPy array of float values
            representing the coupling terms in an Ising model.

    """

    biases: BiasesType
    couplings: CouplingsType


class Problem(BaseModel):
    """A class representing a problem in the VeloxQ API.

    This class stores metadata about a given problem, including name and timestamps
    for creation and updates. It also allows operations such as listing and creating
    files associated with a particular problem.

    Attributes:
        name (str): The name of the problem.
        created_at (datetime): The datetime of when the problem was created.
        updated_at (datetime): The datetime of the last update to the problem.

    """

    name: str = Field(description='The name of the problem.')
    created_at: datetime = Field(description='The date and time when the problem was created.')
    updated_at: datetime = Field(description='The date and time when the problem was last updated.')

    def get_files(self, name: str | None = None, limit: int = 1000) -> list[File]:
        """Get all files associated with this problem.

        Args:
            name (str | None): Optional query string to filter files by name.
            limit (int): Maximum number of files to return (default 1000).

        Returns:
            list[File]: A list of files that belong to this problem.

        """
        params: dict[str, int | str] = {
            '_page': 1,
            '_limit': limit,
            '_sort': 'created_at',
            'order': 'desc',
        }
        if name:
            params['q'] = name

        response = self._http.get(f'problems/{self.id}/files', params=params)
        response.raise_for_status()
        data = response.json()['data']
        return [File.model_validate(item) for item in data]

    def new_file(self, name: str, size: int) -> File:
        """Create a new file for this problem.

        Args:
            name (str): The name of the file to create.
            size (int): The file size in bytes.

        Returns:
            File: A File object that references the newly created file on the server.

        """
        return File.create(name=name, size=size, problem=self)

    def delete(self):
        """Delete this problem from the VeloxQ platform.

        Raises:
            ValueError: If the problem cannot be deleted.

        """
        response = self._http.delete(f'problems/{self.id}')
        try:
            response.raise_for_status()
        except BaseException as e:
            msg = f'Failed to delete problem {self.id}'
            raise ValueError(msg) from e

    @classmethod
    def undefined(cls) -> Problem:
        """Retrieve or create a default "undefined" Problem instance.

        Used when no specific problem context was provided.

        Returns:
            Problem: The default Problem with the name "undefined".

        """
        response = cls._http.get('problems', params={'_page': 1, '_limit': 1, 'q': 'undefined'})
        response.raise_for_status()
        data = response.json()['data']
        if data:
            return cls.model_validate(data[0])

        return cls.create(name='undefined')

    @classmethod
    def create(cls, name: str) -> Problem:
        """Create a new problem.

        Args:
            name (str): The name for the new problem.

        Returns:
            Problem: The newly created Problem object as stored on the server.

        """
        response = cls._http.post('problems', json={'name': name})
        response.raise_for_status()
        data = response.json()
        return cls.model_validate(data)

    @classmethod
    def get_problems(cls, name: str | None = None, limit: int = 1000) -> list[Problem]:
        """Get all user problems, optionally filtering by name.

        Args:
            name (str | None): An optional query parameter to filter problems by name.
            limit (int): The maximum number of problems to return (default 1000).

        Returns:
            list[Problem]: A list of problems matching the query.

        """
        params: dict[str, int | str] = {'_page': 1, '_limit': limit}
        if name:
            params['q'] = name

        response = cls._http.get('problems', params=params)
        response.raise_for_status()
        data = response.json()['data']
        return [cls.model_validate(item) for item in data]

    @classmethod
    def from_id(cls, problem_id: str) -> Problem:
        """Create a Problem instance from an ID.

        Args:
            problem_id (str): The unique problem ID in the VeloxQ system.

        Returns:
            Problem: The matching Problem object, if found.

        """
        response = cls._http.get(f'problems/{problem_id}')
        response.raise_for_status()
        data = response.json()
        return cls.model_validate(data)


class File(BaseModel):
    """A class representing a file in the VeloxQ API [2].

    Files are associated with a specific problem and contain attributes such as
    name, size, and status. This class provides methods for uploading, downloading,
    and managing files on the VeloxQ platform.

    Attributes:
        name (str): The name of the file (with or without file extension).
        size (int): The total size of the file in bytes.
        uploaded_bytes (int): The number of bytes that have been uploaded so far.
        problem (Problem): The Problem instance to which this file belongs.
        created_at (datetime): The date/time this file was created.
        updated_at (Optional[datetime]): The date/time this file was last updated.
        status (str): The current status of this file upload (e.g., "completed").

    """

    name: str
    size: int = Field(description='The size of the file in bytes.')
    uploaded_bytes: int = Field(description='The number of bytes that have been uploaded.')
    problem: Problem = Field(description='The problem associated with this file.')
    created_at: datetime = Field(description='The date and time when the file was created.')
    updated_at: t.Optional[datetime] = Field(
        default=None,
        description='The date and time when the file was updated.',
    )
    status: str = Field(description='The status of the file upload.')

    def upload(self, content: t.IO, chunk_size: int = 1024 * 1024) -> None:
        """Upload content to this File via a WebSocket.

        Args:
            content (t.IO): A file-like object to read from.
            chunk_size (int): Size of each data chunk in bytes. Defaults to 1 MB.

        """
        with self.http.open_ws(
            f'problems/{self.problem.id}/files/{self.id}/upload/ws',
        ) as ws:
            while data := content.read(chunk_size):
                ws.send(data)
                ws.recv()
            ws.send(b'')
        self.refresh()

    def download(self, file: t.BinaryIO, chunk_size: int = 1024 * 1024) -> None:
        """Download the file content from VeloxQ and write it to a binary file-like object.

        Args:
            file (t.BinaryIO): The destination file-like object to write data to.
            chunk_size (int): Size of the data chunks to read. Defaults to 1 MB.

        """
        download_url = self.http.get(f'problems/{self.problem.id}/files/{self.id}')
        download_url.raise_for_status()
        with httpx.stream('GET', download_url.text.strip('"')) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes(chunk_size):
                file.write(chunk)

    def cancel(self) -> None:
        """Cancel the file upload on the VeloxQ platform."""
        response = self._http.delete(f'problems/{self.problem.id}/files/{self.id}/cancel')
        response.raise_for_status()
        self.refresh()

    def delete(self) -> None:
        """Delete this file from the VeloxQ platform."""
        response = self._http.delete(f'problems/{self.problem.id}/files/{self.id}')
        response.raise_for_status()

    def refresh(self) -> None:
        """Refresh the file data from the API."""
        response = self._http.get(
            f'/problems/{self.problem.id}/files/{self.id}/upload-status',
        )
        response.raise_for_status()
        data = response.json()
        self.model_update(data)

    @classmethod
    def create(cls, name: str, size: int, problem: Problem | None = None) -> File:
        """Create a new file on the VeloxQ platform.

        This method requests an upload URL for a new file, and returns the related File.
        The name must contain a valid extension (e.g., '.h5', '.txt', '.csv', ...).

        Args:
            name (str): The name of the file to create.
            size (int): The file size in bytes.
            problem (Problem | None): Optional problem to associate with. 
                If None, a default "undefined" problem is used.

        Returns:
            File: A File object representing the newly created entry on the server.

        """
        problem = problem or Problem.undefined()
        response = cls._http.post(
            f'problems/{problem.id}/files/upload-request',
            json={'file_name': name, 'size': size},
        )
        response.raise_for_status()
        data = response.json()
        data['problem'] = problem
        return cls.model_validate(data)

    @classmethod
    def get_files(cls, name: str | None, limit: int = 1000) -> list[File]:
        """Get all user files, optionally filtered by name.

        Args:
            name (str | None): Optional query string to filter files by name.
            limit (int): Maximum number of files to return. Default is 1000.

        """
        params: dict[str, int | str] = {
            '_page': 1,
            '_limit': limit,
            '_sort': 'created_at',
            'order': 'desc',
        }
        if name:
            params['q'] = name

        response = cls._http.get('files', params=params)
        response.raise_for_status()
        data = response.json()['data']
        return [cls.model_validate(item) for item in data]

    @classmethod
    def from_id(cls, file_id: str) -> File:
        """Get a File instance using a file's ID.

        Args:
            file_id (str): The unique identifier for the file.

        Returns:
            File: The matching File object.

        Raises:
            ValueError: If no file with the given ID is found.

        """
        response = cls._http.get(f'files/{file_id}')
        response.raise_for_status()
        data = response.json()
        return cls.model_validate(data)

    @classmethod
    def from_instance(
        cls,
        instance: InstanceLike,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        force: bool = False,
    ) -> File:
        """Create or retrieve a File instance.

        Multiple input types (File, Path, str, dict, or tuple) are supported.
        Path and str inpits are treated as file paths and so must contain
        a valid extension unless a name is provided.

        By default, if a file with the same name already exists,
        it will not be overwritten unless `force` is set to True.

        Args:
            instance (InstanceLike): This can be:
                - An existing File object.
                - A file path or string representing the file path.
                - A dictionary conforming to the InstanceDict structure.
                - A tuple conforming to InstanceTuple (biases, couplings).
            name (str | None): Optional file name to assign if creating a new file.
            problem (Problem | None): Optional Problem to associate with this file.
            force (bool): If True, overwrite existing files with the same
                          name and re-upload content.

        Returns:
            File: A File object representing the data source provided.

        Raises:
            TypeError: If the instance type is unrecognized.

        """
        if isinstance(instance, File):
            return instance
        if isinstance(instance, (Path, str)):
            return cls.from_path(
                path=instance,
                name=name,
                problem=problem,
                force=force,
            )
        if isinstance(instance, BinaryQuadraticModel):
            return cls.from_bqm(
                bqm=instance,
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
        """Create a File instance from a dictionary.

        The Dictonary must follow InstanceDict specification.

        Args:
            data (InstanceDict): Must contain "biases" and "couplings" keys.
            name (str | None): The file name. By default a hash-based name is generated.
            problem (Problem | None): Optional Problem to associate with.
            force (bool): If True, overwrite if a file with the same name exists.

        Returns:
            File: A File object representing the newly created Ising data file.

        """
        return cls.from_ising(
            biases=data['biases'],
            couplings=data['couplings'],
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
        """Create a File instance from a tuple.

        The tuple must contain two elements: biases and couplings.

        Args:
            data (InstanceTuple): A tuple (biases, couplings), where each element
                                  is a list, list-of-lists, or NumPy array.
            name (str | None): The file name. By default a hash-based name is generated.
            problem (Problem | None): Optional Problem to associate with.
            force (bool): If True, overwrite if a file with the same name exists.

        Returns:
            File: A newly created File containing the specified Ising data.

        """
        return cls.from_ising(
            biases=data[0],
            couplings=data[1],
            name=name,
            problem=problem,
            force=force,
        )

    @classmethod
    def from_bqm(
        cls,
        bqm: BinaryQuadraticModel,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        force: bool = False,
    ):
        """Create a File instance from a Binary Quadratic Model (BQM).

        This method converts the BQM into an Ising model format and uploads it.

        Args:
            bqm (BinaryQuadraticModel): The BQM to convert and upload.
            name (str | None): The file name. By default a hash-based name is generated.
            problem (Problem | None): Optional Problem to associate with.
            force (bool): If True, overwrite if a file with the same name exists.

        Returns:
            File: The resulting File object.

        """
        ising = bqm.spin

        return cls.from_ising(
            biases=ising.linear,
            couplings=ising.quadratic,
            name=name,
            problem=problem,
            force=force,
        )


    @classmethod
    def from_ising(
        cls,
        biases: BiasesType,
        couplings: CouplingsType,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        force: bool = False,
    ) -> File:
        """Create a File instance from Ising model.

        A temporary HDF5 file is created to store the Ising model data.
        The file is then uploaded to the VeloxQ platform, and a File object is returned.

        Args:
            biases (BiasesType): The bias terms in the Ising model.
            coupling (CouplingType): The coupling terms in the Ising model.
            name (str | None): The file name. By default a hash-based name is generated.
            problem (Problem | None): Optional Problem to associate with.
            force (bool): If True, overwrite if a file with the same name exists.

        Returns:
            File: The resulting File object.

        """
        if name:
            if (ext_idx := name.find('.')) != -1:
                name = name[:ext_idx]
            name += '.h5'

            if problem is None:
                existing_files = cls.get_files(name=name, limit=1)
            else:
                existing_files = problem.get_files(name=name, limit=1)

            if not force and existing_files:
                return existing_files[0]

        with TemporaryFile() as temp_file:
            if isinstance(biases, Linear) and isinstance(couplings, Quadratic):
                cls._write_dataset_dimod(temp_file, biases, couplings)
            elif isinstance(biases, dict) and isinstance(couplings, dict):
                cls._write_dataset_dict(temp_file, biases, couplings)
            elif isinstance(biases, (list, np.ndarray)) and isinstance(couplings, (list, np.ndarray)):
                cls._write_dataset_array(temp_file, biases, couplings)
            else:
                msg = (
                    'Unsupported data types for biases and couplings. '
                    'Expected lists, NumPy arrays, or dictionaries, or Linear and Quadratic.'
                )
                raise TypeError(msg)

            temp_file.flush()

            temp_file_size = temp_file.tell()
            temp_file.seek(0)

            name = name or (cls._create_hash(temp_file) + '.h5')
            if problem is None:
                existing_files = cls.get_files(name=name, limit=1)
            else:
                existing_files = problem.get_files(name=name, limit=1)
            if not force and existing_files:
                return existing_files[0]

            temp_file.seek(0)

            new_file = cls.create(name=name, size=temp_file_size, problem=problem)
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
        """Create a File instance from a local file path.

        This method uploads a file from the local filesystem to the VeloxQ platform.
        The path must contain a valid extension (e.g., '.h5', '.txt', '.csv', ...) in
        case a name is not provided. If a name is provided, it will be used
        regardless of the file's original name and must also contain a valid extension.

        Args:
            path (Path | str): The path to the file on the local filesystem.
            name (str | None): The file name. By default uses the path's filename.
            problem (Problem | None): Optional Problem to associate with.
            force (bool): If True, overwrite if a file with the same name exists.

        Returns:
            File: The newly created File object.

        Raises:
            FileNotFoundError: If the specified path does not exist.

        """
        path = Path(path)
        if not path.exists():
            msg = f'File {path} does not exist.'
            raise FileNotFoundError(msg)
        name = name or path.name

        if problem is None:
            existing_files = cls.get_files(name=name, limit=1)
        else:
            existing_files = problem.get_files(name=name, limit=1)
        if existing_files and not force:
            return existing_files[0]

        new_file = cls.create(name=name, size=path.stat().st_size, problem=problem)
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
        """Create a File instance directly from a binary IO stream.

        By default the data is considered to be in HDF5 format. To
        use a different format, the extension can be specified. If
        the name is provided and it contains an extension, it will
        be considered regardless of the extension parameter.

        Args:
            data (t.BinaryIO): The in-memory or file-like object containing
                the file's data.
            name (str | None): The file name. By default a hash-based name is generated.
            extension (str): The file extension to use if none is found
                in the name. Defaults to 'h5'.
            problem (Problem | None): Optional Problem to associate with.
            force (bool): If True, overwrite if a file with the same name exists.

        Returns:
            File: The File object created from the IO data.

        """
        if not name:
            data.seek(0)
            name = cls._create_hash(data)

        if name.find('.') == -1:
            name += f'.{extension}'

        if problem is None:
            existing_files = cls.get_files(name=name, limit=1)
        else:
            existing_files = problem.get_files(name=name, limit=1)
        if existing_files and not force:
            return existing_files[0]

        new_file = cls.create(name=name, size=data.seek(0, 2), problem=problem)
        data.seek(0)
        new_file.upload(data)
        return new_file

    @classmethod
    def model_validate(
        cls,
        obj: dict[str, t.Any],
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: t.Any = None,
    ) -> File:
        """Override model_validate to handle Problem association."""
        if 'problem' not in obj:
            obj['problem'] = Problem.from_id(obj['problemId'])
        return super().model_validate(
            obj, strict=strict, from_attributes=from_attributes, context=context,
        )

    @staticmethod
    def _create_hash(
        file: t.BinaryIO,
        chunk_size: int = 1024,
    ) -> str:
        """Create a SHA-256 hash of the file content.

        Args:
            file (BinaryIO): The file-like object to read from.
            chunk_size (int): The size of chunks read from the file. Defaults to 1 KB.

        Returns:
            str: The hexadecimal hash string of the file contents.

        """
        hasher = hashlib.sha256()
        while chunk := file.read(chunk_size):
            hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def _write_dataset_array(
        file: t.BinaryIO,
        biases: np.ndarray | list[BiasType],
        couplings: np.ndarray | list[list[CouplingType]],
    ) -> None:
        """Write the Ising model data to an HDF5 file.

        This method handles both NumPy arrays and lists for biases and couplings.

        Args:
            file (BinaryIO): The file-like object to write the data to.
            biases (np.ndarray | list[float]): The bias terms in the Ising model.
            couplings (np.ndarray | list[list[float]]): The coupling terms in the Ising model.

        """
        with h5py.File(file, 'w') as hdf:
            hdf.create_dataset('/Ising/biases', data=biases)
            hdf.create_dataset('/Ising/couplings', data=couplings)

    @staticmethod
    def _write_dataset_dict(
        file: t.BinaryIO,
        biases: t.Dict[int, float | np.floating],
        couplings: t.Dict[t.Tuple[int, int], float | np.floating],
    ) -> None:
        """Write the Ising model data to an HDF5 file.

        Args:
            file (BinaryIO): The file-like object to write the data to.
            biases (Dict[int, float]): A dictionary mapping qubit indices to bias values.
            couplings (Dict[Tuple[int, int], float]): A dictionary mapping pairs of qubit
                                                     indices to coupling values.

        """
        num_qubits = max(biases.keys(), default=0) + 1

        with h5py.File(file, 'w') as hdf:
            dataset = hdf.create_dataset(
                '/Ising/biases',
                shape=(num_qubits,),
                dtype=type(next(iter(biases.values()))),
            )
            for i in range(num_qubits):
                dataset[i] = biases.get(i, 0.0)

            coupling_matrix = hdf.create_dataset(
                '/Ising/couplings',
                shape=(num_qubits, num_qubits),
                dtype=type(next(iter(couplings.values()))),
            )
            for (i, j), value in couplings.items():
                coupling_matrix[i, j] = value
                coupling_matrix[j, i] = value

    @staticmethod
    def _write_dataset_dimod(
        file: t.BinaryIO,
        linear: Linear,
        quadratic: Quadratic,
    ) -> None:
        """Write the Ising model data to an HDF5 file using dimod.

        Args:
            file (BinaryIO): The file-like object to write the data to.
            linear (Linear): Linear biases.
            quadratic (Quadratic): Quadratic couplings.

        """
        variable0 = next(iter(linear))
        if not isinstance(variable0, (int, np.integer)):
            msg = 'Variables must be integers.'
            raise TypeError(msg)

        num_qubits = len(linear)

        with h5py.File(file, 'w') as hdf:
            dataset = hdf.create_dataset(
                '/Ising/biases',
                shape=(num_qubits,),
                dtype=type(linear[variable0]),
            )
            for var, val in linear.items():
                dataset[var] = val

            coupling_matrix = hdf.create_dataset(
                '/Ising/couplings',
                shape=(num_qubits, num_qubits),
                dtype=type(next(iter(quadratic.values()))),
            )
            for (i, j), value in quadratic.items():
                coupling_matrix[i, j] = value
                coupling_matrix[j, i] = value
