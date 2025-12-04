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
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.widget.AppCompatSpinner
import androidx.core.view.setPadding
import androidx.fragment.app.Fragment
import com.personal.image_toolkit.ui.OptionalField

class WebRequestsFragment : Fragment() {

    private lateinit var urlEdit: EditText
    private lateinit var reqTypeSpinner: AppCompatSpinner
    private lateinit var reqParamEdit: EditText
    private lateinit var requestListLayout: LinearLayout
    private lateinit var actionListLayout: LinearLayout
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

        // 1. Config
        val configGroup = OptionalField(context).apply { setTitle("Request Configuration") }
        urlEdit = EditText(context).apply { hint = "Base URL (e.g. https://api.example.com)..." }
        configGroup.setContent(urlEdit)
        content.addView(configGroup)

        // 2. Request Builder
        val reqGroup = OptionalField(context).apply { setTitle("1. Request List") }
        val reqContainer = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        
        val reqRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        reqTypeSpinner = AppCompatSpinner(context).apply {
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, arrayOf("GET", "POST"))
        }
        reqParamEdit = EditText(context).apply { hint = "Params / Data" }
        val btnAddReq = Button(context).apply {
            text = "Add"
            setOnClickListener { addRequestItem(context) }
        }
        
        reqRow.addView(reqTypeSpinner)
        reqRow.addView(reqParamEdit, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        reqRow.addView(btnAddReq)
        reqContainer.addView(reqRow)

        requestListLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL; setPadding(0, 10, 0, 0) }
        reqContainer.addView(requestListLayout)
        
        reqGroup.setContent(reqContainer)
        content.addView(reqGroup)

        // 3. Action Builder
        val actionGroup = OptionalField(context).apply { setTitle("2. Response Actions") }
        val actContainer = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        actionListLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        
        val btnAddAction = Button(context).apply { 
            text = "Add 'Print Status' Action"
            setOnClickListener { addActionItem(context, "Print Response Status Code") }
        }
        actContainer.addView(btnAddAction)
        actContainer.addView(actionListLayout)
        
        actionGroup.setContent(actContainer)
        content.addView(actionGroup)

        // 4. Run
        val btnRun = Button(context).apply {
            text = "Run Requests"
            setBackgroundColor(Color.parseColor("#8e44ad"))
            setOnClickListener { startRequests() }
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

    private fun addRequestItem(context: Context) {
        val type = reqTypeSpinner.selectedItem.toString()
        val param = reqParamEdit.text.toString()
        val view = TextView(context).apply {
            text = "[$type] $param"
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.parseColor("#36393f"))
            setPadding(10, 10, 10, 10)
        }
        requestListLayout.addView(view)
        reqParamEdit.text.clear()
    }

    private fun addActionItem(context: Context, text: String) {
        val view = TextView(context).apply {
            this.text = "• $text"
            setTextColor(Color.LTGRAY)
            setPadding(10, 5, 0, 5)
        }
        actionListLayout.addView(view)
    }

    private fun startRequests() {
        if (urlEdit.text.isEmpty()) {
            statusLabel.text = "Error: Missing Base URL"
            return
        }
        statusLabel.text = "Running ${requestListLayout.childCount} requests..."
        // Worker logic would go here
    }
}