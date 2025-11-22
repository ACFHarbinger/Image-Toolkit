// This file assumes it is placed in the 'app' directory, 
// and the root project applies the necessary Android plugins.

plugins {
    // Apply the Android Application plugin
    alias(libs.plugins.android.application)
    // Kotlin Android plugin
    alias(libs.plugins.kotlin.android) 
}

android {
    // Configuration common across your Android targets
    namespace = "com.personal.image_toolkit.app"
    compileSdk = 34 // Use a recent version

    defaultConfig {
        applicationId = "com.personal.image_toolkit.app"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // Required for Compose
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    
    // Java/Kotlin configuration for the Android compile step
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    kotlinOptions {
        jvmTarget = "1.8"
    }

    // Compose configuration
    buildFeatures {
        compose = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.11" // Use version compatible with AGP/Kotlin
    }
}

dependencies {
    // --- Link the Cryptography module to the Android application ---
    // The Android app needs access to the cryptography logic
    implementation(project(":cryptography")) 

    // --- Android/Compose Dependencies (from uploaded file) ---
    implementation(libs.androidx.core.ktx) // Using version reference from Version Catalog (assumed)
    implementation(libs.androidx.lifecycle.runtime.ktx) 
    implementation(libs.androidx.activity.compose) 
    
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    
    // Image loading (Coil)
    implementation(libs.coil.compose)
    
    // Testing and Debug
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.espresso.core)
    
    // Compose Testing
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
}