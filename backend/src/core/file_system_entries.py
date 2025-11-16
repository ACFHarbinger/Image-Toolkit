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
        """
        Check if parent_path contains child_path.
        Returns True if child_path is within parent_path or equal to it.
        """
        try:
            parent = Path(parent_path).resolve()
            child = Path(child_path).resolve()
            child.relative_to(parent)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def prefix_create_directory(arg_id=0, kwarg_name='', is_filepath=False):
        """
        Decorator factory that returns a function to create a directory 
        based on a positional argument (arg_id) or keyword argument (kwarg_name).
        """
        def inner(*args, **kwargs):
            path = kwargs.get(kwarg_name, None)
            
            if path is None and len(args) > arg_id:
                path = args[arg_id]
            
            if path:
                directory = os.path.dirname(path) if is_filepath else path
                if not directory:
                    return True
                
                if os.path.exists(directory): 
                    return True
                try:
                    os.makedirs(directory, exist_ok=True)
                    print(f"Created directory: '{directory}'.")
                    return True
                except Exception as e:
                    print(f"ERROR: could not create directory '{directory}' with exception {type(e)}.")
                    raise
            return False
        return inner

    @staticmethod
    def ensure_absolute_paths(prefix_func=None, suffix_func=None):
        """
        Decorator factory to ensure paths are made absolute relative to 
        the system path.
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if prefix_func is not None: prefix_func(*args, **kwargs)

                normalized_args = list(args)
                
                # Normalize positional arguments
                for id, arg in enumerate(normalized_args):
                    if isinstance(arg, str) and not os.path.isabs(arg):
                        if os.path.exists(arg):
                            normalized_args[id] = os.path.abspath(arg)
                        
                # Normalize keyword arguments
                for key, value in kwargs.items():
                    if isinstance(value, str) and not os.path.isabs(value) and os.path.exists(value):
                        kwargs[key] = os.path.abspath(value)

                result = func(*tuple(normalized_args), **kwargs)

                if suffix_func is not None: suffix_func(*normalized_args, **kwargs)
                
                return result
            return wrapper
        return decorator

    # --- Core File System Methods ---

    @staticmethod
    @ensure_absolute_paths()
    def get_files_by_extension(directory, extension, recursive=False):
        """
        Get all files with specific extension in directory.
        
        Args:
            directory: Path to directory
            extension: File extension (e.g., 'txt', '.jpeg')
            recursive: Whether to search subdirectories
        
        Returns:
            List of absolute file paths (strings).
        """
        path = Path(directory)
        
        if not extension.startswith('.'):
            extension = '.' + extension
        
        if recursive:
            pattern = f'**/*{extension}'
        else:
            pattern = f'*{extension}'
        
        files = [str(f.resolve()) for f in path.glob(pattern) if f.is_file()]
        return files


class FileDeleter:
    """
    A class dedicated to safely deleting files and directories, 
    leveraging FSETool for path resolution.
    """

    @staticmethod
    @FSETool.ensure_absolute_paths()
    def delete_path(path_to_delete: str) -> bool:
        """Deletes a file or directory recursively."""
        if not os.path.exists(path_to_delete):
            print(f"WARNING: specified path does not exist - did not delete '{path_to_delete}'.")
            return False
    
        if os.path.isdir(path_to_delete):
            try:
                shutil.rmtree(path_to_delete)
                print(f"Deleted directory: '{path_to_delete}'.")
            except OSError as e:
                print(f"ERROR: Could not delete directory {path_to_delete}. Reason: {e}")
                return False
        elif os.path.isfile(path_to_delete):
            try:
                os.remove(path_to_delete)
                print(f"Deleted file: '{path_to_delete}'.")
            except OSError as e:
                print(f"ERROR: Could not delete file {path_to_delete}. Reason: {e}")
                return False
        return True

    @staticmethod
    @FSETool.ensure_absolute_paths()
    def delete_files_by_extensions(directory: str, extensions: list[str]) -> int:
        """
        Recursively delete files with extension(s) in directory and all subdirectories.
        """
        path = Path(directory)
        deleted_count = 0
        
        for extension in extensions:
            if not extension.startswith('.'):
                extension = '.' + extension
            
            for file_path in path.rglob(f'*{extension}'):
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        print(f"Deleted: {file_path}")
                        deleted_count += 1
                    except OSError as e:
                        print(f"ERROR: Could not delete file {file_path}. Reason: {e}")
        
        print(f"Deleted {deleted_count} files recursively.")
        return deleted_count
