package com.personal.image_toolkit.ui.windows

import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.fragment.app.Fragment

/**
 * Android implementation of LoginWindow.
 * Handles authentication and account creation.
 */
class LoginFragment : Fragment() {

    var onLoginSuccess: (() -> Unit)? = null

    private lateinit var usernameEdit: EditText
    private lateinit var passwordEdit: EditText
    private lateinit var btnLogin: Button
    private lateinit var btnCreate: Button

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        val context = requireContext()
        val layout = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(32, 32, 32, 32)
            setBackgroundColor(Color.parseColor("#2d2d30"))
        }

        // Title
        val title = TextView(context).apply {
            text = "Welcome - Secure Toolkit Access"
            textSize = 24f
            setTextColor(Color.parseColor("#00bcd4"))
            gravity = Gravity.CENTER
            setPadding(0, 0, 0, 48)
        }
        layout.addView(title)

        // Inputs
        usernameEdit = createInput(context, "Account Name")
        layout.addView(usernameEdit)

        passwordEdit = createInput(context, "Password", isPassword = true)
        layout.addView(passwordEdit)

        // Buttons
        val btnLayout = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(0, 32, 0, 0)
        }

        btnCreate = Button(context).apply {
            text = "Create Account"
            setOnClickListener { handleCreate() }
        }
        
        btnLogin = Button(context).apply {
            text = "Login"
            setBackgroundColor(Color.parseColor("#00bcd4"))
            setTextColor(Color.WHITE)
            setOnClickListener { handleLogin() }
        }

        btnLayout.addView(btnCreate)
        // Spacer
        btnLayout.addView(View(context).apply { layoutParams = LinearLayout.LayoutParams(32, 1) })
        btnLayout.addView(btnLogin)

        layout.addView(btnLayout)

        return layout
    }

    private fun createInput(context: Context, hintText: String, isPassword: Boolean = false): EditText {
        return EditText(context).apply {
            hint = hintText
            setHintTextColor(Color.GRAY)
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.parseColor("#3e3e42"))
            setPadding(24, 24, 24, 24)
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, 16, 0, 16)
            }
            if (isPassword) {
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            }
        }
    }

    private fun handleLogin() {
        val user = usernameEdit.text.toString()
        val pass = passwordEdit.text.toString()

        if (user.isEmpty() || pass.isEmpty()) {
            Toast.makeText(context, "Please enter credentials", Toast.LENGTH_SHORT).show()
            return
        }

        // Mock Authentication Logic
        // In real app: VaultManager.load_keystore(...)
        if (pass == "password") { // Mock check
            Toast.makeText(context, "Login Successful for $user", Toast.LENGTH_SHORT).show()
            onLoginSuccess?.invoke()
        } else {
            Toast.makeText(context, "Invalid Password", Toast.LENGTH_SHORT).show()
        }
    }

    private fun handleCreate() {
        val user = usernameEdit.text.toString()
        if (user.isEmpty()) return
        Toast.makeText(context, "Account '$user' created (Mock)", Toast.LENGTH_SHORT).show()
    }
}