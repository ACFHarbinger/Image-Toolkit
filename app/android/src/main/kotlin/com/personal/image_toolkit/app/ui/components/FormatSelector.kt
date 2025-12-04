// ui/components/FormatSelector.kt
package com.example.imagetoolkit.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.layout.FlowRow
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun FormatSelector(
    title: String,
    formats: List<String>,
    selectedFormats: Set<String>,
    onFormatToggle: (String) -> Unit
) {
    SectionCard(title = title) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            FlowRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                formats.forEach { format ->
                    val isSelected = selectedFormats.contains(format)
                    FilterChip(
                        selected = isSelected,
                        onClick = { onFormatToggle(format) },
                        label = { Text(format.uppercase()) },
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
                    onClick = { formats.forEach { onFormatToggle(it) } },
                    modifier = Modifier.weight(1f)
                ) {
                    Text("Add All")
                }
                Button(
                    onClick = { selectedFormats.forEach { onFormatToggle(it) } },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error
                    )
                ) {
                    Text("Remove All")
                }
            }
        }
    }
}