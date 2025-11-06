// ui/screen/DatabaseScreen.kt
package com.example.imagetoolkit.ui.screen

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Power
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.example.imagetoolkit.ui.components.SectionCard
import android.widget.Toast

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun DatabaseScreen() {
    var host by remember { mutableStateOf("localhost") }
    var port by remember { mutableStateOf("5432") }
    var user by remember { mutableStateOf("postgres") }
    var password by remember { mutableStateOf("") }
    var dbName by remember { mutableStateOf("image_db") }
    var imagePath by remember { mutableStateOf("") }
    var seriesName by remember { mutableStateOf("") }
    var seriesExpanded by remember { mutableStateOf(false) }
    var characters by remember { mutableStateOf("") }
    var selectedTags by remember { mutableStateOf(setOf<String>()) }
    val allTags = listOf(
        "landscape", "night", "day", "indoor", "outdoor", "solo", "multiple", "fanart",
        "official", "cosplay", "portrait", "full_body", "action", "close_up", "nsfw"
    )
    val seriesOptions = listOf("Naruto", "Bleach", "One Piece", "Dragon Ball")
    val context = LocalContext.current

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            SectionCard(title = "PostgreSQL Connection", startOpen = true) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(value = host, onValueChange = { host = it }, label = { Text("Host") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = port, onValueChange = { port = it }, label = { Text("Port") }, keyboardOptions = androidx.compose.ui.text.input.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Number), modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = user, onValueChange = { user = it }, label = { Text("User") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = password, onValueChange = { password = it }, label = { Text("Password") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = dbName, onValueChange = { dbName = it }, label = { Text("Database Name") }, modifier = Modifier.fillMaxWidth())
                    Button(
                        onClick = { Toast.makeText(context, "Connecting to $dbName...", Toast.LENGTH_SHORT).show() },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.Power, contentDescription = null, modifier = Modifier.padding(end = 8.dp))
                        Text("Connect to PostgreSQL")
                    }
                }
            }
        }

        item {
            Text(
                "Stats: Not connected to database",
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                    .padding(16.dp),
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        item {
            SectionCard(title = "Single Image Metadata", startOpen = true) {
                Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    OutlinedTextField(
                        value = imagePath,
                        onValueChange = { imagePath = it },
                        label = { Text("Image File Path") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { /* Browse */ }, modifier = Modifier.weight(1f)) { Text("Browse") }
                        Button(onClick = { /* View */ }, modifier = Modifier.weight(1f)) { Text("View") }
                        Button(onClick = { /* Load */ }, modifier = Modifier.weight(1f)) { Text("Load") }
                    }

                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(200.dp)
                            .background(MaterialTheme.colorScheme.secondaryContainer, RoundedCornerShape(8.dp)),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("Select an image to edit...", color = MaterialTheme.colorScheme.onSecondaryContainer)
                    }

                    ExposedDropdownMenuBox(
                        expanded = seriesExpanded,
                        onExpandedChange = { seriesExpanded = !seriesExpanded }
                    ) {
                        OutlinedTextField(
                            value = seriesName,
                            onValueChange = { seriesName = it },
                            label = { Text("Series Name") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = seriesExpanded) },
                            modifier = Modifier.fillMaxWidth().menuAnchor()
                        )
                        ExposedDropdownMenu(
                            expanded = seriesExpanded,
                            onDismissRequest = { seriesExpanded = false }
                        ) {
                            seriesOptions.forEach { series ->
                                DropdownMenuItem(
                                    text = { Text(series) },
                                    onClick = {
                                        seriesName = series
                                        seriesExpanded = false
                                    }
                                )
                            }
                        }
                    }

                    OutlinedTextField(
                        value = characters,
                        onValueChange = { characters = it },
                        label = { Text("Characters (comma-separated)") },
                        modifier = Modifier.fillMaxWidth()
                    )

                    Text("Tags", style = MaterialTheme.typography.titleSmall)
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
                                label = { Text(tag) }
                            )
                        }
                    }

                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { /* Add/Update */ }, modifier = Modifier.fillMaxWidth()) {
                            Text("Add/Update Image Path")
                        }
                        Button(onClick = { /* Update Meta */ }, modifier = Modifier.fillMaxWidth()) {
                            Text("Update Loaded Metadata")
                        }
                        Button(
                            onClick = { /* Delete */ },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                        ) {
                            Text("Delete from Database")
                        }
                    }
                }
            }
        }
    }
}