import org.gradle.api.JavaVersion
import org.gradle.api.plugins.JavaPluginExtension
import org.gradle.api.tasks.testing.Test
import org.gradle.api.tasks.compile.JavaCompile
import org.gradle.jvm.toolchain.JavaLanguageVersion
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

plugins {
    // 1. Plugins managed here for application in subprojects
    
    id("com.github.johnrengelman.shadow") version "8.1.1" apply false

    alias(libs.plugins.android.application) apply false 
    alias(libs.plugins.android.library) apply false
    
    id("org.gradle.version-catalog") 
    
    alias(libs.plugins.kotlin.jvm) apply false 
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
    // 2. Shared configuration for the Cryptography module
    // We target only ":cryptography" to avoid applying Java/Kotlin library plugins 
    // to the Android App, which manages its own plugins.
    if (path == ":cryptography") {
        
        // Apply plugins needed for the Java Library
        apply(plugin = "java-library") 
        apply(plugin = "org.jetbrains.kotlin.jvm")

        // Configure the Java Toolchain
        configure<JavaPluginExtension> {
            toolchain {
                languageVersion.set(JavaLanguageVersion.of(libs.versions.java.get().toInt()))
            }
        }
        
        // FIX: The 'dependencies' block is removed from here.
        // The dependencies are already defined in 'cryptography/build.gradle.kts',
        // which is the correct and most stable place for them.

        // Configure Task Defaults
        tasks.withType<JavaCompile> {
            options.encoding = "UTF-8"
        }
        
        tasks.withType<KotlinCompile> {
            kotlinOptions {
                jvmTarget = JavaVersion.VERSION_21.toString()
            }
        }

        tasks.withType<Test> {
            useJUnitPlatform()
        }
    }
}