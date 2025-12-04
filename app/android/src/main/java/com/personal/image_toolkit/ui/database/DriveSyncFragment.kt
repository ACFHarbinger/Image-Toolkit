package com.personal.image_toolkit.ui.tabs

import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.widget.AppCompatSpinner
import androidx.core.view.setPadding
import androidx.fragment.app.Fragment
import com.personal.image_toolkit.ui.OptionalField

class DriveSyncFragment : Fragment() {

    private lateinit var providerSpinner: AppCompatSpinner
    private lateinit var localPathEdit: EditText
    private lateinit var remotePathEdit: EditText
    private lateinit var dryRunCheck: CheckBox
    private lateinit var btnSync: Button
    private lateinit var statusLog: TextView

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
            setBackgroundColor(Color.parseColor("#2c2f33"))
        }

        val content = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16)
        }

        // 1. Config Group
        val configGroup = OptionalField(context).apply { setTitle("Cloud Sync Configuration") }
        val configLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }

        // Provider
        val providerRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        providerRow.addView(createLabel(context, "Provider: "))
        providerSpinner = AppCompatSpinner(context).apply {
            val items = arrayOf("Google Drive", "Dropbox", "OneDrive")
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, items)
        }
        providerRow.addView(providerSpinner)
        configLayout.addView(providerRow)

        // Paths
        localPathEdit = EditText(context).apply { hint = "Local Source Directory" }
        configLayout.addView(localPathEdit)
        
        remotePathEdit = EditText(context).apply { hint = "Remote Destination Path" }
        configLayout.addView(remotePathEdit)

        // Dry Run
        dryRunCheck = CheckBox(context).apply {
            text = "Perform Dry Run (Simulate)"
            isChecked = true
            setTextColor(Color.YELLOW)
        }
        configLayout.addView(dryRunCheck)

        configGroup.setContent(configLayout)
        content.addView(configGroup)

        // 2. Behavior Group
        val behaviorGroup = OptionalField(context).apply { setTitle("Sync Behavior") }
        val behaviorLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }

        behaviorLayout.addView(createLabel(context, "Local Orphans Action:", Color.CYAN))
        val localGroup = RadioGroup(context).apply { orientation = RadioGroup.HORIZONTAL }
        localGroup.addView(RadioButton(context).apply { text = "Upload"; isChecked = true; setTextColor(Color.WHITE) })
        localGroup.addView(RadioButton(context).apply { text = "Delete Local"; setTextColor(Color.RED) })
        localGroup.addView(RadioButton(context).apply { text = "Ignore"; setTextColor(Color.GRAY) })
        behaviorLayout.addView(localGroup)

        behaviorLayout.addView(createLabel(context, "Remote Orphans Action:", Color.GREEN))
        val remoteGroup = RadioGroup(context).apply { orientation = RadioGroup.HORIZONTAL }
        remoteGroup.addView(RadioButton(context).apply { text = "Download"; isChecked = true; setTextColor(Color.WHITE) })
        remoteGroup.addView(RadioButton(context).apply { text = "Delete Remote"; setTextColor(Color.RED) })
        remoteGroup.addView(RadioButton(context).apply { text = "Ignore"; setTextColor(Color.GRAY) })
        behaviorLayout.addView(remoteGroup)

        behaviorGroup.setContent(behaviorLayout)
        content.addView(behaviorGroup)

        // 3. Action
        btnSync = Button(context).apply {
            text = "Run Synchronization Now"
            setBackgroundColor(Color.parseColor("#27ae60")) // Green
            setOnClickListener { runSync() }
        }
        content.addView(btnSync)

        // Log Area
        statusLog = TextView(context).apply {
            text = "Ready."
            setTextColor(Color.LTGRAY)
            setPadding(0, 16, 0, 0)
        }
        content.addView(statusLog)

        scrollView.addView(content)
        return scrollView
    }

    private fun createLabel(context: Context, text: String, color: Int = Color.WHITE): TextView {
        return TextView(context).apply {
            this.text = text
            setTextColor(color)
            setPadding(0, 8, 0, 8)
        }
    }

    private fun runSync() {
        val provider = providerSpinner.selectedItem.toString()
        val isDry = dryRunCheck.isChecked
        val mode = if (isDry) "DRY RUN" else "LIVE"
        
        statusLog.text = "Starting $mode sync with $provider...\nScanning local...\nScanning remote...\nDone."
        // In real app, launch Coroutine Worker here
    }
}