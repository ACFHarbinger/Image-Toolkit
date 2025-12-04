package com.personal.image_toolkit.ui.windows

import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.TextView
import androidx.fragment.app.DialogFragment
import java.io.File

/**
 * Android implementation of ImagePreviewWindow.
 * A full-screen dialog for viewing images/GIFs with navigation.
 */
class ImagePreviewFragment(
    private val initialPath: String,
    private val allPaths: List<String>
) : DialogFragment() {

    private var currentIndex = allPaths.indexOf(initialPath).coerceAtLeast(0)
    private lateinit var imageView: ImageView
    private lateinit var titleView: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setStyle(STYLE_NORMAL, android.R.style.Theme_Black_NoTitleBar_Fullscreen)
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        val context = requireContext()
        val layout = FrameLayout(context).apply {
            setBackgroundColor(Color.BLACK)
        }

        // Image Container (would use a ZoomableView/PhotoView library in prod)
        imageView = ImageView(context).apply {
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            scaleType = ImageView.ScaleType.FIT_CENTER
        }
        layout.addView(imageView)

        // Overlay UI
        val overlay = FrameLayout(context).apply {
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        // Close Button
        val btnClose = Button(context).apply {
            text = "✕"
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.TRANSPARENT)
            textSize = 20f
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, 
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = Gravity.TOP or Gravity.END
                setMargins(16, 16, 16, 16)
            }
            setOnClickListener { dismiss() }
        }
        overlay.addView(btnClose)

        // Navigation (Left)
        val btnPrev = Button(context).apply {
            text = "◀"
            textSize = 30f
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.parseColor("#44000000"))
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = Gravity.CENTER_VERTICAL or Gravity.START
            }
            setOnClickListener { navigate(-1) }
        }
        overlay.addView(btnPrev)

        // Navigation (Right)
        val btnNext = Button(context).apply {
            text = "▶"
            textSize = 30f
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.parseColor("#44000000"))
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = Gravity.CENTER_VERTICAL or Gravity.END
            }
            setOnClickListener { navigate(1) }
        }
        overlay.addView(btnNext)

        // Title
        titleView = TextView(context).apply {
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#88000000"))
            setPadding(16, 16, 16, 16)
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = Gravity.BOTTOM
            }
        }
        overlay.addView(titleView)

        layout.addView(overlay)
        
        loadImage()
        return layout
    }

    private fun navigate(direction: Int) {
        if (allPaths.isEmpty()) return
        currentIndex = (currentIndex + direction + allPaths.size) % allPaths.size
        loadImage()
    }

    private fun loadImage() {
        val path = allPaths[currentIndex]
        // Mock loading. Real app uses Glide/Coil
        titleView.text = "${File(path).name} (${currentIndex + 1}/${allPaths.size})"
        // imageView.setImageURI(Uri.fromFile(File(path))) 
        // For mock:
        imageView.setBackgroundColor(if (currentIndex % 2 == 0) Color.DKGRAY else Color.GRAY)
    }
}