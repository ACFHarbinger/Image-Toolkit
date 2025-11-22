plugins {
    `java-library`
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.shadow)          // ← now uses 8.3.1
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(libs.versions.java.get()))
    }
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
}

tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
    kotlinOptions {
        jvmTarget = "21"
    }
}

dependencies {
    api(libs.bc.provider)
    api(libs.bc.pki)
    testImplementation(libs.bundles.test.libraries)
}

tasks.shadowJar {
    archiveClassifier.set("")           // makes this the main JAR
    manifest {
        attributes["Main-Class"] = "com.personal.image_toolkit.YourMainKt" // set later
    }
    exclude("META-INF/*.SF", "META-INF/*.DSA", "META-INF/*.RSA")
    mergeServiceFiles()
    relocate("org.bouncycastle", "com.personal.image_toolkit.shaded.org.bouncycastle")
}

tasks.assemble { dependsOn(tasks.shadowJar) }