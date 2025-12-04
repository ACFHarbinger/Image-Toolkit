package com.personal.image_toolkit.ui.tabs

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.media.MediaMetadataRetriever
import android.os.Bundle
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.GridLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.fragment.app.Fragment
import com.personal.image_toolkit.ui.MarqueeSelectionLayout
import com.personal.image_toolkit.ui.PaginationControl
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Kotlin implementation of AbstractClassSingleGallery.
 * Provides a structure with a custom top content area and a single paginated gallery at the bottom.
 */
abstract class BaseSingleGalleryFragment : Fragment() {

    // Data State
    protected val galleryItems = mutableListOf<String>()
    protected val selectedItems = mutableListOf<String>()
    
    // Pagination State
    protected var pageSize = 100
    protected var currentPage = 0

    // UI References
    protected lateinit var mainLayout: LinearLayout
    protected lateinit var galleryContainer: GridLayout
    protected lateinit var paginationControl: PaginationControl
    protected lateinit var statusLabel: TextView
    
    private val thumbnailSize = 300 // px
    private var populationJob: Job? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        val context = requireContext()
        
        // Root Layout
        mainLayout = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            setBackgroundColor(Color.parseColor("#2c2f33"))
        }

        // 1. Specific Content (Top Area)
        val specificContent = createSpecificContent(context)
        if (specificContent != null) {
            mainLayout.addView(specificContent)
        }

        // 2. Gallery Area (Bottom Area)
        // Header
        val header = TextView(context).apply {
            text = "Gallery"
            setTextColor(Color.WHITE)
            textSize = 16f
            setPadding(16, 8, 16, 8)
            setBackgroundColor(Color.parseColor("#40444b"))
        }
        mainLayout.addView(header)

        // Scrollable Gallery
        val scrollView = ScrollView(context).apply {
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
            isFillViewport = true
        }

        val marqueeLayout = MarqueeSelectionLayout(context).apply {
            onSelectionChanged = { paths -> handleSelection(paths) }
        }

        galleryContainer = GridLayout(context).apply {
            columnCount = 3
            alignmentMode = GridLayout.ALIGN_BOUNDS
        }

        marqueeLayout.addView(galleryContainer)
        scrollView.addView(marqueeLayout)
        mainLayout.addView(scrollView)

        // 3. Pagination
        paginationControl = PaginationControl(context).apply {
            onPageSizeChanged = { size ->
                pageSize = size
                currentPage = 0
                refreshGallery()
            }
            onPageChange = { delta ->
                currentPage += delta
                refreshGallery()
            }
        }
        mainLayout.addView(paginationControl)

        // 4. Status
        statusLabel = TextView(context).apply {
            text = "Ready."
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER
            setPadding(16, 16, 16, 16)
        }
        mainLayout.addView(statusLabel)

        return mainLayout
    }

    /**
     * Subclasses must implement this to add their specific UI controls above the gallery.
     */
    abstract fun createSpecificContent(context: Context): View?

    /**
     * Subclasses must implement this to create the card view for a gallery item.
     */
    abstract fun createCardView(context: Context, path: String): View

    // --- Core Logic ---

    protected fun refreshGallery() {
        populationJob?.cancel()
        galleryContainer.removeAllViews()

        currentPage = paginationControl.updateState(galleryItems.size, currentPage, pageSize)
        
        val startIndex = currentPage * pageSize
        val endIndex = (startIndex + pageSize).coerceAtMost(galleryItems.size)
        
        if (startIndex >= galleryItems.size) return

        val slice = galleryItems.subList(startIndex, endIndex)

        populationJob = CoroutineScope(Dispatchers.Main).launch {
            statusLabel.text = "Showing ${slice.size} items (Total: ${galleryItems.size})"
            
            slice.forEach { path ->
                val card = createCardView(requireContext(), path)
                
                val params = GridLayout.LayoutParams().apply {
                    width = thumbnailSize
                    height = thumbnailSize + 50
                    setMargins(8, 8, 8, 8)
                }
                card.layoutParams = params
                galleryContainer.addView(card)
                
                // Simulate sequential loading
                withContext(Dispatchers.IO) { Thread.sleep(5) }
            }
        }
    }

    private fun handleSelection(paths: Set<String>) {
        selectedItems.clear()
        selectedItems.addAll(paths)
        statusLabel.text = "${selectedItems.size} items selected."
    }

    /**
     * Helper to generate video thumbnails using Android's MediaMetadataRetriever.
     * Equivalent to the OpenCV logic in Python.
     */
    protected fun generateVideoThumbnail(path: String): Bitmap? {
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(path)
            // Retrieve frame at 1 second (1000000 microseconds)
            retriever.getFrameAtTime(1000000, MediaMetadataRetriever.OPTION_CLOSEST_SYNC)
        } catch (e: Exception) {
            e.printStackTrace()
            null
        } finally {
            retriever.release()
        }
    }
}