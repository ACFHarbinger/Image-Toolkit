package com.personal.image_toolkit.ui.tabs

import android.content.Context
import android.graphics.Color
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.GridLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.VideoView
import com.personal.image_toolkit.ui.ClickableItemView
import com.personal.image_toolkit.ui.MarqueeSelectionLayout
import com.personal.image_toolkit.ui.OptionalField

/**
 * Android implementation of ImageExtractorTab.
 * Features a Source Gallery (top), Video Player, and Results Gallery (bottom/base).
 */
class ImageExtractorFragment : BaseSingleGalleryFragment() {

    private lateinit var sourcePathEdit: EditText
    private lateinit var outputDirEdit: EditText
    private lateinit var sourceGalleryContainer: GridLayout
    private lateinit var videoView: VideoView
    private lateinit var btnSnapshot: Button
    private lateinit var btnExtractRange: Button

    override fun createSpecificContent(context: Context): View {
        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            // padding removed to let children handle it or match parent
        }

        // 1. Source Directory Input
        val sourceGroup = createSection(context, "Source Directory")
        sourcePathEdit = EditText(context).apply { hint = "Select folder with videos..." }
        val btnBrowse = Button(context).apply {
            text = "Browse"
            setOnClickListener { scanSourceDirectory(sourcePathEdit.text.toString()) }
        }
        val sourceRow = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(sourcePathEdit, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            addView(btnBrowse)
        }
        sourceGroup.setContent(sourceRow)
        container.addView(sourceGroup)

        // 2. Source Gallery (Available Media)
        // This corresponds to self.source_scroll in Python
        val sourceGalleryLabel = TextView(context).apply {
            text = "Available Media"
            setTextColor(Color.LTGRAY)
            setPadding(16, 8, 16, 0)
        }
        container.addView(sourceGalleryLabel)

        val sourceScroll = ScrollView(context).apply {
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 300) // Fixed height like Python
        }
        sourceGalleryContainer = GridLayout(context).apply {
            columnCount = 4
        }
        sourceScroll.addView(sourceGalleryContainer)
        container.addView(sourceScroll)

        // 3. Video Player
        val playerGroup = createSection(context, "Video Player")
        val playerContainer = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.BLACK)
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 500)
        }
        
        videoView = VideoView(context).apply {
            // In a real app, you'd need MediaController here
        }
        playerContainer.addView(videoView, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.MATCH_PARENT))
        playerGroup.setContent(playerContainer)
        container.addView(playerGroup)

        // 4. Extraction Controls
        val extractGroup = createSection(context, "Extraction Settings")
        val controlsLayout = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        
        btnSnapshot = Button(context).apply {
            text = "Snapshot Frame"
            setOnClickListener { extractSnapshot() }
        }
        btnExtractRange = Button(context).apply {
            text = "Extract Range"
            isEnabled = false // Logic would enable this
        }
        
        controlsLayout.addView(btnSnapshot)
        controlsLayout.addView(btnExtractRange)
        extractGroup.setContent(controlsLayout)
        container.addView(extractGroup)

        return container
    }

    override fun createCardView(context: Context, path: String): View {
        // This handles the "Results" gallery items (bottom)
        return ClickableItemView(context).apply {
            filePath = path
            // Styling for extracted frames
            setBackgroundColor(Color.parseColor("#2c2f33"))
        }
    }

    private fun createSection(context: Context, title: String): OptionalField {
        return OptionalField(context).apply {
            setTitle(title)
            // OptionalField in Android impl is collapsible
        }
    }

    // --- Mock Logic ---

    private fun scanSourceDirectory(path: String) {
        sourceGalleryContainer.removeAllViews()
        // Mock finding videos
        for (i in 1..5) {
            val vidPath = "$path/video_$i.mp4"
            val card = ClickableItemView(requireContext()).apply {
                filePath = vidPath
                text = "VIDEO $i" // Simplified since we can't gen thumbnails easily in mock
                setBackgroundColor(Color.parseColor("#34495e"))
                onPathClicked = { p -> loadVideo(p) }
            }
            val params = GridLayout.LayoutParams().apply {
                width = 200
                height = 200
                setMargins(4, 4, 4, 4)
            }
            card.layoutParams = params
            sourceGalleryContainer.addView(card)
        }
    }

    private fun loadVideo(path: String) {
        // In real app: videoView.setVideoPath(path); videoView.start()
        statusLabel.text = "Loaded video: $path"
    }

    private fun extractSnapshot() {
        // Mock extraction
        val newFrame = "/storage/emulated/0/Pictures/Extracted/frame_${System.currentTimeMillis()}.png"
        galleryItems.add(0, newFrame) // Add to results
        refreshGallery()
        statusLabel.text = "Extracted frame."
    }
}