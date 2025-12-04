import org.gradle.jvm.toolchain.JavaLanguageVersion

// This file is the root build file for all projects (including sub-modules).
plugins {
    // These plugins define versions and are available to sub-projects via 'alias(libs.plugins.x)'

    // Android Gradle Plugin (AGP) - Required for Android Application builds
    alias(libs.plugins.android.application) apply false
    // Android Gradle Plugin (AGP) - Required for Android Library builds (if you had a library module)
    alias(libs.plugins.android.library) apply false

    // Kotlin Multiplatform/Android/JVM Plugin - Essential for all Kotlin code
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.jvm) apply false

    // Other utility plugins
    alias(libs.plugins.shadow) apply false
}

allprojects {
    group = "com.personal.image_toolkit"
    version = "1.0.0-SNAPSHOT"

    // Defines Maven repositories for dependencies (same as in settings.gradle.kts)
    repositories {
        google()
        mavenCentral()
    }
}