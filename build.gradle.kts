plugins {
    // Apply common plugins but don't apply them to the root project itself
    // Shadow plugin version is managed here.
    id("com.github.johnrengelman.shadow") version "8.1.1" apply false
    
    // Enable the Version Catalog feature
    id("org.gradle.version-catalog") version "8.5" // Use a stable version of the plugin
}

allprojects {
    group = "com.personal.image_toolkit"
    version = "1.0.0-SNAPSHOT"

    repositories {
        google()
        mavenCentral()
    }
}

subprojects {
    apply(plugin = "java")
    apply(plugin = "java-library")

    // Java Configuration using the version from libs.versions.toml
    java {
        toolchain {
            languageVersion.set(JavaLanguageVersion.of(libs.versions.java.get()))
        }
    }

    // UTF-8 encoding
    tasks.withType<JavaCompile> {
        options.encoding = "UTF-8"
    }

    // JUnit 5 Configuration
    tasks.withType<Test> {
        useJUnitPlatform()
    }
}