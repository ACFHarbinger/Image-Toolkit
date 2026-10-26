// Placeholder entry point — see ../../../../../../README.md. Not yet wired
// to a backend API.
package com.acfharbinger.cel_shaded_generator

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Text

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            Text("Cel-Shaded-Generator — scaffold, not yet implemented.")
        }
    }
}
