package com.personal.image_toolkit.ui.tabs

import android.content.Context
import android.graphics.Color
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

/**
 * Kotlin implementation of AbstractClassTwoGalleries + MetaAbstractClassGallery.
 * Provides the base UI structure for two galleries (Found & Selected), pagination, and selection logic.
 */
abstract class BaseTwoGalleriesFragment : Fragment() {

    // Data State
    protected val foundFiles = mutableListOf<String>()
    protected val selectedFiles = mutableListOf<String>()
    
    // Pagination State
    protected var foundPageSize = 100
    protected var foundCurrentPage = 0
    protected var selectedPageSize = 100
    protected var selectedCurrentPage = 0

    // UI References
    protected lateinit var mainLayout: LinearLayout
    protected lateinit var foundGalleryContainer: GridLayout
    protected lateinit var selectedGalleryContainer: GridLayout
    protected lateinit var foundPagination: PaginationControl
    protected lateinit var selectedPagination: PaginationControl
    protected lateinit var statusLabel: TextView
    
    private val thumbnailSize = 300 // px approx
    private var populationJob: Job? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        val context = requireContext()
        
        // Root Layout (Vertical)
        mainLayout = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            setBackgroundColor(Color.parseColor("#2c2f33")) // Dark theme background
        }

        // 1. Content Area (To be filled by subclasses)
        val contentContainer = createSpecificContent(context)
        mainLayout.addView(contentContainer)

        // 2. Found Gallery Area
        mainLayout.addView(createSectionHeader(context, "Found Images"))
        val foundScroll = ScrollView(context).apply {
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
            isFillViewport = true
        }
        
        // Marquee wrapper
        val foundMarquee = MarqueeSelectionLayout(context).apply {
            onSelectionChanged = { paths -> handleMarqueeSelection(paths) }
        }
        
        foundGalleryContainer = GridLayout(context).apply {
            columnCount = 3 // Default, will calculate dynamically in real app
            alignmentMode = GridLayout.ALIGN_BOUNDS
        }
        
        foundMarquee.addView(foundGalleryContainer)
        foundScroll.addView(foundMarquee)
        mainLayout.addView(foundScroll)

        // Found Pagination
        foundPagination = PaginationControl(context).apply {
            onPageSizeChanged = { size -> 
                foundPageSize = size
                foundCurrentPage = 0
                refreshFoundGallery()
            }
            onPageChange = { delta ->
                foundCurrentPage += delta
                refreshFoundGallery()
            }
        }
        mainLayout.addView(foundPagination)

        // 3. Selected Gallery Area
        mainLayout.addView(createSectionHeader(context, "Selected Images"))
        val selectedScroll = ScrollView(context).apply {
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
            isFillViewport = true
        }
        
        val selectedMarquee = MarqueeSelectionLayout(context) // No selection logic needed for bottom usually
        selectedGalleryContainer = GridLayout(context).apply {
            columnCount = 3
        }
        
        selectedMarquee.addView(selectedGalleryContainer)
        selectedScroll.addView(selectedMarquee)
        mainLayout.addView(selectedScroll)

        // Selected Pagination
        selectedPagination = PaginationControl(context).apply {
            onPageSizeChanged = { size ->
                selectedPageSize = size
                selectedCurrentPage = 0
                refreshSelectedGallery()
            }
            onPageChange = { delta ->
                selectedCurrentPage += delta
                refreshSelectedGallery()
            }
        }
        mainLayout.addView(selectedPagination)

        // Status Label
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
     * Abstract method for subclasses to inject their top-level controls (Inputs, Buttons).
     */
    abstract fun createSpecificContent(context: Context): View

    /**
     * Abstract method to create the card View for a specific file path.
     */
    abstract fun createCardView(context: Context, path: String, isSelected: Boolean): View

    /**
     * Abstract method called when selection changes.
     */
    abstract fun onSelectionChanged()

    // --- Core Logic ---

    protected fun refreshFoundGallery() {
        // Cancel any running population job
        populationJob?.cancel()
        
        foundGalleryContainer.removeAllViews()
        
        // Calculate pagination
        foundCurrentPage = foundPagination.updateState(foundFiles.size, foundCurrentPage, foundPageSize)
        
        val startIndex = foundCurrentPage * foundPageSize
        val endIndex = (startIndex + foundPageSize).coerceAtMost(foundFiles.size)
        val slice = foundFiles.subList(startIndex, endIndex)

        // Sequential loading using Coroutines
        populationJob = CoroutineScope(Dispatchers.Main).launch {
            statusLabel.text = "Showing ${foundFiles.size} items (Page ${foundCurrentPage + 1})"
            
            slice.forEach { path ->
                val isSelected = selectedFiles.contains(path)
                val card = createCardView(requireContext(), path, isSelected)
                
                // Add margins
                val params = GridLayout.LayoutParams().apply {
                    width = thumbnailSize
                    height = thumbnailSize + 50
                    setMargins(8, 8, 8, 8)
                }
                card.layoutParams = params
                
                foundGalleryContainer.addView(card)
                
                // Yield to main thread to allow UI updates (visualizing "one by one" loading)
                withContext(Dispatchers.IO) { Thread.sleep(10) } 
            }
        }
    }

    protected fun refreshSelectedGallery() {
        selectedGalleryContainer.removeAllViews()
        
        selectedCurrentPage = selectedPagination.updateState(selectedFiles.size, selectedCurrentPage, selectedPageSize)
        
        val startIndex = selectedCurrentPage * selectedPageSize
        val endIndex = (startIndex + selectedPageSize).coerceAtMost(selectedFiles.size)
        val slice = selectedFiles.subList(startIndex, endIndex)

        slice.forEach { path ->
            val card = createCardView(requireContext(), path, true)
             val params = GridLayout.LayoutParams().apply {
                width = thumbnailSize
                height = thumbnailSize + 50
                setMargins(8, 8, 8, 8)
            }
            card.layoutParams = params
            selectedGalleryContainer.addView(card)
        }
    }

    protected fun toggleSelection(path: String) {
        if (selectedFiles.contains(path)) {
            selectedFiles.remove(path)
        } else {
            selectedFiles.add(path)
        }
        refreshSelectedGallery()
        refreshFoundGallery() // To update borders
        onSelectionChanged()
    }

    private fun handleMarqueeSelection(paths: Set<String>) {
        // Simple logic: Additive selection for this demo
        var changed = false
        paths.forEach { path ->
            if (!selectedFiles.contains(path)) {
                selectedFiles.add(path)
                changed = true
            }
        }
        if (changed) {
            refreshSelectedGallery()
            refreshFoundGallery()
            onSelectionChanged()
        }
    }

    protected fun clearGalleries() {
        foundFiles.clear()
        selectedFiles.clear()
        foundCurrentPage = 0
        selectedCurrentPage = 0
        refreshFoundGallery()
        refreshSelectedGallery()
    }

    private fun createSectionHeader(context: Context, title: String): TextView {
        return TextView(context).apply {
            text = title
            setTextColor(Color.WHITE)
            textSize = 16f
            setPadding(16, 8, 16, 8)
            setBackgroundColor(Color.parseColor("#40444b"))
        }
    }
}