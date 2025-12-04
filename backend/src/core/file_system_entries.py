import os
import shutil
import functools

from pathlib import Path


class FSETool:
    """
    A comprehensive tool for managing file system entries, including path
    resolution, directory creation, file searching, and path manipulation.
    """

    # --- Utility Methods ---
    @staticmethod
    def path_contains(parent_path, child_path):
        try:
            parent = Path(parent_path).resolve()
            child = Path(child_path).resolve()
            child.relative_to(parent)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def prefix_create_directory(arg_id=0, kwarg_name="", is_filepath=False):
        def inner(*args, **kwargs):
            path = kwargs.get(kwarg_name, None)
            if path is None and len(args) > arg_id:
                path = args[arg_id]
            if path:
                directory = os.path.dirname(path) if is_filepath else path
                if not directory or os.path.exists(directory):
                    return True
                try:
                    os.makedirs(directory, exist_ok=True)
                    print(f"Created directory: '{directory}'.")
                    return True
                except Exception as e:
                    print(f"ERROR: could not create directory '{directory}': {e}")
                    raise
            return False

        return inner

    @staticmethod
    def ensure_absolute_paths(prefix_func=None, suffix_func=None):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if prefix_func:
                    prefix_func(*args, **kwargs)
                normalized_args = list(args)
                for id, arg in enumerate(normalized_args):
                    if (
                        isinstance(arg, str)
                        and not os.path.isabs(arg)
                        and os.path.exists(arg)
                    ):
                        normalized_args[id] = os.path.abspath(arg)
                for key, value in kwargs.items():
                    if (
                        isinstance(value, str)
                        and not os.path.isabs(value)
                        and os.path.exists(value)
                    ):
                        kwargs[key] = os.path.abspath(value)
                result = func(*tuple(normalized_args), **kwargs)
                if suffix_func:
                    suffix_func(*normalized_args, **kwargs)
                return result

            return wrapper

        return decorator

    @staticmethod
    @ensure_absolute_paths()
    def get_files_by_extension(directory, extension, recursive=False):
        path = Path(directory)
        if not extension.startswith("."):
            extension = "." + extension
        pattern = f"**/*{extension}" if recursive else f"*{extension}"
        return [str(f.resolve()) for f in path.glob(pattern) if f.is_file()]


class FileDeleter:
    @staticmethod
    @FSETool.ensure_absolute_paths()
    def delete_path(path_to_delete: str) -> bool:
        if not os.path.exists(path_to_delete):
            return False
        try:
            if os.path.isdir(path_to_delete):
                shutil.rmtree(path_to_delete)
            elif os.path.isfile(path_to_delete):
                os.remove(path_to_delete)
            return True
        except OSError as e:
            print(f"Delete Error: {e}")
            return False

    @staticmethod
    @FSETool.ensure_absolute_paths()
    def delete_files_by_extensions(directory: str, extensions: list[str]) -> int:
        path = Path(directory)
        deleted = 0
        for ext in extensions:
            if not ext.startswith("."):
                ext = "." + ext
            for f in path.rglob(f"*{ext}"):
                if f.is_file():
                    try:
                        f.unlink()
                        deleted += 1
                    except OSError:
                        pass
        return deleted
