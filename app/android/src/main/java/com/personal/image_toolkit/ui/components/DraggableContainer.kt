package com.personal.image_toolkit.ui

import android.content.Context
import android.util.AttributeSet
import android.view.DragEvent
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout

/**
 * Equivalent to DraggableMonitorContainer.
 * A horizontal linear layout that allows reordering its children via Drag and Drop.
 */
class DraggableContainer @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : LinearLayout(context, attrs) {

    init {
        orientation = HORIZONTAL
        gravity = Gravity.CENTER
        setOnDragListener(ReorderDragListener())
    }

    /**
     * Custom DragListener to handle reordering logic.
     * Equivalent to dragMoveEvent and dropEvent in PySide6.
     */
    private inner class ReorderDragListener : OnDragListener {
        override fun onDrag(v: View, event: DragEvent): Boolean {
            when (event.action) {
                DragEvent.ACTION_DRAG_STARTED -> return true
                DragEvent.ACTION_DRAG_LOCATION -> {
                    // This creates the "live reordering" effect
                    val draggedView = event.localState as? View ?: return false
                    if (draggedView.parent != this@DraggableContainer) return false

                    val touchX = event.x
                    
                    // Find where we are dropping relative to other children
                    val count = childCount
                    var targetIndex = count - 1
                    
                    for (i in 0 until count) {
                        val child = getChildAt(i)
                        // center point of the child
                        val childCenter = child.x + (child.width / 2)
                        if (touchX < childCenter) {
                            targetIndex = i
                            break
                        }
                    }

                    val currentIndex = indexOfChild(draggedView)
                    // If position changed, move the view
                    if (currentIndex != targetIndex && targetIndex in 0 until count) {
                        removeView(draggedView)
                        addView(draggedView, targetIndex)
                    }
                    return true
                }
                DragEvent.ACTION_DROP -> {
                    // Drop accepted, layout updates are persistent
                    return true
                }
            }
            return true
        }
    }
}