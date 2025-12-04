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
import androidx.fragment.app.DialogFragment
import com.personal.image_toolkit.ui.QueueItemWidget

/**
 * Android implementation of SlideshowQueueWindow.
 * Displays a list of queued items for a specific monitor.
 */
class SlideshowQueueFragment(
    private val monitorName: String,
    private val queue: MutableList<String>
) : DialogFragment() {

    private lateinit var listContainer: LinearLayout

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        val context = requireContext()
        val layout = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#2c2f33"))
            layoutParams = ViewGroup.LayoutParams(600, 800) // Desired dialog size
        }

        // Header
        val header = TextView(context).apply {
            text = "Queue for $monitorName"
            setTextColor(Color.WHITE)
            textSize = 18f
            setPadding(16, 16, 16, 16)
            setBackgroundColor(Color.parseColor("#23272a"))
        }
        layout.addView(header)

        // List
        val scrollView = ScrollView(context).apply {
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0, 1f
            )
        }
        
        listContainer = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(8, 8, 8, 8)
        }
        
        refreshList(context)
        
        scrollView.addView(listContainer)
        layout.addView(scrollView)

        // Footer
        val btnClose = Button(context).apply {
            text = "Close"
            setOnClickListener { dismiss() }
        }
        layout.addView(btnClose)

        return layout
    }

    private fun refreshList(context: Context) {
        listContainer.removeAllViews()
        if (queue.isEmpty()) {
            val empty = TextView(context).apply {
                text = "Queue is empty."
                setTextColor(Color.GRAY)
                setPadding(16, 16, 16, 16)
            }
            listContainer.addView(empty)
            return
        }

        queue.forEachIndexed { index, path ->
            val item = QueueItemWidget(context).apply {
                setData(path)
                // Add click listener to remove or move
                setOnClickListener { 
                    // Mock removal
                    queue.removeAt(index)
                    refreshList(context)
                }
            }
            listContainer.addView(item)
        }
    }
}