// ui/screen/MergeScreen.kt
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
fun MergeScreen() {
    var direction by remember { mutableStateOf("horizontal") }
    val directions = listOf("horizontal", "vertical", "grid")
    var inputPath by remember { mutableStateOf("") }
    var outputPath by remember { mutableStateOf("") }
    var spacing by remember { mutableStateOf("0") }
    var gridRows by remember { mutableStateOf("2") }
    var gridCols by remember { mutableStateOf("2") }
    var selectedFormats by remember { mutableStateOf(setOf<String>()) }
    val allFormats = listOf("jpg", "png", "bmp", "gif", "webp", "tiff")
    val context = LocalContext.current
    var directionExpanded by remember { mutableStateOf(false) }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { Text("Merge Images", style = MaterialTheme.typography.headlineSmall) }

        item {
            ExposedDropdownMenuBox(
                expanded = directionExpanded,
                onExpandedChange = { directionExpanded = !directionExpanded }
            ) {
                OutlinedTextField(
                    value = direction,
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("Direction") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = directionExpanded) },
                    modifier = Modifier.fillMaxWidth().menuAnchor()
                )
                ExposedDropdownMenu(
                    expanded = directionExpanded,
                    onDismissRequest = { directionExpanded = false }
                ) {
                    directions.forEach { dir ->
                        DropdownMenuItem(
                            text = { Text(dir.capitalize()) },
                            onClick = {
                                direction = dir
                                directionExpanded = false
                            }
                        )
                    }
                }
            }
        }

        item {
            FileInput("Input Paths (Files or Dir)", inputPath) { inputPath = it }
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
            OutlinedTextField(
                value = spacing,
                onValueChange = { spacing = it.filter { char -> char.isDigit() } },
                label = { Text("Spacing (px)") },
                keyboardOptions = androidx.compose.ui.text.input.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Number),
                modifier = Modifier.fillMaxWidth()
            )
        }

        if (direction == "grid") {
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    OutlinedTextField(
                        value = gridRows,
                        onValueChange = { gridRows = it.filter { char -> char.isDigit() } },
                        label = { Text("Rows") },
                        keyboardOptions = androidx.compose.ui.text.input.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Number),
                        modifier = Modifier.weight(1f)
                    )
                    OutlinedTextField(
                        value = gridCols,
                        onValueChange = { gridCols = it.filter { char -> char.isDigit() } },
                        label = { Text("Cols") },
                        keyboardOptions = androidx.compose.ui.text.input.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Number),
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }

        item {
            Button(
                onClick = {
                    val msg = "Running Merge:\nDirection: $direction\nInput: $inputPath"
                    Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.PlayArrow, contentDescription = null, modifier = Modifier.padding(end = 8.dp))
                Text("Run Merge", fontSize = 16.sp)
            }
        }
    }
}