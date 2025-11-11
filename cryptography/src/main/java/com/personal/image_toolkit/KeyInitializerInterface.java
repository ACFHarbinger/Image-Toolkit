package com.personal.image_toolkit;

import java.io.IOException;
import java.security.KeyStoreException;
import java.security.NoSuchAlgorithmException;
import java.security.cert.CertificateException;
import org.bouncycastle.operator.OperatorCreationException;

/**
 * Defines the contract for a component responsible for ensuring the KeyStore file
 * and its required SecretKey entry are initialized and persisted.
 */
public interface KeyInitializerInterface {

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
    void initializeKeystore(String keystoreFile, String keyAlias, char[] keystorePassword, char[] keyPassword)
            throws KeyStoreException, IOException, NoSuchAlgorithmException, CertificateException, OperatorCreationException;
}