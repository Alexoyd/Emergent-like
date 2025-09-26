# stacks/__init__.py
"""Importing this package registers all default stack handlers."""
from . import registry as _registry # noqa: F401
from .laravel_handler import LaravelHandler # noqa: F401
from .react_handler import ReactHandler # noqa: F401
from .vue_handler import VueHandler # noqa: F401
from .python_handler import PythonHandler # noqa: F401
from .node_handler import NodeHandler # noqa: F401