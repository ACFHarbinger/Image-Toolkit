package com.personal.image_toolkit;

import java.io.File;
import java.io.IOException;
import java.security.KeyStore;
import java.security.KeyStoreException;
import java.security.NoSuchAlgorithmException;
import java.security.cert.CertificateException;
import org.bouncycastle.operator.OperatorCreationException;

/**
 * Utility class to ensure the KeyStore and the required SecretKey are initialized
 * before the application attempts to use them.
 *
 * Implements the KeyInitializerInterface for testability.
 */
public class KeyInitializer implements KeyInitializerInterface {

    private final KeyStoreManager manager;

    public KeyInitializer() {
        this.manager = new KeyStoreManager();
    }

    /**
     * Loads the keystore, checks if the SecretKey exists, and creates/saves it if missing.
     *
     * @param keystoreFile The path to the KeyStore file (e.g., my_keystore.p12).
     * @param keyAlias The alias of the required SecretKey (e.g., my-secret-key).
     * @param keystorePassword The password to protect the KeyStore file.
     * @param keyPassword The password to protect the individual key entry.
     * @throws KeyStoreException if initialization fails.
     */
    @Override
    public void initializeKeystore(String keystoreFile, String keyAlias, char[] keystorePassword, char[] keyPassword)
            throws KeyStoreException, IOException, NoSuchAlgorithmException, CertificateException, OperatorCreationException {

        // 1. Load or create the keystore file
        KeyStore keyStore = manager.loadKeyStore(keystoreFile, keystorePassword);
        
        // 2. Check if the key entry exists
        // Check both if the alias exists AND if the entry is the correct type (SecretKeyEntry)
        if (!keyStore.containsAlias(keyAlias) || !keyStore.entryInstanceOf(keyAlias, KeyStore.SecretKeyEntry.class)) {
            System.out.println("Keystore initialization: Secret key not found. Generating and storing a new key...");
            
            // 3. Generate and store a new secret key
            manager.storeSecretKey(keyStore, keyAlias, keyPassword);
            
            // 4. Save the keystore to persist the new key
            manager.saveKeyStore(keyStore, keystoreFile, keystorePassword);
            System.out.println("Keystore initialization: Secret key stored and keystore saved successfully.");
        } else {
            System.out.println("Keystore initialization: Secret key found for alias '" + keyAlias + "'. Skipping generation.");
        }
    }
}