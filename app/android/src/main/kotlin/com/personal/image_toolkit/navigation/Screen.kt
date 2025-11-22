// navigation/Screen.kt
package com.example.imagetoolkit.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(
    val route: String,
    val label: String,
    val icon: ImageVector
) {
    object Convert : Screen("convert", "Convert", Icons.Default.Transform)
    object Merge : Screen("merge", "Merge", Icons.Default.CallMerge)
    object Delete : Screen("delete", "Delete", Icons.Default.DeleteForever)
    object Search : Screen("search", "Search", Icons.Default.Search)
    object Database : Screen("database", "Database", Icons.Default.Storage)
    object Scan : Screen("scan", "Scan", Icons.Default.FilterCenterFocus)
}