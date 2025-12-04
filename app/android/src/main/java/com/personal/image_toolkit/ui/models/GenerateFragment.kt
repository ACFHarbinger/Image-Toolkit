package com.personal.image_toolkit.ui.tabs

import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.GridLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.widget.AppCompatSpinner
import androidx.core.view.setPadding
import com.personal.image_toolkit.ui.OptionalField

/**
 * Android implementation of UnifiedGenerateTab.
 * Handles sub-tabs: LoRA Gen, SD3 Gen, R3GAN Gen, Basic GAN Gen.
 */
class GenerateFragment : BaseGenerativeFragment() {

    private lateinit var contentContainer: LinearLayout
    private lateinit var modelSelector: AppCompatSpinner
    private lateinit var resultsGrid: GridLayout
    private lateinit var statusLabel: TextView

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        val context = requireContext()
        val scrollView = ScrollView(context).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(Color.parseColor("#2c2f33"))
        }

        val mainLayout = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16)
        }

        // 1. Selector
        val selectorRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        val lblSelector = TextView(context).apply {
            text = "Model Architecture: "
            setTextColor(Color.WHITE)
            textSize = 16f
        }
        modelSelector = AppCompatSpinner(context).apply {
            val items = arrayOf("LoRA (Diffusion)", "Stable Diffusion 3.5", "R3GAN", "Basic GAN")
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, items)
            onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
                override fun onItemSelected(p0: AdapterView<*>?, p1: View?, position: Int, p3: Long) {
                    updateContent(position)
                }
                override fun onNothingSelected(p0: AdapterView<*>?) {}
            }
        }
        selectorRow.addView(lblSelector)
        selectorRow.addView(modelSelector, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        mainLayout.addView(selectorRow)

        // Separator
        mainLayout.addView(View(context).apply {
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 2)
            setBackgroundColor(Color.DKGRAY)
            // Fix: Use setMargins on LayoutParams object
            (layoutParams as ViewGroup.MarginLayoutParams).setMargins(0, 16, 0, 16)
        })

        // 2. Dynamic Settings
        contentContainer = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        mainLayout.addView(contentContainer)

        // 3. Results Area
        val resGroup = OptionalField(context).apply { setTitle("Generated Results") }
        resultsGrid = GridLayout(context).apply { columnCount = 2 }
        resGroup.setContent(resultsGrid)

        mainLayout.addView(resGroup)

        // Status
        statusLabel = TextView(context).apply {
            text = "Ready."
            setTextColor(Color.LTGRAY)
            gravity = android.view.Gravity.CENTER
            setPadding(0, 16, 0, 0)
        }
        mainLayout.addView(statusLabel)

        scrollView.addView(mainLayout)
        return scrollView
    }

    private fun updateContent(index: Int) {
        contentContainer.removeAllViews()
        formWidgets.clear()

        when (index) {
            0 -> setupLoRAGenUI(requireContext())
            1 -> setupSD3UI(requireContext())
            2 -> setupR3GANUI(requireContext())
            3 -> setupGANUI(requireContext())
        }
    }

    // --- SUB-TAB: LoRA Generate ---
    private fun setupLoRAGenUI(context: Context) {
        val models = arrayOf("Illustrious XL V2.0", "Animagine XL 3.1", "AnimeGANv2")
        addParamWidget(context, contentContainer, "Select Model:", createSpinner(context, models), "model_id")

        val diffGroup = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        addParamWidget(context, diffGroup, "Prompt:", createEditText(context, "1girl, solo..."), "prompt")
        addParamWidget(context, diffGroup, "Neg. Prompt:", createEditText(context, "lowres, bad anatomy"), "neg_prompt")
        addParamWidget(context, diffGroup, "LoRA Path:", createEditText(context, "output_lora"), "lora_path")

        addParamWidget(context, diffGroup, "Steps:", createEditText(context, "25", "25"), "steps")
        addParamWidget(context, diffGroup, "Guidance:", createEditText(context, "7.0", "7.0"), "cfg")

        contentContainer.addView(diffGroup)

        val btnGen = createStyledButton(context, "Generate Image", "#2980b9")
        btnGen.setOnClickListener { mockGeneration() }
        contentContainer.addView(btnGen)
    }

    // --- SUB-TAB: SD3 Generate ---
    private fun setupSD3UI(context: Context) {
        val baseModels = arrayOf("sd3.5_large.safetensors", "sd3.5_medium.safetensors")
        addParamWidget(context, contentContainer, "Base Model:", createSpinner(context, baseModels), "sd3_model")

        addParamWidget(context, contentContainer, "Prompt:", createEditText(context, "cute cat"), "prompt")
        addParamWidget(context, contentContainer, "Width:", createEditText(context, "1024", "1024"), "width")
        addParamWidget(context, contentContainer, "Height:", createEditText(context, "1024", "1024"), "height")

        val cnModels = arrayOf("None", "canny.safetensors", "depth.safetensors")
        addParamWidget(context, contentContainer, "ControlNet:", createSpinner(context, cnModels), "cn_model")

        val btnGen = createStyledButton(context, "Generate SD3", "#d35400")
        btnGen.setOnClickListener { mockGeneration() }
        contentContainer.addView(btnGen)
    }

    // --- SUB-TAB: R3GAN Generate ---
    private fun setupR3GANUI(context: Context) {
        addParamWidget(context, contentContainer, "Network (.pkl):", createEditText(context, ""), "network")
        addParamWidget(context, contentContainer, "Seeds:", createEditText(context, "0-7"), "seeds")

        val btnGen = createStyledButton(context, "Generate R3GAN", "#8e44ad")
        btnGen.setOnClickListener { mockGeneration() }
        contentContainer.addView(btnGen)
    }

    // --- SUB-TAB: Basic GAN Generate ---
    private fun setupGANUI(context: Context) {
        val row = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        val editPath = createEditText(context, "Path to .pth checkpoint")
        val btnBrowse = Button(context).apply { text = "Browse" }
        row.addView(editPath, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        row.addView(btnBrowse)

        addParamWidget(context, contentContainer, "Checkpoint:", row, "ckpt")
        addParamWidget(context, contentContainer, "Count:", createEditText(context, "8", "8"), "count")

        val btnGen = createStyledButton(context, "Generate Images", "#27ae60")
        btnGen.setOnClickListener { mockGeneration() }
        contentContainer.addView(btnGen)
    }

    private fun mockGeneration() {
        statusLabel.text = "Generating..."
        resultsGrid.removeAllViews()

        // Convert DP to PX (8dp to px)
        val density = resources.displayMetrics.density
        val marginPx = (8 * density).toInt()

        // Mock Result
        for (i in 1..4) {
            val img = ImageView(requireContext()).apply {
                setBackgroundColor(Color.DKGRAY)
                scaleType = ImageView.ScaleType.CENTER_CROP
                layoutParams = GridLayout.LayoutParams().apply {
                    width = 300
                    height = 300
                    // Fix: Directly set margins properties
                    this.topMargin = marginPx
                    this.bottomMargin = marginPx
                    this.leftMargin = marginPx
                    this.rightMargin = marginPx
                }
            }
            resultsGrid.addView(img)
        }
        statusLabel.text = "Generation Complete."
    }
}