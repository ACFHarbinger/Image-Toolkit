package com.personal.image_toolkit

import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatIllegalArgumentException
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.DataOutputStream
import java.io.File
import java.io.FileNotFoundException
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.Path
import java.util.Arrays
import javax.crypto.AEADBadTagException
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import kotlin.io.path.pathString

class SecureJsonVaultTest {

    @TempDir
    lateinit var tempDir: Path

    private lateinit var aesKey: SecretKey
    private lateinit var vaultFilePath: String
    private lateinit var vault: SecureJsonVault
    private val testJson = """{"name":"test-user", "id":123}"""

    @BeforeEach
    fun setUp() {
        // Generate a 256-bit AES key
        val keyGen = KeyGenerator.getInstance("AES")
        keyGen.init(256)
        aesKey = keyGen.generateKey()

        vaultFilePath = tempDir.resolve("test.vault").pathString
        vault = SecureJsonVault(aesKey, vaultFilePath)
    }

    @Test
    fun constructor_shouldThrowExceptionForNonAesKey() {
        // Generate a DES key (not AES)
        val keyGen = KeyGenerator.getInstance("DES")
        keyGen.init(56)
        val desKey = keyGen.generateKey()

        assertThatIllegalArgumentException()
            .isThrownBy { SecureJsonVault(desKey, vaultFilePath) }
            .withMessage("Key must be an AES key for this vault.")
    }

    @Test
    fun saveData_shouldCreateEncryptedFile() {
        vault.saveData(testJson)

        val vaultFile = File(vaultFilePath)
        assertThat(vaultFile).exists().isFile.isNotEmpty

        // Check that content is not plaintext
        val fileContent = Files.readAllBytes(vaultFile.toPath())
        val fileString = String(fileContent)
        assertThat(fileString).doesNotContain(testJson)
    }

    @Test
    fun loadData_shouldDecryptDataSuccessfully() {
        // 1. Save
        vault.saveData(testJson)

        // 2. Load
        val loadedData = vault.loadData()

        // 3. Assert
        assertThat(loadedData).isEqualTo(testJson)
    }

    @Test
    fun loadData_shouldThrowExceptionIfFileDoesNotExist() {
        // Don't save, just try to load
        assertThatThrownBy { vault.loadData() }
            .isInstanceOf(FileNotFoundException::class.java)
            .hasMessageContaining("Vault file not found")
    }

    @Test
    fun saveData_shouldOverwriteExistingData() {
        val json1 = """{"data":"first"}"""
        val json2 = """{"data":"second"}"""

        // 1. Save first time
        vault.saveData(json1)
        val loaded1 = vault.loadData()
        assertThat(loaded1).isEqualTo(json1)

        // 2. Save second time (overwrite)
        vault.saveData(json2)
        val loaded2 = vault.loadData()
        assertThat(loaded2).isEqualTo(json2)
    }

    @Test
    fun loadData_shouldThrowExceptionIfDataIsTampered() {
        // 1. Save good data
        vault.saveData(testJson)

        // 2. Read raw bytes and tamper with the ciphertext
        val originalBytes = Files.readAllBytes(Path.of(vaultFilePath))

        // File format is: [IV_LENGTH (int 4 bytes)][IV (12 bytes)][CIPHERTEXT]
        val ivLength = 12
        val ciphertextStartIndex = 4 + ivLength

        // Make sure we have ciphertext to tamper with
        assertThat(originalBytes.size).isGreaterThan(ciphertextStartIndex)

        // Copy and tamper
        val tamperedBytes = originalBytes.copyOf()
        // Flip a bit. Note: Bytes in Kotlin are signed, math creates Int, so we cast back.
        tamperedBytes[ciphertextStartIndex] = (tamperedBytes[ciphertextStartIndex] + 1).toByte()

        // 3. Write tampered data back to file
        Files.write(Path.of(vaultFilePath), tamperedBytes)

        // 4. Try to load
        // GCM's authentication tag check should fail
        assertThatThrownBy { vault.loadData() }
            .isInstanceOf(AEADBadTagException::class.java)
    }

    @Test
    fun loadData_shouldThrowExceptionIfIvIsTampered() {
        // 1. Save good data
        vault.saveData(testJson)

        // 2. Read raw bytes and tamper with the IV
        val originalBytes = Files.readAllBytes(Path.of(vaultFilePath))

        // File format is: [IV_LENGTH (int 4 bytes)][IV (12 bytes)][CIPHERTEXT]
        // Let's flip the first byte of IV (index 4).
        val ivStartIndex = 4

        // Copy and tamper
        val tamperedBytes = originalBytes.copyOf()
        tamperedBytes[ivStartIndex] = (tamperedBytes[ivStartIndex] + 1).toByte()

        // 3. Write tampered data back
        Files.write(Path.of(vaultFilePath), tamperedBytes)

        // 4. Try to load
        // Decryption should fail because the IV is wrong (tag mismatch usually)
        assertThatThrownBy { vault.loadData() }
            .isInstanceOf(AEADBadTagException::class.java)
    }

    @Test
    fun loadData_shouldThrowExceptionForInvalidIvLength() {
        // Manually write a file with an invalid IV length
        FileOutputStream(vaultFilePath).use { fos ->
            DataOutputStream(fos).use { dos ->
                dos.writeInt(99) // Invalid length (should be 12)
                dos.write(byteArrayOf(1, 2, 3))
            }
        }

        assertThatThrownBy { vault.loadData() }
            .isInstanceOf(SecurityException::class.java)
            .hasMessage("Invalid IV length in vault file.")
    }
}