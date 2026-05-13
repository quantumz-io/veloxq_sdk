"""VeloxQ API Problems Module.

This module provides classes and methods for interacting with the VeloxQ API, focusing on
Problem and File entities. These classes enable creating, retrieving, uploading, downloading,
and managing files and problems within the VeloxQ platform.
"""

from __future__ import annotations

import hashlib
import logging
import typing as t
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
import httpx
from pydantic.alias_generators import to_camel
from pydantic import BaseModel as PydanticBaseModel
from typing_extensions import TypedDict
from concurrent.futures import ThreadPoolExecutor

import h5py
import numpy as np
from dimod import BinaryQuadraticModel
from dimod.views.quadratic import Linear, Quadratic
from dimod.sampleset import SampleSet
from pydantic import Field, TypeAdapter

from veloxq_sdk.api.core.base import BaseModel, build_adapters
from veloxq_sdk.config import VeloxQAPIConfig

_logger = logging.getLogger(__name__)

InstanceLike = t.Union[
    "InstanceDict",
    "InstanceTuple",
    "File",
    Path,
    str,
    BinaryQuadraticModel,
]

BiasType = t.Union[float, np.number]
CouplingType = BiasType

VariableType = t.Hashable

BiasesType = t.Union[
    t.List[BiasType],
    np.ndarray[tuple[int], np.dtype[np.number]],
    t.Dict[VariableType, BiasType],
    Linear,
]
CouplingsType = t.Union[
    t.List[t.List[CouplingType]],
    np.ndarray[tuple[int, int], np.dtype[np.number]],
    t.Dict[t.Tuple[VariableType, ...], CouplingType],
    Quadratic,
]

InstanceTuple = t.Tuple[BiasesType, CouplingsType]

if t.TYPE_CHECKING:
    class _NormalizedIsingModel(t.TypedDict):
        biases: np.ndarray[tuple[int], np.dtype[np.number]]
        rows: np.ndarray[tuple[int], np.dtype[np.integer]]
        cols: np.ndarray[tuple[int], np.dtype[np.integer]]
        values: np.ndarray[tuple[int], np.dtype[np.number]]
        labels: np.ndarray[tuple[int], np.dtype[np.str_]]
        idx_dtype: np.dtype[np.integer]
        size: int
        offset: float


SPARSE_THRESHOLD = 0.15


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


@build_adapters
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

    name: str = Field(description="The name of the problem.")
    created_at: datetime = Field(
        description="The date and time when the problem was created."
    )
    updated_at: datetime = Field(
        description="The date and time when the problem was last updated."
    )

    def get_files(
        self, name: str | None = None, limit: int = 1000, *, exact: bool = False
    ) -> list[File]:
        """Get all files associated with this problem.

        Args:
            name (str | None): Optional query string to filter files by name.
            limit (int): Maximum number of files to return (default 1000).
            exact (bool): If True, only return files with names exactly matching
                          the provided name.

        Returns:
            list[File]: A list of files that belong to this problem.

        """
        params: dict[str, int | str] = {
            "_limit": limit,
            "_sort": "created_at",
            "_order": "desc",
        }
        if name:
            params["q"] = name

        response = self._http.get(f"problems/{self.id}/files", params=params)
        response.raise_for_status()
        data = File._from_paginated_response(response)

        if exact:
            return list(filter(lambda item: item.name == name, data))

        return data

    def new_file(self, name: str, size: int) -> File:
        """Create a new file for this problem.

        Args:
            name (str): The name of the file to create.
            size (int): The file size in bytes.

        Returns:
            File: A File object that references the newly created file on the server.

        """
        return File.create(name=name, size=size, problem=self)

    @classmethod
    def undefined(cls) -> Problem:
        """Retrieve or create a default "undefined" Problem instance.

        Used when no specific problem context was provided.

        Returns:
            Problem: The default Problem with the name "undefined".

        """
        response = cls._http.get(
            "problems", params={"_page": 1, "_limit": 1, "q": "undefined"}
        )
        response.raise_for_status()
        data = cls._from_paginated_response(response)
        if data:
            return data[0]

        return cls.create(name="undefined")

    @classmethod
    def create(cls, name: str) -> Problem:
        """Create a new problem.

        Args:
            name (str): The name for the new problem.

        Returns:
            Problem: The newly created Problem object as stored on the server.

        """
        response = cls._http.post("problems", json={"name": name})
        return cls._from_response(response)

    @classmethod
    def get_problems(
        cls, name: str | None = None, limit: int = 1000
    ) -> t.Sequence[Problem]:
        """Get all user problems, optionally filtering by name.

        Args:
            name (str | None): An optional query parameter to filter problems by name.
            limit (int): The maximum number of problems to return (default 1000).

        Returns:
            list[Problem]: A list of problems matching the query.

        """
        params: dict[str, int | str] = {"_page": 1, "_limit": limit}
        if name:
            params["q"] = name

        response = cls._http.get("problems", params=params)
        response.raise_for_status()
        return cls._from_paginated_response(response)

    @classmethod
    def from_id(cls, problem_id: int) -> Problem:
        """Create a Problem instance from an integer ID.

        Args:
            problem_id (int): The unique problem ID in the VeloxQ system.

        Returns:
            Problem: The matching Problem object, if found.

        """
        response = cls._http.get(f"problems/{problem_id}")
        return cls._from_response(response)


@build_adapters
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
    size: int = Field(description="The size of the file in bytes.")
    uploaded_bytes: int = Field(
        description="The number of bytes that have been uploaded."
    )
    problem_id: str = Field(description="The problem id associated with this file.")
    created_at: datetime = Field(
        description="The date and time when the file was created."
    )
    updated_at: t.Optional[datetime] = Field(
        default=None,
        description="The date and time when the file was updated.",
    )
    status: str = Field(description="The status of the file upload.")

    class _PreassignedChunkUploader(PydanticBaseModel):
        """Helper class for multipart chunked uploads."""

        class Config:
            alias_generator = to_camel
            validate_by_alias = True
            validate_by_name = True

        class _PreasignedUploadChunk(TypedDict):
            """Represents a single chunk in a multipart upload."""

            part_number: int
            upload_url: str
            expires_at: datetime

        file: File
        chunks: list[_PreasignedUploadChunk]

        def upload(
            self,
            file_path: Path,
            callback: t.Callable[[int], None] = lambda _: None,
        ) -> File:
            config = VeloxQAPIConfig.instance()
            uploaded_chunks = []

            def _callback(
                item: tuple[dict[str, t.Any], int],
            ) -> dict[str, t.Any]:
                callback(item[1])
                return item[0]

            with ThreadPoolExecutor(config.multipart_upload_thread_count) as executor:
                uploaded_chunks = list(
                    map(
                        _callback,
                        executor.map(
                            self.upload_part,
                            [file_path] * len(self.chunks),
                            self.chunks,
                        ),
                    )
                )
            response = self.file._http.post(
                f"/problems/{self.file.problem_id}/files/{self.file.id}/direct/complete",
                json={
                    "parts": uploaded_chunks,
                },
            )
            return self.file._update_from_response(response)

        def upload_part(
            self, file_path: Path, chunk: _PreasignedUploadChunk
        ) -> tuple[dict[str, t.Any], int]:
            if datetime.now(timezone.utc) > chunk["expires_at"]:
                msg = (
                    f"Upload URL for part {chunk['part_number']} has expired. "
                    "Please request a new upload URL and retry the upload."
                )
                raise ValueError(msg)
            chunk_size = self.file.size // len(self.chunks)
            with file_path.open("rb") as f:
                f.seek((chunk["part_number"] - 1) * chunk_size)
                data = f.read(chunk_size)
            response = httpx.put(chunk["upload_url"], content=data, timeout=3600)
            response.raise_for_status()
            etag = response.headers.get("ETag")
            if etag is None:
                msg = f"ETag header missing in response for part {chunk['part_number']}"
                raise RuntimeError(msg)
            return {"part_number": chunk["part_number"], "etag": etag}, len(data)

    class _PreassignedUploader(PydanticBaseModel):
        """Helper class for multipart chunked uploads."""

        class Config:
            alias_generator = to_camel
            validate_by_alias = True
            validate_by_name = True

        file: File
        upload_url: str
        expires_at: datetime

        def upload(
            self,
            file_path: Path,
            callback: t.Callable[[int], None] = lambda _: None,
        ) -> File:
            if datetime.now(timezone.utc) > self.expires_at:
                msg = (
                    "Upload URL has expired. Please request a new ",
                    "upload URL and retry the upload.",
                )
                raise ValueError(msg)
            with file_path.open("rb") as f:
                data = f.read()
            httpx.put(self.upload_url, content=data, timeout=3600).raise_for_status()
            callback(len(data))
            response = self.file._http.post(
                f"/problems/{self.file.problem_id}/files/{self.file.id}/direct/complete",
                json={},
            )
            return self.file._update_from_response(response)

    _uploader: t.ClassVar[TypeAdapter] = TypeAdapter(
        t.Union[_PreassignedUploader, _PreassignedChunkUploader],
    )

    def upload(
        self,
        content: t.IO,
        chunk_size: int = 1024 * 1024,
        upload_callback: t.Callable[[int], None] = lambda _: None,
    ) -> None:
        """Upload content to this File via a WebSocket.

        Args:
            content (t.IO): A file-like object to read from.
            chunk_size (int): Size of each data chunk in bytes. Defaults to 1 MB.
            upload_callback (t.Callable[[int], None]): A callback function to report upload progress.

        """
        with self.http.open_ws(
            f"problems/{self.problem_id}/files/{self.id}/upload/ws",
        ) as ws:
            while data := content.read(chunk_size):
                ws.send(data)
                ws.recv()
                upload_callback(len(data))
            ws.send(b"")
        self.refresh()

    def download(self, file: t.BinaryIO, chunk_size: int = 1024 * 1024) -> None:
        """Download the file content from VeloxQ and write it to a binary file-like object.

        Args:
            file (t.BinaryIO): The destination file-like object to write data to.
            chunk_size (int): Size of the data chunks to read. Defaults to 1 MB.

        """
        download_url = self.http.get(f"problems/{self.problem_id}/files/{self.id}")
        download_url.raise_for_status()
        with self.http.stream(
            "GET", download_url.text.strip("'").strip('"')
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes(chunk_size):
                file.write(chunk)

    def cancel(self) -> None:
        """Cancel the file upload on the VeloxQ platform."""
        response = self._http.delete(
            f"problems/{self.problem_id}/files/{self.id}/cancel"
        )
        response.raise_for_status()
        self.refresh()

    def delete(self) -> None:
        """Delete this file from the VeloxQ platform."""
        response = self._http.delete(f"problems/{self.problem_id}/files/{self.id}")
        response.raise_for_status()

    def refresh(self) -> None:
        """Refresh the file data from the API."""
        response = self._http.get(
            f"/problems/{self.problem_id}/files/{self.id}/upload-status",
        )
        self._update_from_response(response)

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
            f"problems/{problem.id}/files/upload-request",
            json={"file_name": name, "size": size},
        )
        return cls._from_response(response)

    @classmethod
    def create_direct(
        cls,
        name: str,
        size: int,
        problem: Problem | None = None,
    ) -> _PreassignedUploader | _PreassignedChunkUploader:
        """Initiate a upload for a new file and retrieve the upload plan.

        This method requests a upload plan for a new file, which includes
        pre-signed URLs.

        Args:
            name (str): The name of the file to create.
            size (int): The total file size in bytes.
            problem (Problem | None): Optional problem to associate with.
                If None, a default "undefined" problem is used.

        Returns:
            _PreassignedUploader | _PreassignedChunkUploader: An object containing the file reference and upload plan.

        """
        settings = VeloxQAPIConfig.instance()
        if size <= settings.max_single_upload_size:
            num_chunks = 0
        else:
            num_chunks = size // settings.multipart_upload_chunk_size + bool(
                size % settings.multipart_upload_chunk_size
            )
        problem = problem or Problem.undefined()
        response = cls._http.post(
            f"problems/{problem.id}/files/direct",
            json={"file_name": name, "size": size, "num_chunks": num_chunks},
        )
        response.raise_for_status()
        return cls._uploader.validate_json(response.content)

    @classmethod
    def get_files(
        cls, name: str | None, limit: int = 1000, *, exact: bool = False
    ) -> t.Sequence[File]:
        """Get all user files, optionally filtered by name.

        Args:
            name (str | None): Optional query string to filter files by name.
            limit (int): Maximum number of files to return. Default is 1000.
            exact (bool): If True, only return files with names exactly matching
                                the provided name.

        """
        params: dict[str, int | str] = {
            "_limit": limit,
            "_sort": "created_at",
            "_order": "desc",
        }
        if name:
            params["q"] = name

        response = cls._http.get("files", params=params)
        response.raise_for_status()
        data = cls._from_paginated_response(response)
        if exact:
            return list(filter(lambda item: item.name == name, data))
        return data

    @classmethod
    def get_file(cls, name: str, problem: Problem | None = None) -> File | None:
        """Get a single File instance by name.

        Args:
            name (str): The name of the file to retrieve.
            problem (Problem | None): Optional Problem to scope the search within.

        Returns:
            File | None: The matching File object, or None if not found.

        """
        if problem is None:
            problem = Problem.undefined()

        existing_files = problem.get_files(name=name, limit=1, exact=True)
        if existing_files:
            return existing_files[0]
        return None

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
        response = cls._http.get(f"files/{file_id}")
        return cls._from_response(response)

    @classmethod
    def from_instance(
        cls,
        instance: InstanceLike,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        init_state: SampleSet | None = None,
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
            if init_state is not None:
                _logger.warning(
                    'Cannot pass initial state when using a File instance'
                )
            return instance
        if isinstance(instance, (Path, str)):
            if init_state is not None:
                _logger.warning(
                    'Cannot pass initial state when using instance path'
                )
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
                init_state=init_state,
                force=force,
            )
        if isinstance(instance, dict):
            return cls.from_dict(
                data=instance,
                name=name,
                problem=problem,
                init_state=init_state,
                force=force,
            )
        if isinstance(instance, tuple):
            return cls.from_tuple(
                data=instance,
                name=name,
                problem=problem,
                init_state=init_state,
                force=force,
            )

        msg = (
            f"Unsupported instance type: {type(instance)}. "
            "Expected a File, Path, str, dict, or tuple."
        )
        raise TypeError(msg)

    @classmethod
    def from_dict(
        cls,
        data: InstanceDict,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        init_state: SampleSet | None = None,
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
            biases=data["biases"],
            couplings=data["couplings"],
            name=name,
            problem=problem,
            init_state=init_state,
            force=force,
        )

    @classmethod
    def from_tuple(
        cls,
        data: InstanceTuple,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        init_state: SampleSet | None = None,
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
            init_state=init_state,
            force=force,
        )

    @classmethod
    def from_bqm(
        cls,
        bqm: BinaryQuadraticModel,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        init_state: SampleSet | None = None,
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
            init_state=init_state,
            force=force,
            offset=ising.offset,
        )

    @classmethod
    def from_ising(
        cls,
        biases: BiasesType,
        couplings: CouplingsType,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        init_state: SampleSet | None = None,
        force: bool = False,
        offset: float = 0.0,
        upload_callback: t.Callable[[int], None] = lambda _: None,
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
            offset (float): Energy offset carried in the Ising model. Defaults to 0.0.
            upload_callback (t.Callable[[int], None]): A callback function to report upload progress.

        Returns:
            File: The resulting File object.

        """
        if name:
            if (ext_idx := name.find(".")) != -1:
                name = name[:ext_idx]
            name += ".h5"
            if not force and (file := cls.get_file(name=name, problem=problem)):
                return file

        with NamedTemporaryFile() as temp_file:
            cls._write_ising_hdf5(temp_file, biases, couplings, init_state=init_state, offset=offset)

            temp_file.flush()

            temp_file_size = temp_file.tell()
            temp_file.seek(0)

            name = name or (cls._create_hash(temp_file) + ".h5")
            if not force and (file := cls.get_file(name=name, problem=problem)):
                return file

            temp_file.seek(0)

            file_uploader = cls.create_direct(
                name=name, size=temp_file_size, problem=problem
            )
            return file_uploader.upload(Path(temp_file.name), callback=upload_callback)

    @classmethod
    def from_path(
        cls,
        path: Path | str,
        name: str | None = None,
        problem: Problem | None = None,
        *,
        force: bool = False,
        upload_callback: t.Callable[[int], None] = lambda _: None,
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
            upload_callback (t.Callable[[int], None]): A callback function to report upload progress.

        Returns:
            File: The newly created File object.

        Raises:
            FileNotFoundError: If the specified path does not exist.

        """
        path = Path(path)
        if not path.exists():
            msg = f"File {path} does not exist."
            raise FileNotFoundError(msg)
        name = name or path.name

        if not force and (file := cls.get_file(name=name, problem=problem)):
            return file

        file_uploader = cls.create_direct(
            name=name, size=path.stat().st_size, problem=problem
        )
        return file_uploader.upload(path, callback=upload_callback)

    @classmethod
    def from_io(
        cls,
        data: t.BinaryIO,
        name: str | None = None,
        extension: str = "h5",
        problem: Problem | None = None,
        *,
        force: bool = False,
        upload_callback: t.Callable[[int], None] = lambda _: None,
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
            upload_callback (t.Callable[[int], None]): A callback function to report upload progress.
        Returns:
            File: The File object created from the IO data.

        """
        if not name:
            data.seek(0)
            name = cls._create_hash(data)

        if name.find(".") == -1:
            name += f".{extension}"

        if not force and (file := cls.get_file(name=name, problem=problem)):
            return file

        new_file = cls.create(name=name, size=data.seek(0, 2), problem=problem)
        data.seek(0)
        new_file.upload(data)
        return new_file

    @staticmethod
    def _create_hash(
        file: t.IO,
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
    def _write_ising_hdf5(
        file: t.IO,
        biases: BiasesType | Linear,
        couplings: CouplingsType | Quadratic,
        *,
        init_state: SampleSet | None = None,
        offset: float = 0.0,
    ) -> None:
        """Serialize Ising data into the solver-compatible HDF5 layout.

        Group `Ising` with attributes `sparsity`, `type`, `var_type`, and datasets
        `biases`, `L`, and a sparse CSC-encoded `couplings` subgroup (I, J, V, dims)
        if sparse, or a dense `couplings` dataset if dense.
        Labels are stored as strings for round-tripping non-integer variables.
        Sparse indices are stored 1-based to match the solver reader.
        """
        normalized = File._normalize_ising_inputs(biases, couplings, offset=offset)
        with h5py.File(file, "w") as hdf:
            group = hdf.require_group("Ising")
            group.attrs["type"] = "BinaryQuadraticModel"
            group.attrs["var_type"] = "SPIN"
            group.attrs["offset"] = float(normalized["offset"])

            group.create_dataset("biases", data=normalized["biases"])
            group.create_dataset("L", data=np.array(normalized["size"], dtype=np.int64))

            label_dtype = h5py.string_dtype("utf-8")
            group.create_dataset(
                "labels",
                data=np.array(
                    [str(label) for label in normalized["labels"]], dtype=label_dtype
                ),
            )

            # Decide sparse vs dense based on coupling density.
            total_entries = max(1, normalized["size"] * normalized["size"])
            density = (total_entries - len(normalized["values"])) / total_entries
            if density >= SPARSE_THRESHOLD:
                group.attrs["sparsity"] = "sparse"
                couplings_group = group.create_group("couplings")
                couplings_group.attrs["type"] = "SparseMatrixCSC"
                couplings_group.create_dataset(
                    "dims",
                    data=np.array(
                        [normalized["size"], normalized["size"]], dtype=np.int64
                    ),
                )
                couplings_group.create_dataset(
                    "I", data=normalized["rows"], dtype=np.int64
                )
                couplings_group.create_dataset(
                    "J", data=normalized["cols"], dtype=np.int64
                )
                couplings_group.create_dataset(
                    "V", data=normalized["values"], dtype=normalized["dtype"]
                )
            else:
                group.attrs["sparsity"] = "dense"
                dense = np.zeros(
                    (normalized["size"], normalized["size"]), dtype=normalized["dtype"]
                )
                # rows/cols are 1-based; convert to 0-based for assignment
                if len(normalized["values"]):
                    dense[normalized["rows"] - 1, normalized["cols"] - 1] = normalized[
                        "values"
                    ]
                group.create_dataset("couplings", data=dense)

            # Include the initial state as spectrum
            if init_state is not None:
                states = init_state.record.sample
                energies = init_state.record.energy
                num_rep = energies.shape[0]
                size = normalized["size"]
                if energies.shape != (num_rep,) or states.shape != (num_rep, size):
                    msg = "Initial SampleSet needs to have consistent size and fit the instance."
                    raise TypeError(msg)
                spectrum = hdf.require_group("Spectrum")
                spectrum.create_dataset("L", data=np.array(size, dtype=np.int64))
                spectrum.create_dataset("num_rep", data=np.array(num_rep, dtype=np.int64))
                spectrum.create_dataset("energies", data=energies.astype(normalized["dtype"]))
                spectrum.create_dataset("states", data=states.astype(normalized["dtype"]))

    @staticmethod
    def _normalize_ising_inputs(
        biases: BiasesType,
        couplings: CouplingsType,
        *,
        offset: float = 0.0,
    ) -> _NormalizedIsingModel:
        """Normalize heterogeneous Ising inputs into arrays for HDF5 serialization."""
        if isinstance(biases, (Linear, dict)):
            biases_dict = dict(biases)
        elif isinstance(biases, (list, np.ndarray)):
            bias_array = np.asarray(biases)
            if bias_array.ndim != 1:
                msg = "Biases array must be one-dimensional or a dict of labels and biases."
                raise TypeError(msg)
            biases_dict: dict[VariableType, BiasType] = {i: bias_array[i] for i in range(len(bias_array))}
        else:
            msg = "Unsupported bias type. Expected Linear, dict, list, or ndarray."
            raise TypeError(msg)

        # Process couplings - optimize array case with vectorization
        if isinstance(couplings, (Quadratic, dict)):
            coupling_items = list(couplings.items())
        elif isinstance(couplings, (list, np.ndarray)):
            coupling_array = np.asarray(couplings)
            if (
                coupling_array.ndim != 2
                or coupling_array.shape[0] != coupling_array.shape[1]
            ):
                msg = "Couplings array must be square."
                raise TypeError(msg)
            # Vectorized extraction of nonzero elements
            nz_rows, nz_cols = np.nonzero(coupling_array)
            coupling_items = [((i, j), coupling_array[i, j]) for i, j in zip(nz_rows, nz_cols)]
        else:
            msg = (
                "Unsupported coupling type. Expected Quadratic, dict, list, or ndarray."
            )
            raise TypeError(msg)

        couplings_dict: dict[tuple[VariableType, ...], CouplingType] = {}
        for key, val in coupling_items:
            # Ensure biases exist for all variables in couplings
            if len(key) == 1:
                canonical_key = key
                if key[0] not in biases_dict:
                    biases_dict[key[0]] = 0.0
            elif len(key) == 2:
                # Canonical ordering: min index first
                canonical_key = (min(key), max(key)) if key[0] != key[1] else (key[0],)
                for i in key:
                    if i not in biases_dict:
                        biases_dict[i] = 0.0
            else:
                msg = f"Coupling key must have 1 or 2 elements, got {len(key)}"
                raise ValueError(msg)

            # Check for conflicts only when key already exists
            if canonical_key in couplings_dict:
                existing = couplings_dict[canonical_key]
                if not np.isclose(existing, val):
                    u, v = canonical_key if len(canonical_key) == 2 else (canonical_key[0], canonical_key[0])
                    msg = f"Symmetric couplings contain mismatched values for pair ({u}, {v}): {existing} vs {val}"
                    raise ValueError(msg)
            else:
                couplings_dict[canonical_key] = val

        if not biases_dict:
            msg = "Empty instance"
            raise ValueError(msg)

        # Create label mapping
        label_to_idx = {label: idx for idx, label in enumerate(biases_dict.keys())}
        size = len(label_to_idx)
        idx_dtype: np.dtype[np.integer] = np.min_scalar_type(size)

        # Estimate size: diagonal + off-diagonal elements (symmetrized)
        num_couplings = len(couplings_dict)
        # Count off-diagonal elements for proper pre-allocation
        num_off_diag = sum(1 for key in couplings_dict.keys() if len(key) == 2)
        total_entries = num_couplings + num_off_diag  # diagonal + 2x off-diagonal

        rows_list = np.empty(total_entries, dtype=idx_dtype)
        cols_list = np.empty(total_entries, dtype=idx_dtype)
        values_list = np.empty(total_entries, dtype=float)

        idx = 0
        max_value = -np.inf
        for key, val in couplings_dict.items():
            if len(key) == 1:
                u = key[0]
                i = label_to_idx[u]
                rows_list[idx] = i + 1
                cols_list[idx] = i + 1
                values_list[idx] = val
                idx += 1
            else:  # len(key) == 2
                u, v = key
                i = label_to_idx[u]
                j = label_to_idx[v]
                # Upper triangle entry
                rows_list[idx] = i + 1
                cols_list[idx] = j + 1
                values_list[idx] = val
                idx += 1
                # Lower triangle entry (symmetric)
                rows_list[idx] = j + 1
                cols_list[idx] = i + 1
                values_list[idx] = val
                idx += 1

            max_value = max(max_value, abs(val))

        # Trim to actual size
        rows_list = rows_list[:idx]
        cols_list = cols_list[:idx]
        values_list = values_list[:idx]

        # Sort by column-major order
        order = np.lexsort((rows_list, cols_list))
        rows_arr = rows_list[order]
        cols_arr = cols_list[order]

        # Select float32 or float64 for Solver compatibility
        # Use float32 if values fit, otherwise float64 for precision
        value_dtype = np.min_scalar_type(max_value if max_value != -np.inf else 0.0)
        if value_dtype.kind == "f" and value_dtype.itemsize < 4:
            value_dtype = np.float32
        values_arr = values_list[order].astype(value_dtype)

        # Convert biases to array efficiently
        bias_vals = np.array(list(biases_dict.values()), dtype=float)
        bias_dtype = np.min_scalar_type(np.abs(bias_vals).max())
        if bias_dtype.kind == "f" and bias_dtype.itemsize < 4:
            bias_dtype = np.float32
        bias_arr = bias_vals.astype(bias_dtype)

        # Convert labels to array of strings for HDF5 compatibility
        labels = np.fromiter(map(str, biases_dict.keys()), dtype=np.dtype("T"))

        return {
            "biases": bias_arr,
            "rows": rows_arr,
            "cols": cols_arr,
            "values": values_arr,
            "labels": labels,
            "idx_dtype": idx_dtype,
            "size": size,
            "offset": offset,
        }
