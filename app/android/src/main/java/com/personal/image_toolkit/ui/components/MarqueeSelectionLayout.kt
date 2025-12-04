package com.personal.image_toolkit.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.core.view.children

/**
 * Equivalent to MarqueeScrollArea.
 * A Layout that intercepts touch events to draw a selection rectangle.
 * It does not scroll itself (use a ScrollView as parent or child), but handles the selection logic.
 */
class MarqueeSelectionLayout @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : FrameLayout(context, attrs) {

    private val selectionPaint = Paint().apply {
        color = Color.parseColor("#3498db")
        style = Paint.Style.STROKE
        strokeWidth = 3f
        alpha = 200
    }
    
    private val fillPaint = Paint().apply {
        color = Color.parseColor("#3498db")
        style = Paint.Style.FILL
        alpha = 50
    }

    private var startX = 0f
    private var startY = 0f
    private var currentX = 0f
    private var currentY = 0f
    private var isSelecting = false
    
    // Callback: Returns a set of file paths found in selected DraggableItemViews
    var onSelectionChanged: ((Set<String>) -> Unit)? = null

    init {
        setWillNotDraw(false) // Enable onDraw for ViewGroup
    }

    override fun onInterceptTouchEvent(ev: MotionEvent): Boolean {
        // If the user touches a DraggableItemView directly, don't intercept (let them click/drag)
        // If they touch empty space, intercept to start marquee
        if (ev.action == MotionEvent.ACTION_DOWN) {
            val touchedView = findViewAtPosition(this, ev.rawX.toInt(), ev.rawY.toInt())
            if (touchedView is DraggableItemView) {
                return false
            }
            // Start selection
            startX = ev.x
            startY = ev.y
            currentX = startX
            currentY = startY
            isSelecting = true
            invalidate()
            return true
        }
        return super.onInterceptTouchEvent(ev)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (!isSelecting) return super.onTouchEvent(event)

        when (event.action) {
            MotionEvent.ACTION_MOVE -> {
                currentX = event.x
                currentY = event.y
                invalidate()
                checkSelection()
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                isSelecting = false
                invalidate()
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (isSelecting) {
            val left = startX.coerceAtMost(currentX)
            val top = startY.coerceAtMost(currentY)
            val right = startX.coerceAtLeast(currentX)
            val bottom = startY.coerceAtLeast(currentY)
            
            val rect = Rect(left.toInt(), top.toInt(), right.toInt(), bottom.toInt())
            canvas.drawRect(rect, fillPaint)
            canvas.drawRect(rect, selectionPaint)
        }
    }

    /**
     * Helper to find a child view at specific screen coordinates recursively
     */
    private fun findViewAtPosition(parent: ViewGroup, x: Int, y: Int): View? {
        val count = parent.childCount
        for (i in 0 until count) {
            val child = parent.getChildAt(i)
            val loc = IntArray(2)
            child.getLocationOnScreen(loc)
            val rect = Rect(loc[0], loc[1], loc[0] + child.width, loc[1] + child.height)
            if (rect.contains(x, y)) {
                if (child is ViewGroup) {
                    val nested = findViewAtPosition(child, x, y)
                    if (nested != null) return nested
                }
                return child
            }
        }
        return null
    }

    private fun checkSelection() {
        val selectionRect = Rect(
            startX.coerceAtMost(currentX).toInt(),
            startY.coerceAtMost(currentY).toInt(),
            startX.coerceAtLeast(currentX).toInt(),
            startY.coerceAtLeast(currentY).toInt()
        )

        val selectedPaths = mutableSetOf<String>()
        findSelectedItems(this, selectionRect, selectedPaths)
        
        onSelectionChanged?.invoke(selectedPaths)
    }

    private fun findSelectedItems(parent: ViewGroup, selectionRect: Rect, result: MutableSet<String>) {
        for (child in parent.children) {
            if (child is DraggableItemView) {
                val loc = IntArray(2)
                child.getLocationInWindow(loc)
                // Need to convert selectionRect to window coordinates or child to local
                // Simplified: assuming simple layout structure. 
                // For robust implementation, use getLocationOnScreen for both.
                
                // Using View's hit rect relative to this container
                val childRect = Rect()
                child.getHitRect(childRect) // relative to parent
                
                // Basic intersection check
                if (Rect.intersects(selectionRect, childRect)) {
                    child.filePath?.let { result.add(it) }
                }
            } else if (child is ViewGroup) {
                findSelectedItems(child, selectionRect, result)
            }
        }
    }
}