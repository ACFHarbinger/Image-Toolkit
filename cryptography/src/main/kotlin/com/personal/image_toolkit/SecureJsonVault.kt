package com.personal.image_toolkit

import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.charset.StandardCharsets
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Manages an encrypted file vault for storing and retrieving sensitive data
 * as a JSON string.
 *
 * This class uses AES/GCM (Galois/Counter Mode), which is an authenticated
 * encryption (AEAD) mode. It encrypts the data and also provides integrity
 * and authenticity, protecting it from being tampered with.
 */
class SecureJsonVault(
    private val secretKey: SecretKey,
    vaultFilePath: String
) : SecureJsonVaultInterface {

    private val vaultFile: File = File(vaultFilePath)
    private val secureRandom: SecureRandom = SecureRandom()

    init {
        if (!secretKey.algorithm.equals("AES", ignoreCase = true)) {
            throw IllegalArgumentException("Key must be an AES key for this vault.")
        }
    }

    companion object {
        /**
         * The algorithm specification for authenticated encryption.
         * AES/GCM/NoPadding is the modern standard.
         */
        private const val ALGORITHM = "AES/GCM/NoPadding"

        /**
         * The recommended length for the GCM Initialization Vector (IV) in bytes.
         * 96 bits (12 bytes) is standard for GCM.
         */
        private const val GCM_IV_LENGTH_BYTES = 12

        /**
         * The length of the GCM authentication tag in bits.
         * 128 bits is standard for high security.
         */
        private const val GCM_TAG_LENGTH_BITS = 128
    }

    /**
     * Encrypts a JSON string and saves it to the vault file.
     *
     * The file format is: [IV_LENGTH (int)][IV_DATA][ENCRYPTED_DATA]
     *
     * @param jsonData The plaintext JSON string to save.
     * @throws Exception If an encryption or I/O error occurs.
     */
    @Throws(Exception::class)
    override fun saveData(jsonData: String) {
        // 1. Generate a new, unique Initialization Vector (IV) for each encryption.
        val iv = ByteArray(GCM_IV_LENGTH_BYTES)
        secureRandom.nextBytes(iv)

        // 2. Get a Cipher instance
        val cipher = Cipher.getInstance(ALGORITHM)

        // 3. Create the GCM parameters with the IV and tag length
        val gcmSpec = GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv)

        // 4. Initialize the cipher for encryption
        cipher.init(Cipher.ENCRYPT_MODE, secretKey, gcmSpec)

        // 5. Encrypt the data
        val plainTextBytes = jsonData.toByteArray(StandardCharsets.UTF_8)
        val cipherText = cipher.doFinal(plainTextBytes)

        // 6. Write the IV and the ciphertext to the file using use block (try-with-resources)
        FileOutputStream(vaultFile).use { fos ->
            DataOutputStream(fos).use { dos ->
                // Write the IV length (so we know how much to read back)
                dos.writeInt(iv.size)
                // Write the IV itself
                dos.write(iv)
                // Write the encrypted data
                dos.write(cipherText)
            }
        }
        println("Secure data saved to: " + vaultFile.absolutePath)
    }

    /**
     * Loads and decrypts the JSON data from the vault file.
     *
     * @return The plaintext JSON string.
     * @throws Exception If the file doesn't exist, or if decryption or I/O fails.
     * A failure here can also mean the data was tampered with
     * (AuthenticationTagMismatchException).
     */
    @Throws(Exception::class)
    override fun loadData(): String {
        if (!vaultFile.exists()) {
            throw java.io.FileNotFoundException("Vault file not found: " + vaultFile.absolutePath)
        }

        val iv: ByteArray
        val cipherText: ByteArray

        // 1. Read the IV and ciphertext from the file using use block
        FileInputStream(vaultFile).use { fis ->
            DataInputStream(fis).use { dis ->
                val ivLength = dis.readInt()
                if (ivLength != GCM_IV_LENGTH_BYTES) {
                    throw SecurityException("Invalid IV length in vault file.")
                }
                iv = ByteArray(ivLength)
                dis.readFully(iv)

                // Read the remaining bytes as the ciphertext
                cipherText = dis.readBytes()
            }
        }

        // 2. Get a Cipher instance
        val cipher = Cipher.getInstance(ALGORITHM)

        // 3. Create the GCM parameters from the loaded IV
        val gcmSpec = GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv)

        // 4. Initialize the cipher for decryption
        cipher.init(Cipher.DECRYPT_MODE, secretKey, gcmSpec)

        // 5. Decrypt the data
        val plainTextBytes = cipher.doFinal(cipherText)

        // 6. Return the data as a string
        return String(plainTextBytes, StandardCharsets.UTF_8)
    }
}