package com.personal.image_toolkit

import org.bouncycastle.operator.OperatorCreationException
import java.io.IOException
import java.security.KeyStoreException
import java.security.NoSuchAlgorithmException
import java.security.cert.CertificateException

/**
 * Defines the contract for a component responsible for ensuring the KeyStore file
 * and its required SecretKey entry are initialized and persisted.
 */
interface KeyInitializerInterface {
    /**
     * Loads the keystore, checks if the SecretKey exists under the given alias,
     * and creates/saves a new SecretKey if it is missing.
     *
     * @param keystoreFile The path to the KeyStore file (e.g., my_keystore.p12).
     * @param keyAlias The alias of the required SecretKey (e.g., my-secret-key).
     * @param keystorePassword The password to protect the KeyStore file.
     * @param keyPassword The password to protect the individual key entry.
     * @throws KeyStoreException If no KeyStore provider is available.
     * @throws IOException If an I/O error occurs (file reading/writing).
     * @throws NoSuchAlgorithmException If the required cryptographic algorithms (e.g., AES) are not found.
     * @throws CertificateException If certificate issues arise during KeyStore loading.
     * @throws OperatorCreationException If Bouncy Castle operator issues occur.
     */
    @Throws(
        KeyStoreException::class,
        IOException::class,
        NoSuchAlgorithmException::class,
        CertificateException::class,
        OperatorCreationException::class
    )
    fun initializeKeystore(
        keystoreFile: String,
        keyAlias: String,
        keystorePassword: CharArray,
        keyPassword: CharArray
    )
}