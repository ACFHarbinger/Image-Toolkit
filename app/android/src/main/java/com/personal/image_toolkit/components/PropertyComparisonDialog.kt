package com.personal.image_toolkit.ui

import android.app.Dialog
import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.view.Window
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TableLayout
import android.widget.TableRow
import android.widget.TextView
import androidx.appcompat.app.AppCompatDialog

/**
 * Equivalent to PropertyComparisonDialog.
 * A Dialog that displays a comparison table of image properties.
 */
class PropertyComparisonDialog(
    context: Context,
    private val propertyData: List<Map<String, Any>>
) : AppCompatDialog(context) {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestWindowFeature(Window.FEATURE_NO_TITLE)

        // Root ScrollView
        val scrollView = ScrollView(context)
        scrollView.layoutParams = ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )
        
        // Main Container
        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16, 16, 16, 16)
            setBackgroundColor(Color.parseColor("#2c2f33"))
        }

        // Title
        val titleView = TextView(context).apply {
            text = "Image Property Comparison"
            textSize = 20f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            setPadding(0, 0, 0, 16)
        }
        container.addView(titleView)

        // Table
        val table = createTable()
        container.addView(table)

        // Close Button
        val closeBtn = androidx.appcompat.widget.AppCompatButton(context).apply {
            text = "Close"
            setOnClickListener { dismiss() }
        }
        container.addView(closeBtn)

        scrollView.addView(container)
        setContentView(scrollView)
        
        window?.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
    }

    private fun createTable(): TableLayout {
        val table = TableLayout(context).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            isStretchAllColumns = true
        }

        if (propertyData.isEmpty()) {
            val row = TableRow(context)
            row.addView(createCell("No Images Selected", Color.WHITE, true))
            table.addView(row)
            return table
        }

        // 1. Gather all Keys
        val allKeys = mutableSetOf<String>()
        propertyData.forEach { allKeys.addAll(it.keys) }

        // 2. Define Priority
        val priorityOrder = listOf("File Size", "Width", "Height", "Format", "Mode", "Path")
        val sectionKeys = priorityOrder.filter { it in allKeys }.toMutableList()
        allKeys.sorted().forEach { 
            if (it !in sectionKeys && it != "File Name") sectionKeys.add(it) 
        }

        // 3. Header Row
        val headerRow = TableRow(context)
        headerRow.addView(createCell("Property", Color.LTGRAY, true))
        headerRow.addView(createCell("Image File", Color.LTGRAY, true))
        headerRow.addView(createCell("Value", Color.LTGRAY, true))
        table.addView(headerRow)

        // 4. Data Rows
        val color1 = Color.parseColor("#2c2f33")
        val color2 = Color.parseColor("#23272a")

        var rowIndex = 0
        for (key in sectionKeys) {
            val bgColor = if (rowIndex % 2 == 0) color1 else color2
            
            for (item in propertyData) {
                val row = TableRow(context)
                row.setBackgroundColor(bgColor)

                val imgName = item["File Name"]?.toString() ?: "Unknown"
                val value = item[key]?.toString() ?: "N/A"

                row.addView(createCell(key, Color.parseColor("#b9bbbe"), false))
                row.addView(createCell(imgName, Color.parseColor("#b9bbbe"), false))
                row.addView(createCell(value, Color.WHITE, false))
                
                table.addView(row)
            }
            rowIndex++
        }

        return table
    }

    private fun createCell(text: String, textColor: Int, isHeader: Boolean): TextView {
        return TextView(context).apply {
            this.text = text
            this.setTextColor(textColor)
            this.setPadding(8, 8, 8, 8)
            this.textSize = if (isHeader) 16f else 14f
            if (isHeader) this.setTypeface(null, android.graphics.Typeface.BOLD)
        }
    }
}