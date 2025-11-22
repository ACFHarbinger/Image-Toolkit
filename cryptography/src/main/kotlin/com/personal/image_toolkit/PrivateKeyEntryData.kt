package com.personal.image_toolkit

import java.security.PrivateKey
import java.security.cert.Certificate
import java.util.Arrays

/**
 * A data container class (Data Transfer Object) for bundling all necessary
 * components of a PrivateKeyEntry needed for KeyStore operations.
 * This simplifies passing a private key, its certificate chain, alias,
 * and password between methods without long parameter lists.
 */
class PrivateKeyEntryData(
    override val alias: String,
    override val privateKey: PrivateKey,
    certificateChain: Array<Certificate>,
    keyPassword: CharArray
) : PrivateKeyEntryDataInterface {

    // Internal backing fields to support defensive copying
    private val _certificateChain: Array<Certificate> = certificateChain
    private val _keyPassword: CharArray = keyPassword

    /**
     * @return The certificate chain. Returns a defensive copy to prevent external modification.
     */
    override val certificateChain: Array<Certificate>
        get() = _certificateChain.clone()

    /**
     * @return The password for the key. Returns a defensive copy (char array) for security.
     */
    override val keyPassword: CharArray
        get() = _keyPassword.clone()

    /**
     * Security best practice: clears the key password from the internal array.
     * This should be called when the object is no longer needed.
     */
    override fun clearPassword() {
        Arrays.fill(_keyPassword, ' ')
    }
}