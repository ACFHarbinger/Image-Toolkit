package com.personal.image_toolkit.ui.tabs

import android.content.Context
import android.graphics.Color
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.widget.AppCompatSpinner
import androidx.core.view.setPadding
import androidx.fragment.app.Fragment

/**
 * Base class for Generative AI fragments.
 * Provides helper methods to build standardized form rows (Label + Input).
 */
abstract class BaseGenerativeFragment : Fragment() {

    // Helper map to store references to form widgets for "collect()" functionality
    protected val formWidgets = mutableMapOf<String, View>()

    /**
     * Adds a row with a Label and a Widget (EditText, Spinner, etc.) to the parent layout.
     * Registers the widget in 'formWidgets' map with the given key.
     */
    protected fun addParamWidget(
        context: Context,
        parent: ViewGroup,
        label: String,
        widget: View,
        key: String
    ) {
        val row = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, 8, 0, 8)
            }
        }

        val labelView = TextView(context).apply {
            text = label
            setTextColor(Color.LTGRAY)
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 0.4f)
        }

        // Adjust widget params to fill remaining space
        if (widget.layoutParams == null) {
            widget.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 0.6f)
        } else {
            val params = widget.layoutParams as LinearLayout.LayoutParams
            params.width = 0
            params.weight = 0.6f
            widget.layoutParams = params
        }

        row.addView(labelView)
        row.addView(widget)
        parent.addView(row)

        formWidgets[key] = widget
    }

    /**
     * Creates a standardized styled Button.
     */
    protected fun createStyledButton(context: Context, text: String, colorHex: String): android.widget.Button {
        return android.widget.Button(context).apply {
            this.text = text
            setBackgroundColor(Color.parseColor(colorHex))
            setTextColor(Color.WHITE)
            setPadding(16)
        }
    }

    /**
     * Helper to create an EditText with a hint.
     */
    protected fun createEditText(context: Context, hintText: String = "", defaultText: String = ""): EditText {
        return EditText(context).apply {
            hint = hintText
            setText(defaultText)
            setTextColor(Color.WHITE)
            setHintTextColor(Color.GRAY)
        }
    }

    /**
     * Helper to create a Spinner with items.
     */
    protected fun createSpinner(context: Context, items: Array<String>): AppCompatSpinner {
        return AppCompatSpinner(context).apply {
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, items)
        }
    }

    protected fun createCheckBox(context: Context, text: String): CheckBox {
        return CheckBox(context).apply {
            this.text = text
            setTextColor(Color.WHITE)
        }
    }

    /**
     * Collects values from all registered widgets into a Map.
     */
    protected fun collectParams(): Map<String, Any> {
        val params = mutableMapOf<String, Any>()
        for ((key, view) in formWidgets) {
            when (view) {
                is EditText -> params[key] = view.text.toString()
                is AppCompatSpinner -> params[key] = view.selectedItem?.toString() ?: ""
                is CheckBox -> params[key] = view.isChecked
                // Add logic for custom widgets if needed
            }
        }
        return params
    }
}