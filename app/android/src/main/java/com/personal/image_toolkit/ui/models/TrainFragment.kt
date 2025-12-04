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
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.widget.AppCompatSpinner
import androidx.core.view.setPadding
import com.personal.image_toolkit.ui.OptionalField

/**
 * Android implementation of UnifiedTrainTab.
 * Handles sub-tabs: LoRA Train, R3GAN Train, and Basic GAN Train.
 */
class TrainFragment : BaseGenerativeFragment() {

    private lateinit var contentContainer: LinearLayout
    private lateinit var modelSelector: AppCompatSpinner
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

        // 1. Model Architecture Selector
        val selectorRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        val lblSelector = TextView(context).apply {
            text = "Model Architecture: "
            setTextColor(Color.WHITE)
            textSize = 16f
        }
        
        modelSelector = AppCompatSpinner(context).apply {
            val items = arrayOf("LoRA (Diffusion)", "R3GAN (NVLabs)", "Basic GAN (Custom)")
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
            setPadding(0, 16, 0, 16)
        })

        // 2. Dynamic Content Area
        contentContainer = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 16, 0, 0)
        }
        mainLayout.addView(contentContainer)

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
        formWidgets.clear() // Clear base class tracking

        when (index) {
            0 -> setupLoRAUI(requireContext())
            1 -> setupR3GANUI(requireContext())
            2 -> setupGANUI(requireContext())
        }
    }

    // --- SUB-TAB: LoRA Train ---
    private fun setupLoRAUI(context: Context) {
        // Model Selection
        val models = arrayOf("Illustrious XL V2.0", "Anything V5", "Animagine XL 3.1")
        addParamWidget(context, contentContainer, "Base Model:", createSpinner(context, models), "model_id")

        // Dataset
        val datasetLayout = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        val datasetEdit = createEditText(context, "Dataset Folder Path")
        val btnBrowse = Button(context).apply { text = "Browse" } // Mock browse
        
        datasetLayout.addView(datasetEdit, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        datasetLayout.addView(btnBrowse)
        addParamWidget(context, contentContainer, "Dataset:", datasetLayout, "dataset_path") // Only tracking layout won't work well with collect(), simplifying for UI demo

        addParamWidget(context, contentContainer, "Output Name:", createEditText(context, "my_model"), "output_name")

        // LoRA Group
        val loraGroup = OptionalField(context).apply { setTitle("LoRA Configuration") }
        val loraLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        addParamWidget(context, loraLayout, "Trigger Word:", createEditText(context, "1girl, style..."), "trigger")
        addParamWidget(context, loraLayout, "Rank:", createEditText(context, "4", "4"), "rank")
        loraGroup.setContent(loraLayout)
        contentContainer.addView(loraGroup)

        // Params
        addParamWidget(context, contentContainer, "Epochs:", createEditText(context, "5", "5"), "epochs")
        addParamWidget(context, contentContainer, "Batch Size:", createEditText(context, "1", "1"), "batch")
        addParamWidget(context, contentContainer, "Learning Rate:", createEditText(context, "0.0001", "0.0001"), "lr")

        val btnTrain = createStyledButton(context, "Start LoRA Training", "#2980b9")
        btnTrain.setOnClickListener { statusLabel.text = "Starting LoRA Training..." }
        contentContainer.addView(btnTrain)
    }

    // --- SUB-TAB: R3GAN Train ---
    private fun setupR3GANUI(context: Context) {
        addParamWidget(context, contentContainer, "Output Dir:", createEditText(context, "./training-runs"), "outdir")
        addParamWidget(context, contentContainer, "Dataset (.zip):", createEditText(context, ""), "dataset_zip")
        
        val presets = arrayOf("FFHQ-256", "FFHQ-64", "CIFAR10")
        addParamWidget(context, contentContainer, "Preset:", createSpinner(context, presets), "preset")
        
        addParamWidget(context, contentContainer, "GPUs:", createEditText(context, "8", "8"), "gpus")
        addParamWidget(context, contentContainer, "Mirror Data:", createCheckBox(context, ""), "mirror")
        
        val btnTrain = createStyledButton(context, "Start R3GAN Training", "#8e44ad")
        btnTrain.setOnClickListener { statusLabel.text = "Starting R3GAN Training..." }
        contentContainer.addView(btnTrain)
    }

    // --- SUB-TAB: Basic GAN Train ---
    private fun setupGANUI(context: Context) {
        addParamWidget(context, contentContainer, "Dataset Path:", createEditText(context, "/path/to/images"), "gan_data")
        addParamWidget(context, contentContainer, "Save Path:", createEditText(context, "./gan_checkpoints"), "gan_save")
        
        addParamWidget(context, contentContainer, "Epochs:", createEditText(context, "50", "50"), "gan_epochs")
        addParamWidget(context, contentContainer, "Batch Size:", createEditText(context, "64", "64"), "gan_batch")
        addParamWidget(context, contentContainer, "Learning Rate:", createEditText(context, "0.0002", "0.0002"), "gan_lr")

        val btnTrain = createStyledButton(context, "Start Custom GAN Training", "#27ae60")
        btnTrain.setOnClickListener { statusLabel.text = "Starting Basic GAN Training..." }
        contentContainer.addView(btnTrain)
    }
}