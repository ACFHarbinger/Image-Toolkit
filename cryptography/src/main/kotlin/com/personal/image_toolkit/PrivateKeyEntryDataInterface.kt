package com.personal.image_toolkit

import java.security.PrivateKey
import java.security.cert.Certificate

/**
 * Defines the contract for accessing data related to a PrivateKeyEntry.
 */
interface PrivateKeyEntryDataInterface {
    /**
     * @return The alias of the key entry.
     */
    val alias: String

    /**
     * @return The private key.
     */
    val privateKey: PrivateKey

    /**
     * @return The certificate chain.
     */
    val certificateChain: Array<Certificate>

    /**
     * @return The password for the key.
     */
    val keyPassword: CharArray

    /**
     * Clears the key password from the internal array for security best practice.
     */
    fun clearPassword()
}