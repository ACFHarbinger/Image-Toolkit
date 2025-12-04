package com.personal.image_toolkit.ui

import android.content.ClipData
import android.content.ClipDescription
import android.content.Context
import android.graphics.Color
import android.util.AttributeSet
import android.view.Gravity
import android.view.View
import androidx.appcompat.widget.AppCompatTextView

/**
 * Equivalent to ClickableLabel and DraggableLabel.
 * Handles click events and initiates Drag and Drop on long press.
 */
class DraggableItemView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : AppCompatTextView(context, attrs, defStyleAttr) {

    var filePath: String? = null
    var onPathClicked: ((String) -> Unit)? = null
    var onPathDoubleClicked: ((String) -> Unit)? = null
    var onPathLongClicked: ((String) -> Unit)? = null

    private var lastClickTime: Long = 0
    private val doubleClickThreshold = 300L

    init {
        isClickable = true
        isFocusable = true
        gravity = Gravity.CENTER
        
        // Default styling (mimicking the Python dashed border look)
        setBackgroundColor(Color.parseColor("#2c2f33"))
        setTextColor(Color.parseColor("#b9bbbe"))
        setPadding(10, 10, 10, 10)
        
        setOnClickListener {
            val currentClickTime = System.currentTimeMillis()
            if (currentClickTime - lastClickTime < doubleClickThreshold) {
                filePath?.let { path -> onPathDoubleClicked?.invoke(path) }
            } else {
                filePath?.let { path -> onPathClicked?.invoke(path) }
            }
            lastClickTime = currentClickTime
        }

        setOnLongClickListener {
            startDragOperation()
            onPathLongClicked?.invoke(filePath ?: "")
            true
        }
    }

    private fun startDragOperation() {
        val path = filePath ?: return
        
        // Create ClipData with the file path
        val item = ClipData.Item(path)
        val mimeTypes = arrayOf(ClipDescription.MIMETYPE_TEXT_PLAIN)
        val dragData = ClipData("FILE_PATH", mimeTypes, item)

        // Create a visual drag shadow
        val shadowBuilder = View.DragShadowBuilder(this)

        // Start drag (flag 0 is standard, GLOBAL allow dragging between apps)
        startDragAndDrop(dragData, shadowBuilder, this, 0)
    }
}