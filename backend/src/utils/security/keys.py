"""
Key generation and loading utilities.

This module provides functions to generate and load encryption keys.

Attributes:
    generate_key: Generate a key from a password using PBKDF2HMAC.
    load_key: Loads a symmetric key from environment or file parameters.

Example:
    >>> import keys
    >>> keys.generate_key()
    >>> keys.load_key()
"""

import base64
import os
import pickle
from pathlib import Path
from typing import Optional, Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import dotenv_values, load_dotenv, set_key

from logic.src.constants import ROOT_DIR


def _set_param(config, param_name, param_value=None):
    """set param.

    Args:
    config (Any): Description of config.
    param_name (Any): Description of param_name.
    param_value (Any): Description of param_value.

    Returns:
        Any: Description of return value.
    """
    if param_value is None:
        param_value = config.get(param_name.upper())
    if not param_value:
        raise ValueError(f"{param_name} not found in .env file.")
    return param_value


def generate_key(
    salt_size: int = 16,
    key_length: int = 32,
    hash_iterations: int = 100_000,
    symkey_name: Optional[str] = None,
    env_filename: str = ".env",
) -> Tuple[bytes, bytes]:
    """
    Generate a key from a password using PBKDF2HMAC.

    Args:
        salt_size (int, optional): Size of the random salt. Defaults to 16.
        key_length (int, optional): Length of derived key. Defaults to 32.
        hash_iterations (int, optional): Number of hash iterations. Defaults to 100,000.
        symkey_name (str, optional): Name to save key parameters to file (assets/keys/).
        env_filename (str, optional): Environment file to read/write config. Defaults to ".env".

    Returns:
        tuple: (key, salt) bytes.

    Raises:
        ValueError: If configuration values cannot be found or parsed.
        Exception: If directory creation fails.
    """
    env_path = Path(os.path.join(ROOT_DIR, "env", env_filename))
    print(f"Filename: {env_path}")
    config = dotenv_values(env_path)
    salt_size = int(_set_param(config, "SALT_SIZE", salt_size))
    salt = os.urandom(salt_size)
    key_length = int(_set_param(config, "KEY_LENGTH", key_length))
    hash_iterations = int(_set_param(config, "HASH_ITERATIONS", hash_iterations))
    password = _set_param(config, "KEY_PASSWORD")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=key_length,
        salt=salt,
        iterations=hash_iterations,
        backend=default_backend(),
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    salt_str = base64.urlsafe_b64encode(salt).decode("utf-8")
    set_key(env_path, "SALT_STRING", salt_str)
    set_key(env_path, "KEY_LENGTH", str(key_length))
    set_key(env_path, "HASH_ITERATIONS", str(hash_iterations))
    if symkey_name:
        dir_path = os.path.join(ROOT_DIR, "assets", "keys")
        try:
            os.makedirs(dir_path, exist_ok=True)
        except OSError as e:
            raise Exception("directories to save output files do not exist and could not be created") from e

        with open(os.path.join(dir_path, f"{symkey_name}.salt"), "wb") as salt_file:
            salt_file.write(salt)

        kh_params = (key_length, hash_iterations)
        with open(os.path.join(dir_path, f"{symkey_name}.pkl"), "wb") as khp_file:
            pickle.dump(kh_params, khp_file, protocol=pickle.HIGHEST_PROTOCOL)
    return (key, salt)


def load_key(symkey_name: Optional[str] = None, env_filename: str = ".env") -> bytes:
    """
    Loads a symmetric key from environment or file parameters.

    Args:
        symkey_name (str, optional): Name of the key to load parameters from.
        env_filename (str, optional): Environment file name. Defaults to ".env".

    Returns:
        bytes: The derived encryption key.

    Raises:
        ValueError: If password is not found.
    """
    env_path = Path(os.path.join(ROOT_DIR, "env", env_filename))
    load_dotenv(dotenv_path=env_path)
    password = os.getenv("KEY_PASSWORD")
    if not password:
        raise ValueError("Password not found in .env file.")

    if symkey_name:
        print(f"Loading salt from {symkey_name}.salt and key params from {symkey_name}.pkl")
        input_path = os.path.join(ROOT_DIR, "assets", "keys", symkey_name)
        with open(f"{input_path}.salt", "rb") as salt_file:
            salt = salt_file.read()

        with open(f"{input_path}.pkl", "rb") as khp_file:
            key_length, hash_iterations = pickle.load(khp_file)
    else:
        print(f"Loading salt and key params from environment variables in {env_filename}")
        salt_str = os.getenv("SALT_STRING")
        if not salt_str:
            raise ValueError("SALT_STRING not found in environment")
        salt = base64.urlsafe_b64decode(salt_str.encode("utf-8"))

        kl_str = os.getenv("KEY_LENGTH")
        hi_str = os.getenv("HASH_ITERATIONS")
        if not kl_str or not hi_str:
            raise ValueError("KEY_LENGTH or HASH_ITERATIONS not found in environment")

        key_length = int(kl_str)
        hash_iterations = int(hi_str)

    # Derive the key using the password and salt
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=key_length,
        salt=salt,
        iterations=hash_iterations,
        backend=default_backend(),
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key
