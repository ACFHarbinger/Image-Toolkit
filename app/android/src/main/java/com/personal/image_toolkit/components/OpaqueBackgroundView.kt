package com.personal.image_toolkit.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View

/**
 * Equivalent to OpaqueViewport.
 * A custom View that explicitly paints its background color to ensure opacity,
 * preventing rendering artifacts (similar to Qt's WA_OpaquePaintEvent in a Viewport).
 */
class OpaqueBackgroundView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private val backgroundPaint = Paint()
    
    // Default background color mimicking the PySide example
    private var backgroundColorInt = Color.parseColor("#2c2f33")

    init {
        // Set the initial paint color
        backgroundPaint.color = backgroundColorInt
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        
        // Explicitly fill the entire canvas rectangle with the background color.
        // This is the core equivalent of QWidget.WA_OpaquePaintEvent + paintEvent implementation.
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), backgroundPaint)
    }
    
    /**
     * Allows dynamic changing of the background color if needed.
     */
    fun setOpaqueBackgroundColor(colorHex: String) {
        backgroundColorInt = Color.parseColor(colorHex)
        backgroundPaint.color = backgroundColorInt
        invalidate() // Request a redraw
    }
}