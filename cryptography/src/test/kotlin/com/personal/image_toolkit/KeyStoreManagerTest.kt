package com.personal.image_toolkit

import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.io.PrintStream
import java.nio.file.Path
import java.security.KeyStore
import java.security.UnrecoverableEntryException
import java.security.cert.Certificate
import java.util.Collections
import kotlin.io.path.pathString

class KeyStoreManagerTest {

    @TempDir
    lateinit var tempDir: Path

    private lateinit var keyStoreFile: String
    private lateinit var keyStorePassword: CharArray
    private lateinit var keyPassword: CharArray
    private lateinit var keyStoreManager: KeyStoreManager

    // For capturing System.out and System.err
    private val outContent = ByteArrayOutputStream()
    private val errContent = ByteArrayOutputStream()
    private val originalOut = System.out
    private val originalErr = System.err

    @BeforeEach
    fun setUp() {
        keyStoreFile = tempDir.resolve("test.p12").pathString
        keyStorePassword = "storePassword".toCharArray()
        keyPassword = "keyPassword".toCharArray()
        keyStoreManager = KeyStoreManager()

        // Redirect System.out and System.err
        System.setOut(PrintStream(outContent))
        System.setErr(PrintStream(errContent))
    }

    @AfterEach
    fun tearDown() {
        // Restore System.out and System.err
        System.setOut(originalOut)
        System.setErr(originalErr)
    }

    @Test
    fun loadKeyStore_shouldCreateNewKeyStoreIfFileDoesNotExist() {
        val keyStore = keyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword)

        assertThat(keyStore).isNotNull
        assertThat(Collections.list(keyStore.aliases())).isEmpty()
        assertThat(outContent.toString()).contains("Created new empty keystore")
    }

    @Test
    fun saveAndLoadKeyStore_shouldPreserveEntries() {
        // 1. Create and save a keystore
        val keyStore = keyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword)
        keyStoreManager.storeSecretKey(keyStore, "my-secret-key", keyPassword)
        keyStoreManager.saveKeyStore(keyStore, keyStoreFile, keyStorePassword)

        assertThat(File(keyStoreFile)).exists()

        // 2. Load the existing keystore
        val loadedKeyStore = keyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword)

        assertThat(loadedKeyStore).isNotNull
        assertThat(loadedKeyStore.containsAlias("my-secret-key")).isTrue
        assertThat(outContent.toString()).contains("Loaded existing keystore")
    }

    @Test
    fun loadKeyStore_shouldThrowExceptionForIncorrectPassword() {
        // 1. Create and save a keystore
        val keyStore = keyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword)
        keyStoreManager.saveKeyStore(keyStore, keyStoreFile, keyStorePassword)

        // 2. Try to load with wrong password
        val wrongPassword = "wrong".toCharArray()
        assertThatThrownBy { keyStoreManager.loadKeyStore(keyStoreFile, wrongPassword) }
            .isInstanceOf(IOException::class.java)
    }

    @Test
    fun storeAndGetSecretKey_shouldRetrieveSameKey() {
        val keyStore = keyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword)
        val alias = "aes-key"

        keyStoreManager.storeSecretKey(keyStore, alias, keyPassword)

        val retrievedKey = keyStoreManager.getSecretKey(keyStore, alias, keyPassword)

        assertThat(retrievedKey).isNotNull
        assertThat(retrievedKey!!.algorithm).isEqualTo("AES")
        assertThat(retrievedKey.encoded.size).isEqualTo(32) // 256 bits
    }

    @Test
    fun getSecretKey_shouldReturnNullForNonExistentAlias() {
        val keyStore = keyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword)
        val retrievedKey = keyStoreManager.getSecretKey(keyStore, "non-existent", keyPassword)

        assertThat(retrievedKey).isNull()
        assertThat(errContent.toString()).contains("No entry found for alias: non-existent")
    }

    @Test
    fun getSecretKey_shouldThrowExceptionForIncorrectKeyPassword() {
        val keyStore = keyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword)
        val alias = "aes-key"
        keyStoreManager.storeSecretKey(keyStore, alias, keyPassword)

        val wrongKeyPassword = "wrong".toCharArray()

        assertThatThrownBy { keyStoreManager.getSecretKey(keyStore, alias, wrongKeyPassword) }
            .isInstanceOf(UnrecoverableEntryException::class.java)
    }

    @Test
    fun generatePrivateKeyEntry_shouldCreateValidEntry() {
        val alias = "rsa-key"
        // Companion object call
        val data = KeyStoreManager.generatePrivateKeyEntry(alias, keyPassword)

        assertThat(data).isNotNull
        assertThat(data.alias).isEqualTo(alias)
        assertThat(data.keyPassword).isEqualTo(keyPassword)
        assertThat(data.privateKey).isNotNull
        assertThat(data.privateKey.algorithm).isEqualTo("RSA")
        assertThat(data.certificateChain).isNotNull.hasSize(1)
        assertThat(data.certificateChain[0]).isNotNull.isInstanceOf(Certificate::class.java)
    }

    @Test
    fun storePrivateKeyEntry_shouldStoreEntryAndClearPassword() {
        val keyStore = keyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword)
        val alias = "rsa-key"
        val originalPassword = charArrayOf('s', 'e', 'c', 'r', 'e', 't')

        val data = KeyStoreManager.generatePrivateKeyEntry(alias, originalPassword)

        // Act
        keyStoreManager.storePrivateKeyEntry(keyStore, data)

        // Assert
        assertThat(keyStore.isKeyEntry(alias)).isTrue
        assertThat(outContent.toString()).contains("Stored private key for alias: $alias")

        // Verify the password in the original data object was cleared
        assertThat(originalPassword).containsOnly(' ')
    }

    @Test
    fun storeTrustedCertificate_shouldStoreEntry() {
        val keyStore = keyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword)
        val alias = "trusted-cert"

        val pkeData = KeyStoreManager.generatePrivateKeyEntry("temp", "temp".toCharArray())
        val cert = pkeData.certificateChain[0]

        val data = TrustedCertificateEntryData(alias, cert)

        // Act
        keyStoreManager.storeTrustedCertificate(keyStore, data)

        // Assert
        assertThat(keyStore.isCertificateEntry(alias)).isTrue
        assertThat(keyStore.getCertificate(alias)).isEqualTo(cert)
        assertThat(outContent.toString()).contains("Stored trusted certificate for alias: " + data.alias)
    }

    @Test
    fun listEntries_shouldListAllEntriesCorrectly() {
        val keyStore = keyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword)

        // 1. Test empty keystore
        KeyStoreManager.listEntries(keyStore)
        assertThat(outContent.toString()).contains("Keystore is empty.")

        outContent.reset() // Clear the output stream

        // 2. Add entries
        keyStoreManager.storeSecretKey(keyStore, "secret-key", keyPassword)

        val pkeData = KeyStoreManager.generatePrivateKeyEntry("private-key", keyPassword)
        keyStoreManager.storePrivateKeyEntry(keyStore, pkeData)

        val tcData = TrustedCertificateEntryData("trusted-cert", pkeData.certificateChain[0])
        keyStoreManager.storeTrustedCertificate(keyStore, tcData)

        outContent.reset() // Clear output from store methods

        // 3. Test listing
        KeyStoreManager.listEntries(keyStore)
        val output = outContent.toString()

        assertThat(output)
            .contains("Alias: secret-key (Key Entry)")
            .contains("Alias: private-key (Key Entry)")
            .contains("Alias: trusted-cert (Certificate Entry)")
    }
}