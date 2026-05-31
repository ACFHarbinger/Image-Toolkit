"""
Data encryption/decryption utilities.

This module provides functions to encode, encrypt, and decrypt data.

Attributes:
    encode_data: Encodes various data types into bytes for encryption.
    encrypt_file_data: Encrypt a file or data object using Fernet symmetric encryption.
    decrypt_file_data: Decrypt a file or data bytes using Fernet symmetric encryption.

Example:
    >>> import data
    >>> data.encode_data("test")
    >>> data.encrypt_file_data(key, "test")
    >>> data.decrypt_file_data(key, "test")
"""

import os
import pickle
import struct
from pathlib import Path
from typing import Any, Optional, Union

from cryptography.fernet import Fernet


def encode_data(data: Any) -> bytes:
    """
    Encodes various data types into bytes for encryption.

    Args:
        data (Any): Data to encode (str, int, float, list, dict, etc.).

    Returns:
        bytes: Encoded byte representation.
    """
    if isinstance(data, str):
        return data.encode("utf-8")
    elif isinstance(data, int):
        return data.to_bytes((data.bit_length() + 7) // 8, byteorder="big")
    elif isinstance(data, float):
        return struct.pack("!f", data)
    else:  # elif isinstance(data, list) or isinstance(data, ITraversable):
        return pickle.dumps(data)


def encrypt_file_data(
    key: bytes, input: Union[str, os.PathLike, Any], output_file: Optional[Union[str, os.PathLike]] = None
) -> bytes:
    """
    Encrypt a file or data object using Fernet symmetric encryption.

    Args:
        key (bytes): The encryption key.
        input (Union[str, os.PathLike, Any]): Path to file OR data object to encrypt.
        output_file (Union[str, os.PathLike], optional): Path to save encrypted data.

    Returns:
        bytes: The encrypted data.
    """
    fernet = Fernet(key)
    # Check if input looks like a path and exists
    if isinstance(input, (str, Path)) and os.path.isfile(input):
        with open(input, "rb") as f:
            original_data = f.read()
    else:
        original_data = encode_data(input)

    encrypted_data = fernet.encrypt(original_data)
    if output_file:
        with open(output_file, "wb") as f:
            f.write(encrypted_data)
    return encrypted_data


def decrypt_file_data(
    key: bytes, input: Union[str, os.PathLike, Any], output_file: Optional[Union[str, os.PathLike]] = None
) -> str:
    """
    Decrypt a file or data bytes using Fernet symmetric encryption.

    Args:
        key (bytes): The encryption key.
        input (Union[str, os.PathLike, Any]): Path to encrypted file OR encrypted bytes.
        output_file (Union[str, os.PathLike], optional): Path to save decrypted content.

    Returns:
        str: The decrypted data (decoded as utf-8 string).
    """
    fernet = Fernet(key)
    if isinstance(input, (str, Path)) and os.path.isfile(input):
        with open(input, "rb") as f:
            encrypted_data = f.read()
    else:
        # Cast input to bytes if it's not a file path
        if not isinstance(input, bytes):
            raise TypeError(f"Expected file path or bytes for decryption, got {type(input)}")
        encrypted_data = input

    decrypted_data = fernet.decrypt(encrypted_data).decode("utf-8")
    if output_file:
        with open(output_file, "w") as f:
            f.write(decrypted_data)
    return decrypted_data
