package com.personal.image_toolkit.ui

import android.content.Context
import android.graphics.Color
import android.util.AttributeSet
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.view.setPadding

/**
 * Equivalent to OptionalField.
 * A collapsible section with a header ("+" button and title) and content.
 */
class OptionalField @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : LinearLayout(context, attrs) {

    private val headerLayout: LinearLayout
    private val toggleButton: TextView
    private val titleLabel: TextView
    private var contentContainer: LinearLayout // Container for the inner widget

    private var isExpanded = false

    init {
        orientation = VERTICAL
        
        // 1. Header Row
        headerLayout = LinearLayout(context).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(16)
            setBackgroundColor(Color.parseColor("#F0F0F0")) // Light background
        }

        toggleButton = TextView(context).apply {
            text = "+"
            textSize = 18f
            setPadding(0, 0, 16, 0)
            setTextColor(Color.BLACK)
        }

        titleLabel = TextView(context).apply {
            text = "Optional Field"
            textSize = 14f
            setTextColor(Color.BLACK)
            layoutParams = LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f)
        }

        headerLayout.addView(toggleButton)
        headerLayout.addView(titleLabel)
        
        // 2. Content Container
        contentContainer = LinearLayout(context).apply {
            orientation = VERTICAL
            visibility = View.GONE
        }

        addView(headerLayout)
        addView(contentContainer)

        // Toggle logic
        headerLayout.setOnClickListener {
            toggle()
        }
    }

    fun setTitle(title: String) {
        titleLabel.text = title
    }

    fun setContent(view: View) {
        contentContainer.removeAllViews()
        contentContainer.addView(view)
    }

    private fun toggle() {
        isExpanded = !isExpanded
        contentContainer.visibility = if (isExpanded) View.VISIBLE else View.GONE
        toggleButton.text = if (isExpanded) "-" else "+"
    }
}