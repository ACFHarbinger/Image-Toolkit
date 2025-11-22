package com.personal.image_toolkit

import java.io.IOException
import java.security.KeyStore
import java.security.KeyStoreException
import java.security.NoSuchAlgorithmException
import java.security.UnrecoverableEntryException
import java.security.cert.CertificateException
import javax.crypto.SecretKey

/**
 * Defines the contract for a component responsible for managing Java KeyStore operations,
 * including loading, saving, storing, and retrieving various types of cryptographic entries.
 */
interface KeyStoreManagerInterface {
    /**
     * Loads a KeyStore from a file. If the file doesn't exist,
     * it creates a new, empty KeyStore.
     *
     * @param fileName The path to the KeyStore file.
     * @param password The password for the KeyStore.
     * @return A loaded or newly created [KeyStore] instance.
     * @throws KeyStoreException If no implementation for the KeyStore type is found.
     * @throws IOException If an I/O error occurs while loading the file.
     * @throws NoSuchAlgorithmException If the algorithm for checking the integrity of the KeyStore cannot be found.
     * @throws CertificateException If any of the certificates in the KeyStore could not be loaded.
     */
    @Throws(
        KeyStoreException::class,
        IOException::class,
        NoSuchAlgorithmException::class,
        CertificateException::class
    )
    fun loadKeyStore(fileName: String, password: CharArray): KeyStore

    /**
     * Saves the KeyStore content to a file.
     *
     * @param keyStore The [KeyStore] instance to save.
     * @param fileName The path to the KeyStore file.
     * @param password The password used to protect the KeyStore.
     * @throws KeyStoreException If an error occurs while writing the KeyStore to the output stream.
     * @throws IOException If an I/O error occurs while writing to the file.
     * @throws NoSuchAlgorithmException If the algorithm for creating the integrity protection of the KeyStore cannot be found.
     * @throws CertificateException If any of the certificates in the KeyStore could not be stored.
     */
    @Throws(
        KeyStoreException::class,
        IOException::class,
        NoSuchAlgorithmException::class,
        CertificateException::class
    )
    fun saveKeyStore(keyStore: KeyStore, fileName: String, password: CharArray)

    /**
     * Stores a PrivateKeyEntry into the KeyStore.
     *
     * @param keyStore The KeyStore to store the entry in.
     * @param data The DTO containing the alias, private key, certificate chain, and key password.
     * @throws KeyStoreException If there is an issue storing the entry.
     */
    @Throws(KeyStoreException::class)
    fun storePrivateKeyEntry(keyStore: KeyStore, data: PrivateKeyEntryData)

    /**
     * Stores a SecretKey (Symmetric Key) into the KeyStore.
     *
     * @param keyStore The KeyStore to store the entry in.
     * @param alias The alias for the secret key entry.
     * @param keyPassword The password protecting the specific key entry.
     * @throws NoSuchAlgorithmException If the AES algorithm for key generation is not available.
     * @throws KeyStoreException If there is an issue storing the entry.
     */
    @Throws(NoSuchAlgorithmException::class, KeyStoreException::class)
    fun storeSecretKey(keyStore: KeyStore, alias: String, keyPassword: CharArray)

    /**
     * Retrieves a SecretKey from the KeyStore.
     *
     * @param keyStore The KeyStore to retrieve the entry from.
     * @param alias The alias of the entry.
     * @param keyPassword The password protecting the specific key entry.
     * @return The retrieved SecretKey.
     * @throws KeyStoreException If there is an issue with the KeyStore.
     * @throws NoSuchAlgorithmException If the algorithm is not supported.
     * @throws UnrecoverableEntryException If the entry cannot be recovered with the given password.
     */
    @Throws(
        NoSuchAlgorithmException::class,
        UnrecoverableEntryException::class,
        KeyStoreException::class
    )
    fun getSecretKey(keyStore: KeyStore, alias: String, keyPassword: CharArray): SecretKey?

    /**
     * Stores a TrustedCertificateEntry into the KeyStore.
     *
     * @param keyStore The KeyStore to store the entry in.
     * @param certEntryData The DTO containing the alias and trusted certificate.
     * @throws KeyStoreException If there is an issue storing the entry.
     */
    @Throws(KeyStoreException::class)
    fun storeTrustedCertificate(keyStore: KeyStore, certEntryData: TrustedCertificateEntryData)
}