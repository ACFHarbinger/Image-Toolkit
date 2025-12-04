package com.personal.image_toolkit.ui.windows

import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.google.android.material.bottomsheet.BottomSheetDialogFragment

/**
 * Android implementation of LogWindow.
 * Implemented as a BottomSheet for non-intrusive logging.
 */
class LogFragment : BottomSheetDialogFragment() {

    private lateinit var logTextView: TextView
    private val logBuffer = StringBuilder()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        val context = requireContext()
        val layout = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16, 16, 16, 16)
            setBackgroundColor(Color.parseColor("#1e1e1e"))
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 600) // Fixed height
        }

        // Header
        val headerLayout = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        val title = TextView(context).apply {
            text = "System Log"
            setTextColor(Color.WHITE)
            textSize = 16f
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        }
        val btnClear = Button(context).apply {
            text = "Clear"
            setOnClickListener { clearLog() }
        }
        headerLayout.addView(title)
        headerLayout.addView(btnClear)
        layout.addView(headerLayout)

        // Log Content
        val scrollView = ScrollView(context).apply {
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        }
        
        logTextView = TextView(context).apply {
            setTextColor(Color.parseColor("#b9bbbe"))
            typeface = android.graphics.Typeface.MONOSPACE
            text = logBuffer.toString()
        }
        
        scrollView.addView(logTextView)
        layout.addView(scrollView)

        return layout
    }

    fun appendLog(message: String) {
        logBuffer.append(message).append("\n")
        if (::logTextView.isInitialized) {
            logTextView.text = logBuffer.toString()
        }
    }

    fun clearLog() {
        logBuffer.clear()
        if (::logTextView.isInitialized) {
            logTextView.text = ""
        }
    }
}