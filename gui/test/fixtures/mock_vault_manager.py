"""Shared vault-manager test double + recovery-file cleanup.

Extracted from ``gui/test/windows/test_main_window.py`` -- several other
test modules previously imported these via ``from .test_main_window import
MockVaultManager, cleanup_recovery_files``, a test file importing from
another test file. This is the canonical location; ``test_main_window.py``
itself now imports from here too.
"""

from __future__ import annotations

import contextlib
import json
import os


class MockVaultManager:
    def __init__(self, credentials):
        self.creds = credentials
        self.saved_data = None
        self.account_name = "test_user"
        self.secret_key = b"dummy_key_32_bytes_long_123456789"

        class MockSecureJsonVault:
            _vaults = {}

            def __init__(self, key, path):
                self.key = key
                self.path = path

            def saveData(self, data):
                MockSecureJsonVault._vaults[self.path] = data
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "w") as f:
                    f.write(data)

            def loadData(self):
                if os.path.exists(self.path):
                    with open(self.path, "r") as f:
                        return f.read()
                return MockSecureJsonVault._vaults.get(self.path, "{}")

        self.SecureJsonVault = MockSecureJsonVault

    def load_account_credentials(self):
        return self.creds

    def save_data(self, json_string):
        self.saved_data = json.loads(json_string)
        self.creds = self.saved_data

    def shutdown(self):
        pass


def cleanup_recovery_files():
    recovery_dir = os.path.expanduser("~/.image-toolkit/recovery")
    enc_file = os.path.join(recovery_dir, "recovery_test_user.enc")
    if os.path.exists(enc_file):
        with contextlib.suppress(Exception):
            os.remove(enc_file)


__all__ = ["MockVaultManager", "cleanup_recovery_files"]
