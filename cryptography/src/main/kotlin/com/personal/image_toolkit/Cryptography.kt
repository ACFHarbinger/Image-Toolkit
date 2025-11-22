package com.personal.image_toolkit

import java.security.KeyStore
import java.util.Arrays
import javax.crypto.SecretKey

/**
 * The default filename for the KeyStore file.
 */
private const val KEYSTORE_FILE = "my_keystore.p12"

/**
 * The password for protecting the integrity of the KeyStore file.
 */
private val KEYSTORE_PASSWORD = "changeit".toCharArray()

/**
 * The password for protecting the individual key entries within the KeyStore.
 */
private val KEY_PASSWORD = "my_key_password".toCharArray()

/**
 * The main entry point demonstrating the KeyStore operations.
 */
fun main() {
    try {
        val manager = KeyStoreManager()

        // 1. Load or create the keystore
        val keyStore = manager.loadKeyStore(KEYSTORE_FILE, KEYSTORE_PASSWORD)

        // 2. Define an alias for our new key
        val secretKeyAlias = "my-secret-key"

        // 3. Store a secret key if it doesn't exist
        if (!keyStore.containsAlias(secretKeyAlias)) {
            println("Generating and storing a new secret key...")
            manager.storeSecretKey(keyStore, secretKeyAlias, KEY_PASSWORD)

            // 4. Save the keystore to persist the new key
            manager.saveKeyStore(keyStore, KEYSTORE_FILE, KEYSTORE_PASSWORD)
            println("Secret key stored and keystore saved.")
        } else {
            println("Secret key already exists.")
        }

        // 5. Retrieve the secret key
        println("\nRetrieving secret key...")
        val retrievedKey: SecretKey? = manager.getSecretKey(keyStore, secretKeyAlias, KEY_PASSWORD)
        if (retrievedKey == null) {
            System.err.println("Could not retrieve secret key. Exiting.")
            return
        }
        println("Successfully retrieved key!")

        // --- NEW: Using SecureJsonVault ---
        println("\n--- Testing SecureJsonVault ---")
        val vaultFilePath = "user_data.vault"

        // 6. Initialize the vault with the key from the KeyStore
        val vault = SecureJsonVault(retrievedKey, vaultFilePath)

        // 7. Create some dummy JSON data and save it
        val sampleJson = """
            {
              "username": "ACFPeacekeeper",
              "userId": 12345,
              "preferences": {
                "theme": "dark",
                "notifications": true
              }
            }
        """.trimIndent()

        try {
            vault.saveData(sampleJson)
        } catch (e: Exception) {
            System.err.println("Error saving vault: " + e.message)
            e.printStackTrace()
        }

        // 8. Load the data back from the encrypted file
        try {
            val loadedJson = vault.loadData()
            println("Successfully loaded and decrypted data:")
            println(loadedJson)
        } catch (e: Exception) {
            System.err.println("Error loading vault: " + e.message)
            e.printStackTrace()
        }
        // ------------------------------------

    } catch (e: Exception) {
        e.printStackTrace()
    } finally {
        // Security best practice: clear passwords from memory
        Arrays.fill(KEYSTORE_PASSWORD, ' ')
        Arrays.fill(KEY_PASSWORD, ' ')
    }
}