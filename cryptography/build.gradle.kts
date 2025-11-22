plugins {
    `java-library`
    id("com.github.johnrengelman.shadow")
}

// Access versions defined in root build.gradle.kts
val bouncycastleVersion: String by project.extra
val junitVersion: String by project.extra
val assertjVersion: String by project.extra
val mockitoVersion: String by project.extra

dependencies {
    // Bouncy Castle Dependencies
    implementation("org.bouncycastle:bcprov-jdk18on:$bouncycastleVersion")
    implementation("org.bouncycastle:bcpkix-jdk18on:$bouncycastleVersion")

    // Test Dependencies
    testImplementation("org.junit.jupiter:junit-jupiter-api:$junitVersion")
    testRuntimeOnly("org.junit.jupiter:junit-jupiter-engine:$junitVersion")
    testImplementation("org.assertj:assertj-core:$assertjVersion")
    testImplementation("org.mockito:mockito-core:$mockitoVersion")
}

tasks.shadowJar {
    // Matches <shadedClassifierName>uber</shadedClassifierName>
    archiveClassifier.set("uber")

    // Filters: Matches the <excludes> in the POM
    exclude("META-INF/*.SF")
    exclude("META-INF/*.DSA")
    exclude("META-INF/*.RSA")

    // Transformers: Matches <transformer implementation="...ServicesResourceTransformer"/>
    mergeServiceFiles()

    // Relocations: Matches the <relocation> tag
    relocate("org.bouncycastle", "com.personal.image_toolkit.shaded.org.bouncycastle")
}

// Ensure the shadow jar is built when running 'assemble' or 'build'
tasks.assemble {
    dependsOn(tasks.shadowJar)
}