// ui/screen/ConvertScreen.kt
package com.example.imagetoolkit.ui.screen

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.imagetoolkit.ui.components.FileInput
import com.example.imagetoolkit.ui.components.FormatSelector
import android.widget.Toast

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ConvertScreen() {
    var outputFormat by remember { mutableStateOf("png") }
    var inputPath by remember { mutableStateOf("") }
    var outputPath by remember { mutableStateOf("") }
    var selectedFormats by remember { mutableStateOf(setOf<String>()) }
    val context = LocalContext.current
    val allFormats = listOf("jpg", "png", "bmp", "gif", "webp", "tiff")

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { Text("Convert Image Format", style = MaterialTheme.typography.headlineSmall) }
        item {
            OutlinedTextField(
                value = outputFormat,
                onValueChange = { outputFormat = it },
                label = { Text("Output Format") },
                modifier = Modifier.fillMaxWidth()
            )
        }
        item {
            FileInput("Input Path (File or Dir)", inputPath) { inputPath = it }
        }
        item {
            com.example.imagetoolkit.ui.components.SectionCard("Output Path (Optional)") {
                FileInput("Output Path", outputPath) { outputPath = it }
            }
        }
        item {
            FormatSelector(
                title = "Input Formats (if input is dir)",
                formats = allFormats,
                selectedFormats = selectedFormats,
                onFormatToggle = { format ->
                    selectedFormats = if (selectedFormats.contains(format))
                        selectedFormats - format else selectedFormats + format
                }
            )
        }
        item {
            Button(
                onClick = {
                    val msg = "Running Convert: \n- Format: $outputFormat\n- Input: $inputPath"
                    Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.PlayArrow, contentDescription = null, modifier = Modifier.padding(end = 8.dp))
                Text("Run Conversion", fontSize = 16.sp)
            }
        }
    }
}