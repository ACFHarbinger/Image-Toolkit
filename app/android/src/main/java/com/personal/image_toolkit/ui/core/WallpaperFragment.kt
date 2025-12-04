package com.personal.image_toolkit.ui.tabs

import android.app.AlertDialog
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
import com.personal.image_toolkit.ui.DraggableContainer
import com.personal.image_toolkit.ui.DraggableItemView
import com.personal.image_toolkit.ui.MonitorDropWidget
import com.personal.image_toolkit.ui.OptionalField

/**
 * Android implementation of WallpaperTab.
 * Allows arranging monitors and setting wallpapers (Mocked functionality).
 */
class WallpaperFragment : BaseSingleGalleryFragment() {

    private lateinit var monitorContainer: DraggableContainer
    private lateinit var wallpaperTypeSpinner: AppCompatSpinner
    private lateinit var scanDirEdit: EditText
    private lateinit var btnSetWallpaper: Button

    override fun createSpecificContent(context: Context): View {
        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16)
        }

        // 1. Monitor Layout Group
        val layoutGroup = OptionalField(context).apply {
            setTitle("Monitor Layout")
        }
        
        monitorContainer = DraggableContainer(context).apply {
            // Add some mock monitors
            val mon1 = MonitorDropWidget(context).apply {
                monitorId = "1"
                layoutParams = LinearLayout.LayoutParams(300, 200).apply { marginEnd = 16 }
            }
            val mon2 = MonitorDropWidget(context).apply {
                monitorId = "2"
                layoutParams = LinearLayout.LayoutParams(300, 200)
            }
            
            // Add callback to handle drops
            val dropHandler = { id: String, path: String ->
                statusLabel.text = "Set Monitor $id to $path"
            }
            mon1.onImageDropped = dropHandler
            mon2.onImageDropped = dropHandler

            addView(mon1)
            addView(mon2)
        }
        
        layoutGroup.setContent(monitorContainer)
        container.addView(layoutGroup)

        // 2. Settings Group
        val settingsGroup = OptionalField(context).apply {
            setTitle("Wallpaper Settings")
        }
        val settingsLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        
        // Type Selector
        val typeRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        val lblType = TextView(context).apply { text = "Type: "; setTextColor(Color.WHITE) }
        wallpaperTypeSpinner = AppCompatSpinner(context).apply {
            val types = arrayOf("Image", "Slideshow", "Solid Color")
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, types)
        }
        typeRow.addView(lblType)
        typeRow.addView(wallpaperTypeSpinner)
        settingsLayout.addView(typeRow)

        // Scan Dir
        scanDirEdit = EditText(context).apply { hint = "Scan Directory..." }
        val btnScan = Button(context).apply {
            text = "Browse"
            setOnClickListener { scanDirectory(scanDirEdit.text.toString()) }
        }
        val scanRow = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(scanDirEdit, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            addView(btnScan)
        }
        settingsLayout.addView(scanRow)

        settingsGroup.setContent(settingsLayout)
        container.addView(settingsGroup)

        // 3. Action Button
        btnSetWallpaper = Button(context).apply {
            text = "Set Wallpaper"
            setBackgroundColor(Color.parseColor("#27ae60"))
            setOnClickListener { setWallpaper() }
        }
        container.addView(btnSetWallpaper)

        return container
    }

    override fun createCardView(context: Context, path: String): View {
        // Create draggable items for the gallery so they can be dropped onto monitors
        return DraggableItemView(context).apply {
            filePath = path
            text = java.io.File(path).name
            setBackgroundColor(Color.parseColor("#2c2f33"))
            // In real app, load thumbnail here
        }
    }

    private fun scanDirectory(path: String) {
        // Mock scan
        galleryItems.clear()
        for (i in 1..20) {
            galleryItems.add("/sdcard/Wallpapers/img_$i.jpg")
        }
        refreshGallery()
        statusLabel.text = "Scanned ${galleryItems.size} wallpapers."
    }

    private fun setWallpaper() {
        val type = wallpaperTypeSpinner.selectedItem.toString()
        AlertDialog.Builder(requireContext())
            .setTitle("Apply Wallpaper")
            .setMessage("Applying $type wallpaper to monitors...")
            .setPositiveButton("OK", null)
            .show()
    }
}