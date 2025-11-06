/*
 * This is the root build file where you can define global configurations.
 * All submodules (like your Android project) inherit repositories and dependencies
 * defined here using 'subprojects' or 'allprojects'.
 */

allprojects {
    // Set up standard repositories for all projects
    repositories {
        google()
        mavenCentral()
    }
}

subprojects {
    // Configuration common to all sub-projects (e.g., compile settings)
}