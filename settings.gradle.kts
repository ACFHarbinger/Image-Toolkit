/*
 * This file configures the root project and defines all sub-modules.
 */

pluginManagement {
    // CRITICAL: Tells Gradle where to look for plugins (like Android Gradle Plugin)
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

// Core Java/Kotlin module
include("cryptography")

// Android Application Module
include(":app")
// Maps the ":app" project to the actual Android source directory: "app/android"
project(":app").projectDir = file("app/android")