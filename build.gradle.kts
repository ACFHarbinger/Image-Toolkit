import org.gradle.jvm.toolchain.JavaLanguageVersion

plugins {
    alias(libs.plugins.shadow) apply false
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
}

allprojects {
    group = "com.personal.image_toolkit"
    version = "1.0.0-SNAPSHOT"

    repositories {
        google()
        mavenCentral()
    }
}