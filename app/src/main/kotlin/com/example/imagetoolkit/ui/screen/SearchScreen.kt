// ui/screen/SearchScreen.kt
package com.example.imagetoolkit.ui.screen

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.imagetoolkit.ui.components.SectionCard
import android.widget.Toast

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun SearchScreen() {
    var searchDir by remember { mutableStateOf("") }
    var charName by remember { mutableStateOf("") }
    var seriesName by remember { mutableStateOf("") }
    var selectedTags by remember { mutableStateOf(setOf<String>()) }
    val allTags = listOf(
        "portrait", "full_body", "action", "close_up", "landscape", "night", "day",
        "indoor", "outdoor", "solo", "multiple", "fanart", "official", "color", "monochrome"
    )
    val context = LocalContext.current

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { Text("Search Images", style = MaterialTheme.typography.headlineSmall) }

        item {
            OutlinedTextField(
                value = searchDir,
                onValueChange = { searchDir = it },
                label = { Text("Search Directory") },
                modifier = Modifier.fillMaxWidth(),
                trailingIcon = {
                    IconButton(onClick = {
                        Toast.makeText(context, "Directory Chooser Opened", Toast.LENGTH_SHORT).show()
                    }) {
                        Icon(Icons.Default.FolderOpen, contentDescription = "Browse")
                    }
                }
            )
        }

        item {
            OutlinedTextField(
                value = charName,
                onValueChange = { charName = it },
                label = { Text("Character Name") },
                modifier = Modifier.fillMaxWidth()
            )
        }

        item {
            OutlinedTextField(
                value = seriesName,
                onValueChange = { seriesName = it },
                label = { Text("Series Name") },
                modifier = Modifier.fillMaxWidth()
            )
        }

        item {
            SectionCard(title = "Tags (Optional)") {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    FlowRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        allTags.forEach { tag ->
                            val isSelected = selectedTags.contains(tag)
                            FilterChip(
                                selected = isSelected,
                                onClick = {
                                    selectedTags = if (isSelected) selectedTags - tag else selectedTags + tag
                                },
                                label = { Text(tag) },
                                leadingIcon = if (isSelected) {
                                    { Icon(Icons.Default.Check, contentDescription = null) }
                                } else null
                            )
                        }
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Button(
                            onClick = { selectedTags = allTags.toSet() },
                            modifier = Modifier.weight(1f)
                        ) { Text("Select All") }
                        Button(
                            onClick = { selectedTags = setOf() },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                        ) { Text("Clear All") }
                    }
                }
            }
        }

        item {
            Button(
                onClick = {
                    val msg = "Running Search:\nDir: $searchDir\nChar: $charName"
                    Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.Search, contentDescription = null, modifier = Modifier.padding(end = 8.dp))
                Text("Search", fontSize = 16.sp)
            }
        }

        item {
            Text("Results (Simulated)", style = MaterialTheme.typography.titleMedium)
        }

        item {
            LazyVerticalGrid(
                columns = GridCells.Adaptive(100.dp),
                modifier = Modifier.height(300.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(12) { index ->
                    Box(
                        modifier = Modifier
                            .aspectRatio(1f)
                            .background(
                                MaterialTheme.colorScheme.secondaryContainer,
                                RoundedCornerShape(8.dp)
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("Img ${index + 1}", color = MaterialTheme.colorScheme.onSecondaryContainer)
                    }
                }
            }
        }
    }
}