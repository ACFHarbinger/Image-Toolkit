/*
 * This file configures the root project and defines all sub-modules (including Android).
 */

plugins {
    // Apply the foojay-resolver plugin to allow automatic download of JDKs
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "image-toolkit-root"

// Include the main Android project as a submodule.
// The path must be relative to this root settings file.
// We are mapping the "android" folder to the project name ":android".
include(":android")
project(":android").projectDir = file("android")

// Include any sub-modules within the Android project, if they exist.
// Example: If your app code is in android/app
include(":android:app")
project(":android:app").projectDir = file("android/app")