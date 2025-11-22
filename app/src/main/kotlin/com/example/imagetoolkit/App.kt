package com.example.imagetoolkit

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.example.imagetoolkit.ui.MainAppScreen
import com.example.imagetoolkit.ui.theme.ImageToolkitTheme

class App : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            ImageToolkitTheme {
                MainAppScreen()
            }
        }
    }
}