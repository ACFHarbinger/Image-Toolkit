package com.personal.image_toolkit.ui

import android.content.Context
import android.graphics.Color
import android.util.AttributeSet
import android.view.Gravity
import androidx.appcompat.widget.AppCompatTextView
import java.io.File

/**
 * Equivalent to ClickableLabel.
 * A TextView that handles single click, double click, and long press (for context menu).
 */
class ClickableItemView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : AppCompatTextView(context, attrs, defStyleAttr) {

    var filePath: String? = null
        set(value) {
            field = value // Updates the internal backing field

            // Perform the UI updates immediately when the property is set
            if (value != null) {
                text = File(value).name
                contentDescription = value
            } else {
                text = ""
                contentDescription = null
            }
        }
    var onPathClicked: ((String) -> Unit)? = null
    var onPathDoubleClicked: ((String) -> Unit)? = null
    // Android uses OnLongClickListener for context menu/right-click equivalent
    var onPathRightClicked: ((String) -> Unit)? = null 

    private var lastClickTime: Long = 0
    private val doubleClickThreshold = 300L // Standard Android double-click delay

    init {
        isClickable = true
        isFocusable = true
        gravity = Gravity.CENTER
        
        // Default styling (mimicking the PySide style)
        setBackgroundColor(Color.parseColor("#2c2f33"))
        setTextColor(Color.parseColor("#b9bbbe"))
        setPadding(10, 10, 10, 10)
        
        // Handle single and double click detection
        setOnClickListener {
            val currentClickTime = System.currentTimeMillis()
            if (currentClickTime - lastClickTime < doubleClickThreshold) {
                // Double click occurred
                filePath?.let { path -> onPathDoubleClicked?.invoke(path) }
                lastClickTime = 0 // Reset to prevent triple-click misfires
            } else {
                // Single click recorded
                filePath?.let { path -> onPathClicked?.invoke(path) }
                lastClickTime = currentClickTime
            }
        }

        // Handle right-click equivalent (long press)
        setOnLongClickListener {
            filePath?.let { path -> 
                onPathRightClicked?.invoke(path) 
            }
            true // Consume the event
        }
    }
}