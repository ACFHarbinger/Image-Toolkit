package com.personal.image_toolkit.ui.windows

import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.widget.AppCompatSpinner
import androidx.core.view.setPadding
import androidx.fragment.app.DialogFragment
import com.personal.image_toolkit.ui.OptionalField

/**
 * Android implementation of SettingsWindow.
 * Designed as a DialogFragment to pop up over the main content.
 */
class SettingsFragment : DialogFragment() {

    override fun onStart() {
        super.onStart()
        dialog?.window?.setLayout(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        val context = requireContext()
        val scrollView = ScrollView(context).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(Color.WHITE) // Light theme for settings dialog often works better
        }

        val content = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32)
        }

        // Header
        val header = TextView(context).apply {
            text = "Application Settings"
            textSize = 22f
            setTextColor(Color.BLACK)
            setPadding(0, 0, 0, 32)
        }
        content.addView(header)

        // 1. Account Info
        val accountGroup = OptionalField(context).apply { setTitle("Account Information") }
        val accountLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        accountLayout.addView(TextView(context).apply { text = "Logged in as: User"; setTextColor(Color.DKGRAY) })
        // Add password reset fields here...
        accountGroup.setContent(accountLayout)
        content.addView(accountGroup)

        // 2. Preferences
        val prefsGroup = OptionalField(context).apply { setTitle("Preferences") }
        val prefsLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        
        val themeRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        themeRow.addView(TextView(context).apply { text = "Theme: "; setTextColor(Color.BLACK) })
        val themeSpinner = AppCompatSpinner(context).apply {
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, arrayOf("Dark", "Light"))
        }
        themeRow.addView(themeSpinner)
        prefsLayout.addView(themeRow)
        
        prefsGroup.setContent(prefsLayout)
        content.addView(prefsGroup)

        // 3. Tab Configs (Simplified)
        val configGroup = OptionalField(context).apply { setTitle("Default Configurations") }
        configGroup.setContent(TextView(context).apply { text = "No saved configurations."; setTextColor(Color.GRAY) })
        content.addView(configGroup)

        // Buttons
        val btnLayout = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, 32, 0, 0)
        }
        
        val btnClose = Button(context).apply {
            text = "Close"
            setOnClickListener { dismiss() }
        }
        val btnSave = Button(context).apply {
            text = "Save & Update"
            setBackgroundColor(Color.BLUE)
            setTextColor(Color.WHITE)
            setOnClickListener { 
                // Save logic
                dismiss() 
            }
        }
        
        btnLayout.addView(btnClose)
        btnLayout.addView(View(context).apply { layoutParams = LinearLayout.LayoutParams(16, 1) })
        btnLayout.addView(btnSave)
        
        content.addView(btnLayout)

        scrollView.addView(content)
        return scrollView
    }
}