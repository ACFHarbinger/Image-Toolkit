package com.personal.image_toolkit.ui

import android.content.ClipDescription
import android.content.Context
import android.graphics.Color
import android.util.AttributeSet
import android.view.DragEvent
import android.view.Gravity
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.TextView
import java.io.File

/**
 * Equivalent to MonitorDropWidget.
 * Acts as a drop target for DraggableItemView or external files.
 */
class MonitorDropTarget @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : FrameLayout(context, attrs) {

    var monitorId: String = ""
    var onImageDropped: ((monitorId: String, path: String) -> Unit)? = null

    private val label: TextView
    private val imageView: ImageView
    private val defaultText = "Drop Image Here"

    init {
        // Setup internal image view (for preview)
        imageView = ImageView(context).apply {
            layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT)
            scaleType = ImageView.ScaleType.CENTER_CROP
            alpha = 0.5f // Dim slightly so text is visible
        }
        
        // Setup internal label (for monitor info)
        label = TextView(context).apply {
            layoutParams = LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT).apply {
                gravity = Gravity.CENTER
            }
            text = defaultText
            setTextColor(Color.WHITE)
            textSize = 14f
            textAlignment = TEXT_ALIGNMENT_CENTER
        }

        addView(imageView)
        addView(label)

        // Background styling
        setBackgroundColor(Color.parseColor("#36393f"))
        // Note: Real apps should use a Drawable for borders
        // setBackgroundResource(R.drawable.dashed_border)

        // Enable Drag Events
        setOnDragListener { view, event ->
            when (event.action) {
                DragEvent.ACTION_DRAG_STARTED -> {
                    // Check if the dragged data is text (file path)
                    event.clipDescription.hasMimeType(ClipDescription.MIMETYPE_TEXT_PLAIN)
                }
                DragEvent.ACTION_DRAG_ENTERED -> {
                    view.alpha = 0.7f // Visual feedback
                    true
                }
                DragEvent.ACTION_DRAG_EXITED -> {
                    view.alpha = 1.0f
                    true
                }
                DragEvent.ACTION_DROP -> {
                    view.alpha = 1.0f
                    val item = event.clipData.getItemAt(0)
                    val droppedPath = item.text.toString()
                    handleDrop(droppedPath)
                    true
                }
                DragEvent.ACTION_DRAG_ENDED -> {
                    view.alpha = 1.0f
                    true
                }
                else -> false
            }
        }
    }

    private fun handleDrop(path: String) {
        label.text = "Monitor $monitorId\n${File(path).name}"
        // In a real app, load image: Glide.with(context).load(path).into(imageView)
        onImageDropped?.invoke(monitorId, path)
    }
    
    fun clear() {
        imageView.setImageDrawable(null)
        label.text = defaultText
    }
}