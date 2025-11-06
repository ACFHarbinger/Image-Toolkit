package com.personal.image_toolkit;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import javax.crypto.SecretKey;
import java.io.File;
import java.nio.file.Path;
import java.security.KeyStore;
import java.util.Arrays;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration test for the end-to-end workflow
 *
 * This test validates the interaction between KeyStoreManager and SecureJsonVault:
 * 1. A KeyStore is created and saved.
 * 2. A SecretKey is stored in the KeyStore.
 * 3. The SecretKey is retrieved from the KeyStore.
 * 4. The key is used to initialize a SecureJsonVault.
 * 5. Data is encrypted and saved to the vault.
 * 6. Data is loaded and decrypted from the vault.
 * 7. The decrypted data is verified.
 */
class CryptographyIntegrationTest {

    // JUnit 5 will create a temporary directory for each test
    @TempDir
    Path tempDir;

    private String keyStoreFilePath;
    private String vaultFilePath;
    private char[] keyStorePassword;
    private char[] keyPassword;
    private final String testJson = "{\"user\":\"test-user\", \"data\":\"sensitive-info\"}";

    @BeforeEach
    void setUp() {
        // Define paths for files within the temporary directory
        keyStoreFilePath = tempDir.resolve("test_keystore.p12").toString();
        vaultFilePath = tempDir.resolve("test_vault.dat").toString();

        keyStorePassword = new char[]{'s', 't', 'o', 'r', 'e', 'p', 'a', 's', 's'};
        keyPassword = new char[]{'k', 'e', 'y', 'p', 'a', 's', 's'};
    }

    @AfterEach
    void tearDown() {
        // Clear passwords from memory for security
        Arrays.fill(keyStorePassword, ' ');
        Arrays.fill(keyPassword, ' ');
    }

    @Test
    void testKeyStoreToVaultEndToEndLifecycle() throws Exception {
        // --- 1. KeyStore Creation and Key Storage ---
        // Mimics steps 1-4 of Cryptography.main()

        String secretKeyAlias = "my-integration-test-key";
        File keyStoreFile = new File(keyStoreFilePath);

        // Load an empty keystore in memory
        KeyStore keyStore = KeyStoreManager.loadKeyStore(keyStoreFilePath, keyStorePassword);
        assertThat(keyStoreFile).doesNotExist(); // loadKeyStore creates in memory first

        // Store a new secret key
        KeyStoreManager.storeSecretKey(keyStore, secretKeyAlias, keyPassword);
        assertThat(keyStore.containsAlias(secretKeyAlias)).isTrue();

        // Save the keystore to disk
        KeyStoreManager.saveKeyStore(keyStore, keyStoreFilePath, keyStorePassword);
        assertThat(keyStoreFile).exists().isFile();

        // --- 2. Key Retrieval ---
        // Mimics step 5 of Cryptography.main()

        // Load the persistent keystore from disk to ensure it saved correctly
        KeyStore loadedKeyStore = KeyStoreManager.loadKeyStore(keyStoreFilePath, keyStorePassword);
        
        // Retrieve the key
        SecretKey retrievedKey = KeyStoreManager.getSecretKey(loadedKeyStore, secretKeyAlias, keyPassword);

        assertThat(retrievedKey).isNotNull();
        assertThat(retrievedKey.getAlgorithm()).isEqualTo("AES");

        // --- 3. Secure Vault Encryption ---
        // Mimics steps 6-7 of Cryptography.main()
        
        File vaultFile = new File(vaultFilePath);
        SecureJsonVault vault = new SecureJsonVault(retrievedKey, vaultFilePath);

        // Save data
        vault.saveData(testJson);
        assertThat(vaultFile).exists().isFile();

        // --- 4. Secure Vault Decryption and Verification ---
        // Mimics step 8 of Cryptography.main()

        // Load data from the vault file
        String loadedJson = vault.loadData();

        // Verify the decrypted data matches the original
        assertThat(loadedJson).isEqualTo(testJson);
    }

    @Test
    void testMainMethodCreatesFiles() throws Exception {
        // This is a simple "smoke test" to prove the main() method runs
        // and creates its hardcoded files.
        
        String keyStoreFilename = "my_keystore.p12";
        String vaultFilename = "user_data.vault";

        File keyStoreFile = new File(keyStoreFilename);
        File vaultFile = new File(vaultFilename);

        // Clean up before run, in case they exist from a previous manual run
        keyStoreFile.delete();
        vaultFile.delete();

        assertThat(keyStoreFile).doesNotExist();
        assertThat(vaultFile).doesNotExist();

        // Act
        Cryptography.main(null);

        // Assert
        // The main method should create and save both files
        assertThat(keyStoreFile).exists();
        assertThat(vaultFile).exists();

        // Clean up after run
        keyStoreFile.delete();
        vaultFile.delete();
    }
}