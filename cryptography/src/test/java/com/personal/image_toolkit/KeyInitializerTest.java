package com.personal.image_toolkit;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.io.File;
import java.security.KeyStore;
import static org.junit.jupiter.api.Assertions.*;

/**
 * JUnit 5 test class for KeyInitializer.
 * Verifies that the keystore and secret key are correctly created and persisted.
 */
public class KeyInitializerTest {

    private KeyInitializer initializer;
    private KeyStoreManager manager;
    
    // JUnit 5 annotation to create a temporary directory for file operations
    @TempDir
    File tempDir; 

    private String keystoreFilePath;
    private char[] keystorePass = "masterPass".toCharArray();
    private char[] keyPass = "masterPass".toCharArray();
    private String keyAlias = "test-secret-key";

    @BeforeEach
    void setUp() {
        initializer = new KeyInitializer();
        manager = new KeyStoreManager();
        // Create the full temporary path for the keystore file
        keystoreFilePath = tempDir.getAbsolutePath() + File.separator + "test_keystore.p12";
    }

    @AfterEach
    void tearDown() {
        // Clear passwords from memory after each test
        java.util.Arrays.fill(keystorePass, ' ');
        java.util.Arrays.fill(keyPass, ' ');
    }

    @Test
    void testKeystoreCreationAndKeyStorage() throws Exception {
        File keystoreFile = new File(keystoreFilePath);
        
        // 1. Initial run: Keystore and Key should be created
        assertFalse(keystoreFile.exists(), "Initial: Keystore file should not exist.");
        
        initializer.initializeKeystore(keystoreFilePath, keyAlias, keystorePass, keyPass);
        
        assertTrue(keystoreFile.exists(), "After initialization: Keystore file must exist.");

        // 2. Verify key contents: Load the created keystore and check the key entry
        KeyStore loadedKeystore = manager.loadKeyStore(keystoreFilePath, keystorePass);
        assertTrue(loadedKeystore.containsAlias(keyAlias), "Keystore must contain the alias after creation.");
        
        // Check that the key can be retrieved using the correct key password
        assertNotNull(manager.getSecretKey(loadedKeystore, keyAlias, keyPass), 
                      "SecretKey must be recoverable with the correct password.");
    }

    @Test
    void testKeystoreKeyGenerationIsSkippedOnSecondRun() throws Exception {
        // 1. First run: Key is created
        initializer.initializeKeystore(keystoreFilePath, keyAlias, keystorePass, keyPass);
        
        // 2. Load the keystore
        KeyStore loadedKeystore = manager.loadKeyStore(keystoreFilePath, keystorePass);
        
        // 3. Store the current key's creation date (approximation via modification date)
        long firstModified = new File(keystoreFilePath).lastModified();
        
        // 4. Wait a short period (must be > 1 second for modification time to change)
        Thread.sleep(1500); 

        // 5. Second run: Key should NOT be generated again if it already exists
        initializer.initializeKeystore(keystoreFilePath, keyAlias, keystorePass, keyPass);
        
        long secondModified = new File(keystoreFilePath).lastModified();
        
        // Verification: The file modification time should not have changed, 
        // proving that saveKeyStore() was not called (or not needed) 
        // because the key was already present.
        assertEquals(firstModified, secondModified, 
                     "File modification time should not change on second run, proving key generation was skipped.");
        
        // Final check: key is still present
        KeyStore finalKeystore = manager.loadKeyStore(keystoreFilePath, keystorePass);
        assertTrue(finalKeystore.containsAlias(keyAlias), "Key must still be present.");
    }

    @Test
    void testKeyRetrievalFailsWithWrongPassword() throws Exception {
        initializer.initializeKeystore(keystoreFilePath, keyAlias, keystorePass, keyPass);
        
        KeyStore loadedKeystore = manager.loadKeyStore(keystoreFilePath, keystorePass);
        
        char[] wrongPass = "wrongPass".toCharArray();
        
        // Attempt to retrieve the key with the wrong password must throw an exception
        assertThrows(java.security.UnrecoverableEntryException.class, () -> {
            manager.getSecretKey(loadedKeystore, keyAlias, wrongPass);
        }, "Retrieving key with wrong password must fail.");
    }
}