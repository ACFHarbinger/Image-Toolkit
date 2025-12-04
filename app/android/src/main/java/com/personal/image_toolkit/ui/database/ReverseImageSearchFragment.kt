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
import android.widget.TextView
import androidx.appcompat.widget.AppCompatSpinner
import androidx.core.view.setPadding
import com.personal.image_toolkit.ui.ClickableItemView
import com.personal.image_toolkit.ui.OptionalField

/**
 * Android implementation of ReverseImageSearchTab.
 * Inherits from BaseSingleGalleryFragment as per Python structure.
 */
class ReverseImageSearchFragment : BaseSingleGalleryFragment() {

    private lateinit var scanDirEdit: EditText
    private lateinit var browserSpinner: AppCompatSpinner
    private lateinit var modeSpinner: AppCompatSpinner
    private lateinit var keepOpenCheck: CheckBox
    private lateinit var btnSearch: Button
    private var selectedImagePath: String? = null

    override fun createSpecificContent(context: Context): View {
        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16)
        }

        // 1. Config Group
        val configGroup = OptionalField(context).apply { setTitle("Search Configuration") }
        val configLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }

        // Scan Dir
        val scanRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        scanDirEdit = EditText(context).apply { hint = "Scan Directory..." }
        val btnBrowse = Button(context).apply {
            text = "Browse"
            setOnClickListener { mockScan(scanDirEdit.text.toString()) }
        }
        scanRow.addView(scanDirEdit, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        scanRow.addView(btnBrowse)
        configLayout.addView(scanRow)

        // Settings Row
        val settingsRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        
        browserSpinner = AppCompatSpinner(context).apply {
            val browsers = arrayOf("Chrome", "Firefox", "Brave")
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, browsers)
        }
        settingsRow.addView(browserSpinner)

        modeSpinner = AppCompatSpinner(context).apply {
            val modes = arrayOf("All Matches", "Visual", "Exact")
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, modes)
        }
        settingsRow.addView(modeSpinner)

        configLayout.addView(settingsRow)

        keepOpenCheck = CheckBox(context).apply {
            text = "Keep Browser Open"
            isChecked = true
            setTextColor(Color.WHITE)
        }
        configLayout.addView(keepOpenCheck)

        // Search Button
        btnSearch = Button(context).apply {
            text = "Search Selected Image"
            isEnabled = false
            setBackgroundColor(Color.parseColor("#007AFF"))
            setOnClickListener { performSearch() }
        }
        configLayout.addView(btnSearch)

        configGroup.setContent(configLayout)
        container.addView(configGroup)

        return container
    }

    override fun createCardView(context: Context, path: String): View {
        return ClickableItemView(context).apply {
            setFilePath(path)
            if (path == selectedImagePath) {
                setBackgroundColor(Color.parseColor("#007AFF")) // Blue Selection
            } else {
                setBackgroundColor(Color.parseColor("#2c2f33"))
            }
            
            onPathClicked = { p -> 
                selectedImagePath = p
                btnSearch.isEnabled = true
                statusLabel.text = "Selected: ${java.io.File(p).name}"
                refreshGallery() // Redraw to update borders
            }
        }
    }

    private fun mockScan(path: String) {
        galleryItems.clear()
        for (i in 1..10) {
            galleryItems.add("/sdcard/Images/img_$i.jpg")
        }
        refreshGallery()
        statusLabel.text = "Found ${galleryItems.size} images."
    }

    private fun performSearch() {
        val browser = browserSpinner.selectedItem.toString()
        val mode = modeSpinner.selectedItem.toString()
        
        AlertDialog.Builder(requireContext())
            .setTitle("Reverse Search")
            .setMessage("Searching Google Lens via $browser ($mode)...\nImage: $selectedImagePath")
            .setPositiveButton("OK", null)
            .show()
    }
}