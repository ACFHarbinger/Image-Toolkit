import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.gradle.jvm.toolchain.JavaLanguageVersion

plugins {
    `java-library`
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.shadow)
}

java {
    toolchain {
        // Changed libs.versions.java to libs.versions.jvmVersion to fix conflict
        languageVersion.set(JavaLanguageVersion.of(libs.versions.jvmVersion.get()))
    }
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
}

// FIXED: Migrated from deprecated kotlinOptions to compilerOptions
tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_21)
    }
}

dependencies {
    // Now resolves correctly because 'bc-provider' and 'bc-pki' are in [libraries]
    api(libs.bc.provider)
    api(libs.bc.pki)
    
    // CHANGED: Use the new 'jvm.test.libraries' bundle to avoid pulling in Android dependencies (AARs)
    testImplementation(libs.bundles.jvm.test.libraries)
}

tasks.shadowJar {
    archiveClassifier.set("") 
    manifest {
        attributes["Main-Class"] = "com.personal.image_toolkit.cryptography.MainKt"
    }
    exclude("META-INF/*.SF", "META-INF/*.DSA", "META-INF/*.RSA")
    mergeServiceFiles()
    relocate("org.bouncycastle", "com.personal.image_toolkit.shaded.org.bouncycastle")
}

tasks.assemble { dependsOn(tasks.shadowJar) }