"""VeloxQ Client Configuration.

This module provides utilities for configuring the VeloxQ API client.
It includes classes and functions to manage and load configuration,
including environment-based overrides and file-based configuration
(through JSON and Python config files).

Usage Example:
    from traitlets.config import Config
    from veloxq_client_config import load_config
    # Create or update configuration programmatically:
    c = Config()
    c.VeloxQAPIConfig.token = "12345678-90ab-cdef-1234-567890abcdef"
    load_config(c)

Usage with Files:
    # Load configuration from a file:
    from veloxq_client_config import load_config
    load_config("path/to/config.json")
    # or
    load_config("path/to/config.py")

Modifying Directly:
    from veloxq_client_config import VeloxQAPIConfig
    config = VeloxQAPIConfig.instance()
    config.url = "https://api.veloxq.com"

Generating Default Config File:
    from veloxq_client_config import generate_py_config_file
    generate_py_config_file("veloxq_api_config.py")
"""
from __future__ import annotations

import json
import logging
import os
import typing as t
from pathlib import Path

from traitlets import Bool, List, Unicode
from traitlets.config import (
    Config,
    ConfigFileNotFound,
    DeferredConfigString,
    JSONFileConfigLoader,
    PyFileConfigLoader,
    SingletonConfigurable,
)
from traitlets.config.application import TRAITLETS_APPLICATION_RAISE_CONFIG_FILE_ERROR

if t.TYPE_CHECKING:
    ConfigLike = t.Union[Config, t.Dict[str, t.Any], Path, str]

_logger = logging.getLogger(__name__)


class VeloxQAPIConfig(SingletonConfigurable):
    """Configuration class for the VeloxQ API client."""

    name = 'veloxq-api-sdk'

    url = Unicode('https://api-dev.veloxq.com',
                  config=True,
                  help='Base URL for the VeloxQ API.')

    token = Unicode(allow_none=False, config=True,
                    help='API token for authentication with the VeloxQ service.')


    raise_config_file_errors = Bool(TRAITLETS_APPLICATION_RAISE_CONFIG_FILE_ERROR)

    _loaded_config_files: List[str] = List()

    python_config_loader_class = PyFileConfigLoader
    json_config_loader_class = JSONFileConfigLoader

    def __init__(self, **kwargs: t.Any) -> None:
        """Initialize the VeloxQAPIConfig."""
        super().__init__(**kwargs)
        self.load_config_environ()

    def load_config_environ(self) -> None:
        """Load config files by environment."""
        prefix = self.name.upper().replace('-', '_')
        new_config = Config()

        self.log.debug('Looping through config variables with prefix "%s"', prefix)

        for k, v in os.environ.items():
            if k.startswith(prefix):
                self.log.debug('Seeing environ "%s"="%s"', k, v)
                # use __ instead of . as separator in env variable.
                # Warning, case sensitive !
                _, *path, key = k.split("__")
                section = new_config
                for p in path:
                    section = section[p]
                setattr(section, key, DeferredConfigString(v))
        self.update_config(new_config)

    def load_config_file(
        self, filename: str, path: str | t.Sequence[str | None] | None = None
    ) -> None:
        """Load config files by filename and path."""
        filename, ext = os.path.splitext(filename)  # noqa: PTH122
        new_config = Config()
        for config, fname in self._load_config_files(
            filename,
            path=path,
            raise_config_file_errors=self.raise_config_file_errors,
        ):
            new_config.merge(config)
            if (
                fname not in self._loaded_config_files
            ):  # only add to list of loaded files if not previously loaded
                self._loaded_config_files.append(fname)
        self.update_config(new_config)

    @classmethod
    def _load_config_files(
        cls,
        basefilename: str,
        path: str | t.Sequence[str | None] | None,
        *,
        raise_config_file_errors: bool = False,
    ) -> t.Generator[t.Any, None, None]:
        """Load config files (py,json) by filename and path.

        yield each config object in turn.
        """
        if isinstance(path, str) or path is None:
            path = [path]
        for current in reversed(path):
            # path list is in descending priority order, so load files backwards:
            pyloader = cls.python_config_loader_class(basefilename + '.py',
                                                      path=current)
            _logger.debug('Looking for %s in %s', basefilename, current or Path.cwd())
            jsonloader = cls.json_config_loader_class(basefilename + '.json',
                                                      path=current)
            loaded: list[t.Any] = []
            filenames: list[str] = []
            for loader in [pyloader, jsonloader]:
                if config := cls.__load_config(
                    loader, basefilename, raise_config_file_errors
                ):
                    for filename, earlier_config in zip(filenames, loaded):
                        collisions = earlier_config.collisions(config)
                        if collisions:
                            _logger.warning(
                                'Collisions detected in {0} and {1} config files.'  # noqa: G001, UP032
                                ' {1} has higher priority: {2}'.format(
                                filename,
                                loader.full_filename,
                                json.dumps(collisions, indent=2)),
                            )
                    yield (config, loader.full_filename)
                    loaded.append(config)
                    filenames.append(loader.full_filename)

    @staticmethod
    def __load_config(loader: JSONFileConfigLoader | PyFileConfigLoader,
                      basefilename: str,
                      raise_config_file_errors: bool) -> Config | None:
        try:
            return loader.load_config()
        except ConfigFileNotFound:
            pass
        except Exception:
            # try to get the full filename, but it will be empty in the
            # unlikely event that the error raised before filefind finished
            filename = loader.full_filename or basefilename
            # problem while running the file
            if raise_config_file_errors:
                raise
            _logger.error('Exception while loading config file %s', filename,  # noqa: G201
                          exc_info=True)
        else:
            _logger.debug('Loaded config file: %s', loader.full_filename)


def load_config(config: ConfigLike) -> None:
    """Load configuration for the VeloxQ API SDK."""
    api_config = VeloxQAPIConfig.instance()

    if isinstance(config, Config):
        api_config.update_config(config)
    elif isinstance(config, dict):
        api_config.config.merge(config)
        api_config.update_config(api_config.config)
    elif isinstance(config, Path):
        api_config.load_config_file(config.name, path=str(config.parent))
    elif isinstance(config, str):
        path = Path(config)
        api_config.load_config_file(path.name, path=str(path.parent))
    else:
        msg = (
            f'Unsupported config type: {type(config)}. '
            'Expected a ConfigLike object.'
        )
        raise TypeError(msg)


def generate_py_config_file(
    filename: str | Path,
) -> None:
    """Generate default config file for the VeloxQ API SDK."""
    lines = [f'# Configuration file for {VeloxQAPIConfig.name}.']
    lines.append('')
    lines.append('c = get_config()  #' + 'noqa')
    lines.append('')
    for _, v in sorted(VeloxQAPIConfig.class_traits(config=True).items()):
        config_str = f'c.VeloxQAPIConfig.{v.name} = {v.default_value!r}'
        lines.append(config_str)

        if help_str := VeloxQAPIConfig.class_get_trait_help(v).splitlines():
            lines[-1] += f'  # {help_str[0]}'
            spaces = ' '*len(config_str)
            lines.extend(
                f'{spaces}  # {line}' for line in help_str[1:] if line.strip()
            )
            lines.append('')

    with open(filename, 'w') as f:
        f.write('\n'.join(lines))
    _logger.info('Generated config file: %s', filename)
