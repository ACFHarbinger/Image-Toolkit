# Cryptography Module Instructions (`cryptography/`)

## Overview
This module handles **high-security credential management** and **encryption** primitives. It is written in **Kotlin** to leverage strong typing and JVM security features, often compiled into a JAR that is invoked by the Python backend via `vault_manager.py` or used directly by the Android app.

## Structure
* **`src/main/kotlin/`**: Source code location.
* **`build.gradle.kts`**: Build configuration (Gradle Kotlin DSL).

## Capabilities
*   **Vault Management**: Encrypting/Decrypting `.vault` files containing API keys (Google Drive, Danbooru, etc.).
*   **Key Derivation**: Secure handling of master passwords.

## Coding Standards
1.  **Security First**:
    *   **Zero Trace**: Clear sensitive data from memory (ByteArrays) as soon as possible.
    *   **Strong Algo**: Use AES-256-GCM or equivalent authenticated encryption. Do not roll your own crypto.
2.  **Kotlin**:
    *   Use idiomatic Kotlin (data classes, extension functions).
    *   Ensure strict null safety.
3.  **Testing**:
    *   `./gradlew test` must pass.
    *   Unit tests should verify encryption round-trip (Encrypt -> Decrypt = Original).

## Build
*   **Command**: `./gradlew build`
*   **Output**: Typically a shadowed JAR in `build/libs/` used by other modules.
