// ui/components/FileInput.kt
package com.example.imagetoolkit.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.InsertDriveFile
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import android.widget.Toast

@Composable
fun FileInput(
    label: String,
    path: String,
    onPathChange: (String) -> Unit
) {
    val context = LocalContext.current
    OutlinedTextField(
        value = path,
        onValueChange = onPathChange,
        label = { Text(label) },
        modifier = Modifier.fillMaxWidth(),
        placeholder = { Text("Select path...") }
    )
    Spacer(Modifier.height(8.dp))
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Button(
            onClick = { Toast.makeText(context, "File Chooser Opened", Toast.LENGTH_SHORT).show() },
            modifier = Modifier.weight(1f)
        ) {
            Icon(Icons.Default.InsertDriveFile, contentDescription = null, modifier = Modifier.padding(end = 8.dp))
            Text("Choose File")
        }
        Button(
            onClick = { Toast.makeText(context, "Directory Chooser Opened", Toast.LENGTH_SHORT).show() },
            modifier = Modifier.weight(1f)
        ) {
            Icon(Icons.Default.FolderOpen, contentDescription = null, modifier = Modifier.padding(end = 8.dp))
            Text("Choose Dir")
        }
    }
}