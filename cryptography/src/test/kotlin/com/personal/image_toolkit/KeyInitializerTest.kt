package com.personal.image_toolkit

import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.io.TempDir
import java.io.File
import java.security.KeyStore
import java.security.UnrecoverableEntryException
import java.util.Arrays

/**
 * JUnit 5 test class for KeyInitializer.
 * Verifies that the keystore and secret key are correctly created and persisted.
 */
class KeyInitializerTest {

    private lateinit var initializer: KeyInitializer
    private lateinit var manager: KeyStoreManager

    @TempDir
    lateinit var tempDir: File

    private lateinit var keystoreFilePath: String
    private val keystorePass = "masterPass".toCharArray()
    private val keyPass = "masterPass".toCharArray()
    private val keyAlias = "test-secret-key"

    @BeforeEach
    fun setUp() {
        initializer = KeyInitializer()
        manager = KeyStoreManager()
        // Create the full temporary path for the keystore file
        keystoreFilePath = tempDir.absolutePath + File.separator + "test_keystore.p12"
    }

    @AfterEach
    fun tearDown() {
        // Clear passwords from memory after each test
        Arrays.fill(keystorePass, ' ')
        Arrays.fill(keyPass, ' ')
    }

    @Test
    fun testKeystoreCreationAndKeyStorage() {
        val keystoreFile = File(keystoreFilePath)

        // 1. Initial run: Keystore and Key should be created
        assertFalse(keystoreFile.exists(), "Initial: Keystore file should not exist.")

        initializer.initializeKeystore(keystoreFilePath, keyAlias, keystorePass, keyPass)

        assertTrue(keystoreFile.exists(), "After initialization: Keystore file must exist.")

        // 2. Verify key contents: Load the created keystore and check the key entry
        val loadedKeystore = manager.loadKeyStore(keystoreFilePath, keystorePass)
        assertTrue(loadedKeystore.containsAlias(keyAlias), "Keystore must contain the alias after creation.")

        // Check that the key can be retrieved using the correct key password
        assertNotNull(
            manager.getSecretKey(loadedKeystore, keyAlias, keyPass),
            "SecretKey must be recoverable with the correct password."
        )
    }

    @Test
    fun testKeystoreKeyGenerationIsSkippedOnSecondRun() {
        // 1. First run: Key is created
        initializer.initializeKeystore(keystoreFilePath, keyAlias, keystorePass, keyPass)

        // 2. Load the keystore
        // (In a real scenario, we might want to inspect the key content, but checking mod time works for file IO)

        // 3. Store the current key's creation date (approximation via modification date)
        val firstModified = File(keystoreFilePath).lastModified()

        // 4. Wait a short period (must be > 1 second for modification time to change on some FS)
        Thread.sleep(1500)

        // 5. Second run: Key should NOT be generated again if it already exists
        initializer.initializeKeystore(keystoreFilePath, keyAlias, keystorePass, keyPass)

        val secondModified = File(keystoreFilePath).lastModified()

        // Verification: The file modification time should not have changed,
        // proving that saveKeyStore() was not called (or not needed)
        // because the key was already present.
        assertEquals(
            firstModified, secondModified,
            "File modification time should not change on second run, proving key generation was skipped."
        )

        // Final check: key is still present
        val finalKeystore: KeyStore = manager.loadKeyStore(keystoreFilePath, keystorePass)
        assertTrue(finalKeystore.containsAlias(keyAlias), "Key must still be present.")
    }

    @Test
    fun testKeyRetrievalFailsWithWrongPassword() {
        initializer.initializeKeystore(keystoreFilePath, keyAlias, keystorePass, keyPass)

        val loadedKeystore = manager.loadKeyStore(keystoreFilePath, keystorePass)

        val wrongPass = "wrongPass".toCharArray()

        // Attempt to retrieve the key with the wrong password must throw an exception
        assertThrows<UnrecoverableEntryException>("Retrieving key with wrong password must fail.") {
            manager.getSecretKey(loadedKeystore, keyAlias, wrongPass)
        }
    }
}