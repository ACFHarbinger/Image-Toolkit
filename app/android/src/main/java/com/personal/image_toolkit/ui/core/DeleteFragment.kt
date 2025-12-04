package com.personal.image_toolkit.ui.tabs

import android.app.AlertDialog
import android.content.Context
import android.graphics.Color
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import androidx.appcompat.widget.AppCompatSpinner
import androidx.core.view.setPadding
import com.personal.image_toolkit.ui.ClickableItemView
import com.personal.image_toolkit.ui.PropertyComparisonDialog

/**
 * Android implementation of DeleteTab.
 * Handles duplicate scanning and deletion.
 */
class DeleteFragment : BaseTwoGalleriesFragment() {

    private lateinit var targetPathEdit: EditText
    private lateinit var scanMethodSpinner: AppCompatSpinner
    private lateinit var confirmCheckBox: CheckBox
    private lateinit var btnDeleteSelected: Button
    private lateinit var btnCompare: Button

    override fun createSpecificContent(context: Context): View {
        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16)
        }

        // Target
        targetPathEdit = EditText(context).apply { hint = "Target Path..." }
        val btnBrowse = Button(context).apply { 
            text = "Browse/Scan"
            setOnClickListener { startScan() } 
        }
        
        val row = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(targetPathEdit, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            addView(btnBrowse)
        }
        container.addView(row)

        // Settings
        scanMethodSpinner = AppCompatSpinner(context).apply {
            val methods = arrayOf("All Files", "Exact Match", "Similar (Hash)")
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, methods)
        }
        container.addView(scanMethodSpinner)

        confirmCheckBox = CheckBox(context).apply {
            text = "Require confirmation"
            isChecked = true
            setTextColor(Color.LTGRAY)
        }
        container.addView(confirmCheckBox)

        // Actions
        btnCompare = Button(context).apply {
            text = "Compare Properties"
            isEnabled = false
            setOnClickListener { showComparison() }
        }
        btnDeleteSelected = Button(context).apply {
            text = "Delete Selected (0)"
            isEnabled = false
            setBackgroundColor(Color.RED)
            setOnClickListener { deleteSelected() }
        }
        
        container.addView(btnCompare)
        container.addView(btnDeleteSelected)

        return container
    }

    override fun createCardView(context: Context, path: String, isSelected: Boolean): View {
        return ClickableItemView(context).apply {
            filePath = path
            if (isSelected) {
                // Red border styling ideally
                setBackgroundColor(Color.parseColor("#e74c3c")) 
            } else {
                setBackgroundColor(Color.parseColor("#2c2f33"))
            }
            onPathClicked = { p -> toggleSelection(p) }
        }
    }

    override fun onSelectionChanged() {
        btnDeleteSelected.text = "Delete Selected (${selectedFiles.size})"
        btnDeleteSelected.isEnabled = selectedFiles.isNotEmpty()
        btnCompare.isEnabled = selectedFiles.size > 1
    }

    private fun startScan() {
        // Mock scan
        val path = targetPathEdit.text.toString()
        foundFiles.clear()
        foundFiles.add("$path/duplicate_1.jpg")
        foundFiles.add("$path/original_1.jpg")
        foundFiles.add("$path/duplicate_2.jpg")
        refreshFoundGallery()
        statusLabel.text = "Scan complete. Found duplicates."
    }

    private fun deleteSelected() {
        if (confirmCheckBox.isChecked) {
            AlertDialog.Builder(requireContext())
                .setTitle("Confirm Delete")
                .setMessage("Delete ${selectedFiles.size} files?")
                .setPositiveButton("Yes") { _, _ -> performDelete() }
                .setNegativeButton("No", null)
                .show()
        } else {
            performDelete()
        }
    }

    private fun performDelete() {
        // Logic to delete files
        statusLabel.text = "Deleted ${selectedFiles.size} files."
        selectedFiles.clear()
        refreshSelectedGallery()
        refreshFoundGallery()
    }
    
    private fun showComparison() {
        // Create mock data for the dialog
        val data = selectedFiles.map { path ->
            mapOf(
                "File Name" to java.io.File(path).name,
                "Path" to path,
                "Size" to "2MB",
                "Dimensions" to "1920x1080"
            )
        }
        PropertyComparisonDialog(requireContext(), data).show()
    }
}