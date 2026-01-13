# Configuration

The VeloxQ client uses a global singleton configuration via the `VeloxQAPIConfig` class. This configuration can be applied in three ways:

- **Environment variables**
- **File-based configuration (Python or JSON)**
- **Direct programmatic modifications**

Since `VeloxQAPIConfig` is a **singleton**, the entire Python process shares one configuration (URL, token, etc.). If you need multiple independent configurations, spawn multiple processes and configure each process individually.

> **Note:** The only configuration variable not set by default is the **token**. It **must be configured** for authentication on the VeloxQ API platform.

## Environment Variables

Environment variables allow you to override configuration for the session. There are currently two variables:

- `VELOX_TOKEN`: Updates the token authentication.
- `VELOXQ_API_URL`: Updates the base URL used to connect to the API.

Example usage:

```shell
export VELOX_TOKEN="12345678-90ab-cdef-1234-567890abcdef"
```

When your Python code runs, these variables are automatically loaded. This configuration is used as the base, and extra configuration will be merged on top.

## File-Based Configuration

It's possible to load configuration from files in Python or JSON format. For instance:

```python
from veloxq_sdk.config import load_config

# JSON:
load_config("path/to/config.json")

# Python:
load_config("path/to/config.py")
```

Within a `.py` configuration file, you typically define a `c` object:

```python
c = get_config()
c.VeloxQAPIConfig.token = "12345678-90ab-cdef-1234-567890abcdef"
```

## Generating a Default Configuration

Developers can quickly generate a starter Python config file:

```python
from veloxq_sdk.config import generate_py_config_file

generate_py_config_file("veloxq_api_config.py")
```

The auto-generated file includes default attributes and docstrings for easy customization.

## Live Updates to Configuration

Because the configuration is a singleton (`VeloxQAPIConfig`), changes are global to the running session. For example:

```python
from veloxq_sdk.config import VeloxQAPIConfig

api_config = VeloxQAPIConfig.instance()
api_config.token = "NEW_TOKEN_VALUE"
```

All subsequent calls to the VeloxQ API will reflect this change.
