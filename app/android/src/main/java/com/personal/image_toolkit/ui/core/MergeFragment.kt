package com.personal.image_toolkit.ui.tabs

import android.content.Context
import android.graphics.Color
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.widget.AppCompatSpinner
import androidx.core.view.setPadding
import com.personal.image_toolkit.ui.ClickableItemView

/**
 * Android implementation of MergeTab.
 * Handles merging images into grids, panoramas, etc.
 */
class MergeFragment : BaseTwoGalleriesFragment() {

    private lateinit var inputDirEdit: EditText
    private lateinit var directionSpinner: AppCompatSpinner
    private lateinit var btnRunMerge: Button

    override fun createSpecificContent(context: Context): View {
        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16)
        }

        // Input
        container.addView(createLabel(context, "Input Directory"))
        inputDirEdit = EditText(context)
        val btnBrowse = Button(context).apply { 
            text = "Browse"
            setOnClickListener { /* Browse logic */ }
        }
        val row = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(inputDirEdit, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            addView(btnBrowse)
        }
        container.addView(row)

        // Config
        container.addView(createLabel(context, "Merge Direction"))
        directionSpinner = AppCompatSpinner(context).apply {
            val directions = arrayOf("Horizontal", "Vertical", "Grid", "GIF")
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, directions)
        }
        container.addView(directionSpinner)

        // Action
        btnRunMerge = Button(context).apply {
            text = "Run Merge (Select 2+)"
            isEnabled = false
            setOnClickListener { /* Merge Logic */ }
        }
        container.addView(btnRunMerge)

        return container
    }

    override fun createCardView(context: Context, path: String, isSelected: Boolean): View {
        return ClickableItemView(context).apply {
            setFilePath(path)
            if (isSelected) {
                setBackgroundColor(Color.parseColor("#27ae60")) // Green for merge
            } else {
                setBackgroundColor(Color.parseColor("#2c2f33"))
            }
            onPathClicked = { p -> toggleSelection(p) }
        }
    }

    override fun onSelectionChanged() {
        val count = selectedFiles.size
        btnRunMerge.text = if (count < 2) "Select 2+ images" else "Run Merge ($count)"
        btnRunMerge.isEnabled = count >= 2
    }
    
    private fun createLabel(context: Context, text: String): TextView {
        return TextView(context).apply {
            this.text = text
            setTextColor(Color.WHITE)
        }
    }
}