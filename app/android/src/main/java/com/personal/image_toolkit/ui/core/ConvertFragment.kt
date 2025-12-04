package com.personal.image_toolkit.ui.tabs

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
import com.personal.image_toolkit.ui.OptionalField
import java.io.File

/**
 * Android implementation of ConvertTab.
 */
class ConvertFragment : BaseTwoGalleriesFragment() {

    private lateinit var inputPathEdit: EditText
    private lateinit var outputPathEdit: EditText
    private lateinit var formatSpinner: AppCompatSpinner
    private lateinit var deleteCheckBox: CheckBox
    private lateinit var btnConvertAll: Button
    private lateinit var btnConvertSelected: Button

    override fun createSpecificContent(context: Context): View {
        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16)
        }

        // 1. Targets
        inputPathEdit = EditText(context).apply { hint = "Input Directory Path..." }
        val btnBrowse = Button(context).apply { 
            text = "Browse..." 
            setOnClickListener { scanDirectory(inputPathEdit.text.toString()) }
        }
        container.addView(createRow(context, inputPathEdit, btnBrowse))

        // 2. Settings
        formatSpinner = AppCompatSpinner(context).apply {
            val formats = arrayOf("png", "jpg", "webp", "bmp")
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, formats)
        }
        container.addView(formatSpinner)

        outputPathEdit = EditText(context).apply { hint = "Output Path (Optional)" }
        val optionalOutput = OptionalField(context).apply {
            setTitle("Output Path")
            setContent(outputPathEdit)
        }
        container.addView(optionalOutput)

        deleteCheckBox = CheckBox(context).apply {
            text = "Delete original files after conversion"
            setTextColor(Color.LTGRAY)
        }
        container.addView(deleteCheckBox)

        // 3. Actions
        btnConvertAll = Button(context).apply {
            text = "Convert All"
            setOnClickListener { startConversion(false) }
        }
        btnConvertSelected = Button(context).apply {
            text = "Convert Selected (0)"
            isEnabled = false
            setOnClickListener { startConversion(true) }
        }
        container.addView(createRow(context, btnConvertAll, btnConvertSelected))

        return container
    }

    override fun createCardView(context: Context, path: String, isSelected: Boolean): View {
        return ClickableItemView(context).apply {
            // FIX: Use property assignment instead of method call
            filePath = path

            // Visual style for selection
            if (isSelected) {
                setBackgroundColor(Color.parseColor("#3498db"))
            } else {
                setBackgroundColor(Color.parseColor("#2c2f33"))
            }

            onPathClicked = { p -> toggleSelection(p) }
            onPathDoubleClicked = { p -> /* Open Preview logic */ }
        }
    }

    override fun onSelectionChanged() {
        btnConvertSelected.text = "Convert Selected (${selectedFiles.size})"
        btnConvertSelected.isEnabled = selectedFiles.isNotEmpty()
    }

    private fun createRow(context: Context, v1: View, v2: View): LinearLayout {
        return LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(v1, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            addView(v2)
        }
    }

    // --- Logic Stub ---
    private fun scanDirectory(path: String) {
        // Real implementation would use File(path).walk() in coroutine
        if (path.isEmpty()) return
        
        foundFiles.clear()
        // Mocking data for UI demonstration
        for (i in 1..20) {
            foundFiles.add("$path/image_$i.png")
        }
        refreshFoundGallery()
        statusLabel.text = "Found ${foundFiles.size} files."
    }

    private fun startConversion(onlySelected: Boolean) {
        statusLabel.text = "Converting..."
        // Launch Worker here
    }
}