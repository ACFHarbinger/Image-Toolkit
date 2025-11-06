// ui/screen/DeleteScreen.kt
package com.example.imagetoolkit.ui.screen

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DeleteForever
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.imagetoolkit.ui.components.FileInput
import com.example.imagetoolkit.ui.components.FormatSelector
import android.widget.Toast

@Composable
fun DeleteScreen() {
    var targetPath by remember { mutableStateOf("") }
    var confirmDelete by remember { mutableStateOf(true) }
    var selectedExtensions by remember { mutableStateOf(setOf<String>()) }
    val allExtensions = listOf("jpg", "png", "bmp", "gif", "webp", "tiff", "txt", "tmp")
    val context = LocalContext.current

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { Text("Delete Files", style = MaterialTheme.typography.headlineSmall) }

        item {
            FileInput("Target Path (File or Dir)", targetPath) { targetPath = it }
        }

        item {
            FormatSelector(
                title = "Target Extensions (Optional)",
                formats = allExtensions,
                selectedFormats = selectedExtensions,
                onFormatToggle = { ext ->
                    selectedExtensions = if (selectedExtensions.contains(ext))
                        selectedExtensions - ext else selectedExtensions + ext
                }
            )
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { confirmDelete = !confirmDelete }
                    .padding(vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Checkbox(checked = confirmDelete, onCheckedChange = { confirmDelete = it })
                Spacer(Modifier.width(8.dp))
                Text("Require confirmation before delete")
            }
        }

        item {
            Button(
                onClick = {
                    val msg = "Running Delete:\nTarget: $targetPath\nConfirm: $confirmDelete"
                    Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
            ) {
                Icon(Icons.Default.DeleteForever, contentDescription = null, modifier = Modifier.padding(end = 8.dp))
                Text("Run Delete", fontSize = 16.sp)
            }
        }
    }
}