package com.personal.image_toolkit.ui.tabs

import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.widget.AppCompatSpinner
import androidx.core.view.setPadding
import androidx.fragment.app.Fragment
import com.personal.image_toolkit.ui.OptionalField

class ImageCrawlerFragment : Fragment() {

    private lateinit var typeSpinner: AppCompatSpinner
    private lateinit var settingsContainer: LinearLayout
    private lateinit var actionsLayout: LinearLayout
    private lateinit var statusLabel: TextView

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        val context = requireContext()
        val scrollView = ScrollView(context).apply {
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            setBackgroundColor(Color.parseColor("#2c2f33"))
        }
        val content = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16)
        }

        // 1. Crawler Type
        val typeRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        typeRow.addView(TextView(context).apply { text = "Type: "; setTextColor(Color.WHITE) })
        typeSpinner = AppCompatSpinner(context).apply {
            val types = arrayOf("General Web Crawler", "Danbooru API", "Gelbooru API")
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, types)
            
            // Simple listener to swap UI (mock implementation)
            // In real Android, use OnItemSelectedListener
        }
        typeRow.addView(typeSpinner)
        content.addView(typeRow)

        // 2. Settings (Dynamic)
        val settingsGroup = OptionalField(context).apply { setTitle("Configuration") }
        settingsContainer = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        
        // Default General Settings
        settingsContainer.addView(createEditText(context, "Target URL"))
        settingsContainer.addView(createEditText(context, "Login URL (Optional)"))
        
        settingsGroup.setContent(settingsContainer)
        content.addView(settingsGroup)

        // 3. Actions Builder
        val actionsGroup = OptionalField(context).apply { setTitle("Actions (General Only)") }
        actionsLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        
        val addActionBtn = Button(context).apply {
            text = "Add Action"
            setOnClickListener { addMockAction(context) }
        }
        actionsLayout.addView(addActionBtn)
        
        actionsGroup.setContent(actionsLayout)
        content.addView(actionsGroup)

        // 4. Output
        val outputGroup = OptionalField(context).apply { setTitle("Output") }
        val outputLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        outputLayout.addView(createEditText(context, "Download Directory"))
        outputGroup.setContent(outputLayout)
        content.addView(outputGroup)

        // 5. Run
        val btnRun = Button(context).apply {
            text = "Run Crawler"
            setBackgroundColor(Color.parseColor("#2980b9"))
            setOnClickListener { 
                statusLabel.text = "Crawling ${typeSpinner.selectedItem}..." 
            }
        }
        content.addView(btnRun)

        statusLabel = TextView(context).apply {
            text = "Ready."
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(0, 16, 0, 0)
        }
        content.addView(statusLabel)

        scrollView.addView(content)
        return scrollView
    }

    private fun createEditText(context: Context, hintText: String): EditText {
        return EditText(context).apply { hint = hintText }
    }

    private fun addMockAction(context: Context) {
        val actionView = TextView(context).apply {
            text = "• Click Element | Param: #next-button"
            setTextColor(Color.LTGRAY)
            setPadding(16, 4, 0, 4)
        }
        // Add before the button
        actionsLayout.addView(actionView, actionsLayout.childCount - 1)
    }
}