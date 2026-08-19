# Native cryptography library (C/OpenSSL)

Replaces the retired embedded-JVM (Kotlin/Gradle/jpype) cryptography module
(issue #435). File formats are byte-identical to what the JVM wrote, so
existing account keystores/vaults migrate with zero changes:

- **Keystore**: PKCS#12 (`my_keystore-*.p12`). AES secret keys live in a
  `secretBag` whose value is a PKCS#8 EncryptedPrivateKeyInfo (PBES2,
  PBKDF2-HMAC-SHA256, 10000 iterations, AES-256-CBC) — the exact layout
  SunJCE's "PKCS12" KeyStore writes. Both this layout and OpenSSL's own
  shrouded-key layout are read; the writer emits the Java layout.
- **Vault**: `[int32 BE iv_len][12-byte IV][AES-256-GCM ciphertext + 16-byte
  tag]`.

## Build

```sh
just build-crypto        # or:
cc -O2 -fPIC -shared -Wall -o build/crypto/libitk_crypto.so \
   base/src/secret/itk_crypto.c -lcrypto
```

Not part of the `base` pybind11 extension module (`base/CMakeLists.txt`) —
this is a separate, plain-C shared library loaded via `ctypes`, not pybind.
It lives under `base/` because that's where all the project's C++ (and C)
source lives, but it builds and ships independently.

## C API

| Function | Purpose |
| --- | --- |
| `itk_keystore_ensure(path, alias, pass)` | Load-or-create (matches Kotlin `KeyInitializer.initializeKeystore`) |
| `itk_keystore_has_alias(path, alias, pass)` | 1 found / 0 not / -1 hard error |
| `itk_keystore_password_valid(path, pass)` | MAC-verify store password (0 ok / -1 wrong) |
| `itk_keystore_get_key(path, alias, pass, &out, &len)` | Raw AES key bytes (16/24/32) |
| `itk_vault_encrypt(key, len, path, plain, plen)` | Write encrypted vault |
| `itk_vault_decrypt(key, len, path, &out, &len)` | Read + GCM-auth-verify vault |
| `itk_free(ptr)` / `itk_last_error()` | Free output / last error (thread-local) |

Python consumption: `backend/src/core/vault_manager.py` (`_CryptoAPI` ctypes
wrapper). Format compatibility is pinned by fixtures the JVM module generated
before removal: `backend/test/data/crypto_fixture/java_generated.p12/.vault/
_key.bin` (password `fixture-pass`, alias `fixture-alias`).