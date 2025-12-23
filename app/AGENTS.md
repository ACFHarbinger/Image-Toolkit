# Mobile Module Instructions (`app/`)

## Overview
Native mobile applications for Android and iOS that serve as remote viewers and managers for the Image-Toolkit ecosystem.

## Structure
* **`android/`** (Kotlin):
    *   Standard Android Studio project structure.
    *   Uses Jetpack Compose (if applicable) or standard XML Views.
* **`ios/`** (Swift):
    *   Standard Xcode project structure (`image_toolkit` package).
    *   SwiftUI driven.

## Commands
| Context | Command |
| :--- | :--- |
| **Android Build** | `./gradlew assembleDebug` (in `android/`) |
| **Test** | `./gradlew test` |

## Coding Standards
1.  **Concurrency**:
    *   **Android**: Use Kotlin Coroutines for all network/DB I/O.
    *   **iOS**: Use Swift Concurrency (`async`/`await`).
    *   Never block the main UI thread.
2.  **Architecture**:
    *   Follow MVVM (Model-View-ViewModel) patterns where possible.
3.  **Security**:
    *   Use platform-native secure storage for credentials (EncryptedSharedPreferences / Keychain).
