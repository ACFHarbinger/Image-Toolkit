/*
 * This file configures the root project and defines all sub-modules (including Android).
 */

pluginManagement {
    // CRITICAL FIX: Tell the plugin resolution mechanism where to find AGP (com.android.*)
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    // Apply the foojay-resolver plugin to allow automatic download of JDKs
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "image-toolkit"

// Project submodules
include("cryptography")

// Include the main App project as a submodule.
// The path must be relative to this root settings file.
// We are mapping the "app" folder to the project name ":app".
include(":app")
project(":app").projectDir = file("app")

// Include any sub-modules within the Android project, if they exist.
// Example: If your android code is in app/android
include(":app:android")
project(":app:android").projectDir = file("app/android")