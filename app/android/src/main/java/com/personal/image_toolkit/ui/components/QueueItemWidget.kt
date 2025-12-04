package com.personal.image_toolkit.ui

import android.content.Context
import android.graphics.Color
import android.util.AttributeSet
import android.view.Gravity
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import java.io.File

/**
 * Equivalent to QueueItemWidget.
 * A simple row displaying a thumbnail and a filename.
 */
class QueueItemWidget @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : LinearLayout(context, attrs) {

    private val imageView: ImageView
    private val nameLabel: TextView

    init {
        orientation = HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(10, 10, 10, 10)
        
        // Setup layout params
        val imageParams = LayoutParams(160, 120) // approx 80x60 dp * density
        imageParams.marginEnd = 16

        imageView = ImageView(context).apply {
            layoutParams = imageParams
            scaleType = ImageView.ScaleType.CENTER_CROP
            setBackgroundColor(Color.DKGRAY) // Placeholder
        }

        nameLabel = TextView(context).apply {
            layoutParams = LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f)
            setTextColor(Color.parseColor("#b9bbbe"))
            textSize = 12f
        }

        addView(imageView)
        addView(nameLabel)
    }

    fun setData(path: String) {
        val file = File(path)
        nameLabel.text = file.name
        nameLabel.contentDescription = path
        // Load image using Glide/Coil in real app
        // Glide.with(context).load(path).into(imageView)
    }
}