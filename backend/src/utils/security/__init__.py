"""
Crypto package.

Attributes:
    generate_key: Generate a key from a password using PBKDF2HMAC.
    load_key: Loads a symmetric key from environment or file parameters.
    encode_data: Encodes various data types into bytes for encryption.
    encrypt_file_data: Encrypt a file or data object using Fernet symmetric encryption.
    decrypt_file_data: Decrypt a file or data bytes using Fernet symmetric encryption.
    encrypt_directory: Encrypt all files in a directory recursively.
    decrypt_directory: Decrypt all .enc files in a directory recursively.
    encrypt_zip_directory: Zip a directory and then encrypt the resulting zip file.
    decrypt_zip: Decrypt a zip file and extract its contents.

Example:
    >>> import generate_key
    >>> import load_key
    >>> import encode_data
    >>> import encrypt_file_data
    >>> import decrypt_file_data
    >>> import encrypt_directory
    >>> import decrypt_directory
    >>> import encrypt_zip_directory
    >>> import decrypt_zip
"""

from .data import decrypt_file_data, encode_data, encrypt_file_data
from .directories import (
    decrypt_directory,
    decrypt_zip,
    encrypt_directory,
    encrypt_zip_directory,
)
from .keys import generate_key, load_key

__all__ = [
    "generate_key",
    "load_key",
    "encode_data",
    "encrypt_file_data",
    "decrypt_file_data",
    "encrypt_directory",
    "decrypt_directory",
    "encrypt_zip_directory",
    "decrypt_zip",
    "decrypt_zip",
]
