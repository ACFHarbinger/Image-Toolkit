package com.personal.image_toolkit

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File
import java.nio.file.Path
import java.security.KeyStore
import java.util.Arrays
import kotlin.io.path.pathString

/**
 * Integration test for the end-to-end workflow
 */
class CryptographyIntegrationTest {

    @TempDir
    lateinit var tempDir: Path

    private lateinit var keyStoreFilePath: String
    private lateinit var vaultFilePath: String
    private lateinit var keyStorePassword: CharArray
    private lateinit var keyPassword: CharArray
    private val testJson = """{"user":"test-user", "data":"sensitive-info"}"""

    @BeforeEach
    fun setUp() {
        // Define paths for files within the temporary directory
        keyStoreFilePath = tempDir.resolve("test_keystore.p12").pathString
        vaultFilePath = tempDir.resolve("test_vault.dat").pathString

        keyStorePassword = charArrayOf('s', 't', 'o', 'r', 'e', 'p', 'a', 's', 's')
        keyPassword = charArrayOf('k', 'e', 'y', 'p', 'a', 's', 's')
    }

    @AfterEach
    fun tearDown() {
        // Clear passwords from memory for security
        Arrays.fill(keyStorePassword, ' ')
        Arrays.fill(keyPassword, ' ')
    }

    @Test
    fun testKeyStoreToVaultEndToEndLifecycle() {
        val manager = KeyStoreManager()

        // --- 1. KeyStore Creation and Key Storage ---
        val secretKeyAlias = "my-integration-test-key"
        val keyStoreFile = File(keyStoreFilePath)

        // Load an empty keystore in memory
        val keyStore = manager.loadKeyStore(keyStoreFilePath, keyStorePassword)
        assertThat(keyStoreFile).doesNotExist() // loadKeyStore creates in memory first

        // Store a new secret key
        manager.storeSecretKey(keyStore, secretKeyAlias, keyPassword)
        assertThat(keyStore.containsAlias(secretKeyAlias)).isTrue

        // Save the keystore to disk
        manager.saveKeyStore(keyStore, keyStoreFilePath, keyStorePassword)
        assertThat(keyStoreFile).exists().isFile

        // --- 2. Key Retrieval ---
        // Load the persistent keystore from disk to ensure it saved correctly
        val loadedKeyStore = manager.loadKeyStore(keyStoreFilePath, keyStorePassword)

        // Retrieve the key
        val retrievedKey = manager.getSecretKey(loadedKeyStore, secretKeyAlias, keyPassword)

        assertThat(retrievedKey).isNotNull
        assertThat(retrievedKey!!.algorithm).isEqualTo("AES")

        // --- 3. Secure Vault Encryption ---
        val vaultFile = File(vaultFilePath)
        val vault = SecureJsonVault(retrievedKey, vaultFilePath)

        // Save data
        vault.saveData(testJson)
        assertThat(vaultFile).exists().isFile

        // --- 4. Secure Vault Decryption and Verification ---
        // Load data from the vault file
        val loadedJson = vault.loadData()

        // Verify the decrypted data matches the original
        assertThat(loadedJson).isEqualTo(testJson)
    }

    @Test
    fun testMainMethodCreatesFiles() {
        // This is a simple "smoke test" to prove the main() method runs
        // and creates its hardcoded files.

        val keyStoreFilename = "my_keystore.p12"
        val vaultFilename = "user_data.vault"

        val keyStoreFile = File(keyStoreFilename)
        val vaultFile = File(vaultFilename)

        // Clean up before run, in case they exist from a previous manual run
        keyStoreFile.delete()
        vaultFile.delete()

        assertThat(keyStoreFile).doesNotExist()
        assertThat(vaultFile).doesNotExist()

        // Act
        main()

        // Assert
        // The main method should create and save both files
        assertThat(keyStoreFile).exists()
        assertThat(vaultFile).exists()

        // Clean up after run
        keyStoreFile.delete()
        vaultFile.delete()
    }
}