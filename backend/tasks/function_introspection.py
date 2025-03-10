"""Handles function introspection"""

import importlib
import inspect
import logging
import os
import pkgutil
from typing import Any, Callable, Dict, Optional, Union, get_type_hints

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class FunctionInfo(BaseModel):
    """Information about a discovered function."""

    module_name: str
    function_name: str
    full_path: str
    doc: Optional[str]
    is_async: bool
    parameters: Dict[str, Dict[str, Any]]
    return_type: Optional[str]


class FunctionDiscovery:
    """
    Handles function discovery and introspection.
    Don't initialize, use functions
    """

    def __init__(self, root_module: str):
        self.discovered_functions: Dict[str, FunctionInfo] = self.discover_functions(
            root_module
        )

    def get_type_str(self, type_hint: Any) -> str:
        """Convert a type hint to a string representation, handling special cases."""
        try:
            if type_hint is None:
                return "None"
            if hasattr(type_hint, "__name__"):
                return type_hint.__name__
            if hasattr(type_hint, "_name"):  # Handle Union types
                return type_hint._name or str(type_hint)

            # Handle special cases
            origin = getattr(type_hint, "__origin__", None)
            if origin is Union:
                args = getattr(type_hint, "__args__", [])
                types = [self.get_type_str(arg) for arg in args]
                return f"Union[{', '.join(types)}]"

            # For other generic types (List, Dict, etc.)
            if origin is not None:
                args = getattr(type_hint, "__args__", [])
                origin_name = getattr(origin, "__name__", str(origin))
                if args:
                    args_str = ", ".join(self.get_type_str(arg) for arg in args)
                    return f"{origin_name}[{args_str}]"
                return origin_name

            # Fallback
            return str(type_hint)
        except Exception as e:
            logger.debug(f"Error converting type hint to string: {str(e)}")
            return "Any"

    def discover_functions(self, package_path: str) -> Dict[str, FunctionInfo]:
        """Discover all functions in the given package path.

        Args:
            package_path: The package to search in.
                Can be either:
                - A dot-separated Python package path (e.g. "backend.services")
                - A relative path starting with "." (e.g. "." for current package)
        """
        logger.info(f"Discovering functions in {package_path}")
        discovered_functions = {}  # Create a local dict to store functions

        def explore_module(module):
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and not name.startswith("_"):
                    try:
                        # Get the absolute file path of the function's source code
                        try:
                            source_file = inspect.getfile(obj)
                            # Check if the function is from our project directory
                            if not source_file.startswith(
                                os.path.dirname(os.path.dirname(__file__))
                            ):
                                continue
                        except (TypeError, ValueError):
                            # If we can't get the source file, skip this function
                            continue

                        # Get function signature and type hints
                        sig = inspect.signature(obj)
                        try:
                            type_hints = get_type_hints(obj)
                        except Exception:
                            # If we can't get type hints, use empty dict
                            type_hints = {}

                        # Extract parameter information
                        params = {}
                        for param_name, param in sig.parameters.items():
                            if param_name == "self":  # Skip self parameter
                                continue
                            param_info = {
                                "required": param.default == param.empty,
                                "default": (
                                    None
                                    if param.default == param.empty
                                    else param.default
                                ),
                                "type": self.get_type_str(
                                    type_hints.get(param_name, Any)
                                ),
                                "description": None,  # Could be extracted from docstring in the future
                            }
                            params[param_name] = param_info

                        # Create function info
                        func_info = FunctionInfo(
                            module_name=module.__name__,
                            function_name=name,
                            full_path=f"{module.__name__}.{name}",
                            doc=inspect.getdoc(obj),
                            is_async=inspect.iscoroutinefunction(obj),
                            parameters=params,
                            return_type=self.get_type_str(
                                type_hints.get("return", Any)
                            ),
                        )
                        logger.debug(f"Discovered function: {func_info.full_path}")
                        discovered_functions[func_info.full_path] = func_info
                    except Exception as e:
                        logger.debug(f"Error processing function {name}: {str(e)}")

        def explore_package(package_name: str):
            try:
                # Handle relative imports
                if package_name.startswith("."):
                    # Get the parent package name from the caller's frame
                    current_frame = inspect.currentframe()
                    if current_frame is not None:
                        caller_frame = current_frame.f_back
                        if caller_frame is not None:
                            caller_frame = caller_frame.f_back
                            if caller_frame is not None:
                                caller_module = inspect.getmodule(caller_frame)
                                if caller_module and caller_module.__package__:
                                    # Convert relative import to absolute
                                    if package_name == ".":
                                        package_name = "backend"  # Always start from the root backend package
                                    else:
                                        package_name = f"backend{package_name}"

                logger.debug(f"Importing package: {package_name}")
                package = importlib.import_module(package_name)
                explore_module(package)

                # Explore all submodules
                if hasattr(package, "__path__"):
                    for _, name, is_pkg in pkgutil.iter_modules(package.__path__):
                        full_name = f"{package_name}.{name}"
                        explore_package(full_name)
            except Exception as e:
                logger.warning(f"Error exploring package {package_name}: {str(e)}")
            finally:
                # Clean up frame references to avoid memory leaks
                if "current_frame" in locals():
                    del current_frame

        explore_package(package_path)
        return discovered_functions

    def get_function_info(self, full_path: str) -> Optional[FunctionInfo]:
        """Get information about a discovered function."""
        return self.discovered_functions.get(full_path)

    def list_functions(self) -> Dict[str, FunctionInfo]:
        return self.discovered_functions

    def create_task_from_function(self, full_path: str) -> Optional[Callable]:
        """Create a task from a discovered function."""
        func_info = self.get_function_info(full_path)
        if not func_info:
            return None

        try:
            module = importlib.import_module(func_info.module_name)
            func = getattr(module, func_info.function_name)

            # Create a wrapper that handles parameter passing
            async def task_wrapper(**parameters):
                try:
                    if func_info.is_async:
                        return await func(**parameters)
                    return func(**parameters)
                except Exception as e:
                    logger.error(f"Error executing task {full_path}: {str(e)}")
                    raise

            # Store the original function info
            task_wrapper.func_info = func_info
            return task_wrapper
        except Exception as e:
            logger.error(f"Error creating task from function {full_path}: {str(e)}")
            return None


def introspect(root_module: str = "backend"):
    return FunctionDiscovery(root_module)
