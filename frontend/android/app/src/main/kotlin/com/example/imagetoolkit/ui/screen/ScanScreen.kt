// ui/screen/ScanScreen.kt
package com.example.imagetoolkit.ui.screen

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.example.imagetoolkit.ui.components.SectionCard
import android.widget.Toast

@Composable
fun ScanScreen() {
    val context = LocalContext.current
    var scanDir by remember { mutableStateOf("") }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            SectionCard(title = "Scan Directory", startOpen = true) {
                Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    OutlinedTextField(
                        value = scanDir,
                        onValueChange = { scanDir = it },
                        label = { Text("Directory to Scan") },
                        modifier = Modifier.fillMaxWidth(),
                        trailingIcon = {
                            IconButton(onClick = {
                                Toast.makeText(context, "Directory Chooser Opened", Toast.LENGTH_SHORT).show()
                            }) {
                                Icon(Icons.Default.FolderOpen, contentDescription = "Browse")
                            }
                        }
                    )

                    Button(onClick = { /* View */ }, modifier = Modifier.fillMaxWidth()) {
                        Text("View Full Size Image (from selection)")
                    }

                    Text("Scanned Images (Simulated)", style = MaterialTheme.typography.titleMedium)
                    LazyVerticalGrid(
                        columns = GridCells.Adaptive(100.dp),
                        modifier = Modifier.height(400.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(20) { index ->
                            Box(
                                modifier = Modifier
                                    .aspectRatio(1f)
                                    .background(
                                        MaterialTheme.colorScheme.secondaryContainer,
                                        RoundedCornerShape(8.dp)
                                    )
                                    .clickable {
                                        Toast.makeText(context, "Selected Image ${index + 1}", Toast.LENGTH_SHORT).show()
                                    },
                                contentAlignment = Alignment.Center
                            ) {
                                Text("Img ${index + 1}", color = MaterialTheme.colorScheme.onSecondaryContainer)
                            }
                        }
                    }

                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { /* Add */ }, modifier = Modifier.fillMaxWidth()) {
                            Text("Add Selected Images to Database")
                        }
                        Button(
                            onClick = { /* Refresh */ },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.secondary)
                        ) {
                            Text("Refresh Image Directory")
                        }
                        Button(
                            onClick = { /* Delete All */ },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                        ) {
                            Text("Delete All Image Paths in Directory")
                        }
                    }
                }
            }
        }
    }
}