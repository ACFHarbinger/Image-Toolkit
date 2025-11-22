plugins {
    // Apply common plugins
    id("java") apply false
    id("java-library") apply false
    alias(libs.plugins.kotlin.jvm) apply false
    
    // Shadow plugin for the cryptography module
    id("com.github.johnrengelman.shadow") version "8.1.1" apply false

    // Android Gradle Plugin (Apply to root, manage for subprojects)
    alias(libs.plugins.android.application) apply false 
    alias(libs.plugins.android.library) apply false
    
    // Enable the Version Catalog feature
    id("org.gradle.version-catalog") version "8.5"
}

allprojects {
    group = "com.personal.image_toolkit"
    version = "1.0.0-SNAPSHOT"

    repositories {
        google() // Essential for Android dependencies (androidx, etc.)
        mavenCentral()
    }
}

subprojects {
    // Shared configurations for all subprojects
    
    // Java 21 Configuration (Used by 'cryptography' module)
    java {
        toolchain {
            languageVersion.set(JavaLanguageVersion.of(21))
        }
    }
    
    // Kotlin JVM (Used by both Java and Android modules)
    apply(plugin = "org.jetbrains.kotlin.jvm")

    // UTF-8 encoding
    tasks.withType<JavaCompile> {
        options.encoding = "UTF-8"
    }

    // Shared Test Configuration
    tasks.withType<Test> {
        useJUnitPlatform()
    }
    
    // Define shared dependencies/bom for use across JVM and Android tests
    dependencies {
        // Use Kotlin standard library
        implementation(libs.kotlin.stdlib)
        
        // Inherit the test bundle/libraries for JVM modules or Android unit tests
        testImplementation(libs.bundles.test.libraries)
    }
}