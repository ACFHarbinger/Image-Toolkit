plugins {
    // Apply common plugins but don't apply them to the root project itself
    // unless strictly necessary. We apply 'java' via subprojects.
    // Shadow plugin version is managed here.
    id("com.github.johnrengelman.shadow") version "8.1.1" apply false
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

    // Java 21 Configuration
    java {
        toolchain {
            languageVersion.set(JavaLanguageVersion.of(21))
        }
    }

    // UTF-8 encoding (Standard in Gradle, but explicit to match POM)
    tasks.withType<JavaCompile> {
        options.encoding = "UTF-8"
    }

    // JUnit 5 Configuration
    tasks.withType<Test> {
        useJUnitPlatform()
    }

    // Define versions from parent_pom.xml properties for subprojects to use
    extra.apply {
        set("bouncycastleVersion", "1.82")
        set("junitVersion", "5.10.5")
        set("assertjVersion", "3.25.3")
        set("mockitoVersion", "5.11.0")
    }
}