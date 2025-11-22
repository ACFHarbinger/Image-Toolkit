plugins {
    `java-library`
    id("com.github.johnrengelman.shadow")
}

dependencies {
    // Bouncy Castle Dependencies using version catalog aliases
    implementation(libs.bc.provider)
    implementation(libs.bc.pki)

    // Test Dependencies using the bundle alias
    testImplementation(libs.bundles.test.libraries)

    // Note: If you need to scope test dependencies individually, you can do this:
    // testImplementation(libs.test.junit.api)
    // testRuntimeOnly(libs.test.junit.engine)
}

tasks.shadowJar {
    archiveClassifier.set("uber")

    // Filters: Matches the <excludes> in the POM
    exclude("META-INF/*.SF")
    exclude("META-INF/*.DSA")
    exclude("META-INF/*.RSA")

    // Transformers
    mergeServiceFiles()

    // Relocations
    relocate("org.bouncycastle", "com.personal.image_toolkit.shaded.org.bouncycastle")
}

tasks.assemble {
    dependsOn(tasks.shadowJar)
}