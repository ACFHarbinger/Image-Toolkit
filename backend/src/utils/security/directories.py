"""
Directory and Zip encryption utilities.

This module provides functions to encrypt and decrypt directories and zip files.

Attributes:
    encrypt_directory: Encrypt all files in a directory recursively.
    decrypt_directory: Decrypt all .enc files in a directory recursively.
    encrypt_zip_directory: Zip a directory and then encrypt the resulting zip file.
    decrypt_zip: Decrypt a zip file and extract its contents.

Example:
    >>> import directories
    >>> directories.encrypt_directory(key, "test")
    >>> directories.decrypt_directory(key, "test")
    >>> directories.encrypt_zip_directory(key, "test")
    >>> directories.decrypt_zip(key, "test")
"""

import os
from typing import List, Optional, Union

from logic.src.utils.io.files import extract_zip, zip_directory

from .data import decrypt_file_data, encrypt_file_data


def encrypt_directory(
    key: bytes, input_dir: Union[str, os.PathLike], output_dir: Optional[Union[str, os.PathLike]] = None
) -> List[bytes]:
    """
    Encrypt all files in a directory recursively.

    Args:
        key (bytes): The encryption key.
        input_dir (Union[str, os.PathLike]): Directory to encrypt.
        output_dir (Union[str, os.PathLike], optional): Output directory. Defaults to input_dir.

    Returns:
        list: List of encrypted data bytes for each file.

    Raises:
        Exception: If directory creation fails.
    """
    if output_dir is None:
        output_dir = input_dir
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        raise Exception("directories to save output files do not exist and could not be created") from e

    # Recursively process all files in the input directory
    encdata_ls = []
    for root, _, files in os.walk(str(input_dir)):
        for file in files:
            input_file = os.path.join(root, file)
            relative_path = os.path.relpath(input_file, str(input_dir))
            output_file = os.path.join(str(output_dir), relative_path + ".enc")

            # Create subdirectories in the output directory if they don't exist
            try:
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
            except OSError as e:
                raise Exception("subdirectories to save output files do not exist and could not be created") from e
            encdata_ls.append(encrypt_file_data(key, input_file, output_file))
    return encdata_ls


def decrypt_directory(
    key: bytes, input_dir: Union[str, os.PathLike], output_dir: Optional[Union[str, os.PathLike]] = None
) -> List[str]:
    """
    Decrypt all .enc files in a directory recursively.

    Args:
        key (bytes): The encryption key.
        input_dir (Union[str, os.PathLike]): Directory to decrypt.
        output_dir (Union[str, os.PathLike], optional): Output directory. Defaults to input_dir.

    Returns:
        list: List of decrypted string data for each file.

    Raises:
        Exception: If directory creation fails.
    """
    if output_dir is None:
        output_dir = input_dir
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        raise Exception("directories to save output files do not exist and could not be created") from e

    # Recursively process all files in the input directory
    decdata_ls = []
    for root, _, files in os.walk(str(input_dir)):
        for file in files:
            input_file = os.path.join(root, file)
            file_path, file_ext = os.path.splitext(input_file)
            if file_ext == ".enc":
                relative_path = os.path.relpath(file_path, str(input_dir))
                output_file = os.path.join(str(output_dir), relative_path)

                # Create subdirectories in the output directory if they don't exist
                try:
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                except OSError as e:
                    raise Exception("subdirectories to save output files do not exist and could not be created") from e
                decdata_ls.append(decrypt_file_data(key, input_file, output_file))
    return decdata_ls


def encrypt_zip_directory(
    key: bytes, input_dir: Union[str, os.PathLike], output_enczip: Optional[Union[str, os.PathLike]] = None
) -> bytes:
    """
    Zip a directory and then encrypt the resulting zip file.

    Args:
        key (bytes): The encryption key.
        input_dir (Union[str, os.PathLike]): Directory to zip and encrypt.
        output_enczip (Union[str, os.PathLike], optional): Output path for the encrypted zip.

    Returns:
        bytes: The encrypted zip data.
    """
    # str(input_dir) to satisfy os.path functions if it's PathLike
    input_dir_str = str(input_dir)
    if output_enczip is None:
        norm_path = os.path.normpath(input_dir_str)
        output_enczip = os.path.join(os.path.dirname(norm_path), f"{os.path.basename(norm_path)}.zip")

    output_enczip_str = str(output_enczip)
    tmp_zip = "{}.tmp.zip".format(output_enczip_str)
    zip_directory(input_dir_str, tmp_zip)
    encrypted_data = encrypt_file_data(key, tmp_zip, output_enczip_str)
    os.remove(tmp_zip)
    return encrypted_data


def decrypt_zip(
    key: bytes, input_enczip: Union[str, os.PathLike], output_dir: Optional[Union[str, os.PathLike]] = None
) -> str:
    """
    Decrypt a zip file and extract its contents.

    Args:
        key (bytes): The encryption key.
        input_enczip (Union[str, os.PathLike]): Path to the encrypted zip file.
        output_dir (Union[str, os.PathLike], optional): Directory to extract to.

    Returns:
        str: The decrypted data (raw string content of the zip file).
    """

    input_enczip_str = str(input_enczip)
    if output_dir is None:
        norm_path = os.path.normpath(input_enczip_str)
        output_dir, _ = os.path.splitext(norm_path)

    output_dir_str = str(output_dir)
    tmp_zip = input_enczip_str + ".tmp.zip"
    decrypted_data = decrypt_file_data(key, input_enczip_str, tmp_zip)
    extract_zip(tmp_zip, output_dir_str)
    os.remove(tmp_zip)
    return decrypted_data
