package com.personal.image_toolkit.ui

import android.content.Context
import android.graphics.Color
import android.util.AttributeSet
import android.view.Gravity
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.LinearLayout
import android.widget.Spinner
import android.widget.TextView
import androidx.appcompat.widget.AppCompatButton
import androidx.appcompat.widget.AppCompatSpinner
import kotlin.math.ceil

/**
 * A reusable Pagination Control widget.
 * Equivalent to _common_create_pagination_ui in Python.
 */
class PaginationControl @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : LinearLayout(context, attrs) {

    private val pageSizeSpinner: AppCompatSpinner
    private val btnPrev: AppCompatButton
    private val btnNext: AppCompatButton
    private val btnPage: AppCompatButton
    private val label: TextView

    var onPageSizeChanged: ((Int) -> Unit)? = null
    var onPageChange: ((Int) -> Unit)? = null

    private var totalItems = 0
    private var pageSize = 100
    private var currentPage = 0

    init {
        orientation = HORIZONTAL
        gravity = Gravity.CENTER
        setPadding(16, 8, 16, 8)

        label = TextView(context).apply {
            text = "Images per page: "
            setTextColor(Color.LTGRAY)
        }
        addView(label)

        pageSizeSpinner = AppCompatSpinner(context).apply {
            val items = arrayOf("20", "50", "100", "1000", "All")
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, items)
            setSelection(2) // Default to 100
        }
        addView(pageSizeSpinner)

        // Spacer
        addView(android.view.View(context).apply { 
            layoutParams = LayoutParams(0, 0, 1f) 
        })

        btnPrev = AppCompatButton(context).apply {
            text = "< Prev"
            setOnClickListener { onPageChange?.invoke(-1) }
        }
        addView(btnPrev)

        btnPage = AppCompatButton(context).apply {
            text = "Page 1 / 1"
            isEnabled = false
        }
        addView(btnPage)

        btnNext = AppCompatButton(context).apply {
            text = "Next >"
            setOnClickListener { onPageChange?.invoke(1) }
        }
        addView(btnNext)

        // Listeners
        pageSizeSpinner.setOnItemSelectedListener(object : android.widget.AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: android.widget.AdapterView<*>?, view: android.view.View?, position: Int, id: Long) {
                val selected = parent?.getItemAtPosition(position).toString()
                val size = if (selected == "All") Int.MAX_VALUE else selected.toInt()
                if (size != pageSize) {
                    pageSize = size
                    onPageSizeChanged?.invoke(pageSize)
                }
            }
            override fun onNothingSelected(parent: android.widget.AdapterView<*>?) {}
        })
    }

    fun updateState(totalItems: Int, currentPage: Int, pageSize: Int): Int {
        this.totalItems = totalItems
        this.pageSize = pageSize
        
        val totalPages = if (totalItems == 0) 0 else ceil(totalItems.toDouble() / pageSize).toInt()
        
        // Correct current page if out of bounds
        var safePage = currentPage
        if (safePage >= totalPages) safePage = (totalPages - 1).coerceAtLeast(0)
        
        this.currentPage = safePage

        btnPage.text = if (totalItems == 0) "Page 0 / 0" else "Page ${safePage + 1} / $totalPages"
        
        btnPrev.isEnabled = safePage > 0
        btnNext.isEnabled = safePage < totalPages - 1
        
        return safePage
    }
}