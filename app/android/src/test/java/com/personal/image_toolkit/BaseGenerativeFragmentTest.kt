package com.personal.image_toolkit.ui.tabs

import android.content.Context
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import androidx.appcompat.widget.AppCompatSpinner
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class BaseGenerativeFragmentTest {

    // Concrete implementation for testing abstract class
    class TestGenerativeFragment : BaseGenerativeFragment() {
        fun exposeAddParamWidget(context: Context, parent: android.view.ViewGroup, label: String, widget: android.view.View, key: String) {
            addParamWidget(context, parent, label, widget, key)
        }

        fun exposeCollectParams(): Map<String, Any> {
            return collectParams()
        }
    }

    private lateinit var fragment: TestGenerativeFragment
    private lateinit var context: Context
    private lateinit var container: LinearLayout

    @Before
    fun setup() {
        fragment = TestGenerativeFragment()
        context = ApplicationProvider.getApplicationContext()
        container = LinearLayout(context)
    }

    @Test
    fun `collectParams gathers data from EditText`() {
        val editText = EditText(context).apply { setText("Hello World") }
        
        fragment.exposeAddParamWidget(context, container, "Prompt", editText, "prompt_key")
        
        val params = fragment.exposeCollectParams()
        
        assertEquals("Hello World", params["prompt_key"])
    }

    @Test
    fun `collectParams gathers data from CheckBox`() {
        val checkBox = CheckBox(context).apply { isChecked = true }
        
        fragment.exposeAddParamWidget(context, container, "Use GPU", checkBox, "gpu_key")
        
        val params = fragment.exposeCollectParams()
        
        assertEquals(true, params["gpu_key"])
    }

    @Test
    fun `collectParams gathers data from multiple widgets`() {
        val edit = EditText(context).apply { setText("Value1") }
        val check = CheckBox(context).apply { isChecked = false }
        
        fragment.exposeAddParamWidget(context, container, "Label1", edit, "key1")
        fragment.exposeAddParamWidget(context, container, "Label2", check, "key2")
        
        val params = fragment.exposeCollectParams()
        
        assertEquals("Value1", params["key1"])
        assertEquals(false, params["key2"])
        assertEquals(2, params.size)
    }
}