package com.personal.image_toolkit;

import java.security.KeyStore;
import javax.crypto.SecretKey;

import com.personal.image_toolkit.KeyStoreManager;
import com.personal.image_toolkit.SecureJsonVault;

/**
 * Hello world!
 *
 */
public class Cryptography 
{
    /**
     * The default filename for the KeyStore file.
     */
    private static final String KEYSTORE_FILE = "my_keystore.p12";

    /**
     * The password for protecting the integrity of the KeyStore file.
     * Stored as a {@code char[]} for security best practices.
     */
    private static final char[] KEYSTORE_PASSWORD = "changeit".toCharArray();

    /**
     * The password for protecting the individual key entries within the KeyStore.
     * Stored as a {@code char[]} for security best practices.
     */
    private static final char[] KEY_PASSWORD = "my_key_password".toCharArray();

    /**
     * The main method demonstrating the KeyStore operations.
     *
     * @param args Command line arguments (unused).
     */
    public static void main(String[] args) {
        try {
            // FIX: Create an instance of KeyStoreManager to call its non-static methods.
            KeyStoreManager manager = new KeyStoreManager();
            
            // 1. Load or create the keystore
            // FIX: Call the method on the instance 'manager'
            KeyStore keyStore = manager.loadKeyStore(KEYSTORE_FILE, KEYSTORE_PASSWORD);

            // 2. Define an alias for our new key
            String secretKeyAlias = "my-secret-key";

            // 3. Store a secret key if it doesn't exist
            if (!keyStore.containsAlias(secretKeyAlias)) {
                System.out.println("Generating and storing a new secret key...");
                // FIX: Call the method on the instance 'manager'
                manager.storeSecretKey(keyStore, secretKeyAlias, KEY_PASSWORD);
                
                // 4. Save the keystore to persist the new key
                // FIX: Call the method on the instance 'manager'
                manager.saveKeyStore(keyStore, KEYSTORE_FILE, KEYSTORE_PASSWORD);
                System.out.println("Secret key stored and keystore saved.");
            } else {
                System.out.println("Secret key already exists.");
            }

            // 5. Retrieve the secret key
            System.out.println("\nRetrieving secret key...");
            // FIX: Call the method on the instance 'manager'
            SecretKey retrievedKey = manager.getSecretKey(keyStore, secretKeyAlias, KEY_PASSWORD);
            if (retrievedKey == null) {
                System.err.println("Could not retrieve secret key. Exiting.");
                return;
            }
            System.out.println("Successfully retrieved key!");
            

            // --- NEW: Using SecureJsonVault ---
            System.out.println("\n--- Testing SecureJsonVault ---");
            String vaultFilePath = "user_data.vault";
            
            // 6. Initialize the vault with the key from the KeyStore
            SecureJsonVault vault = new SecureJsonVault(retrievedKey, vaultFilePath);
            
            // 7. Create some dummy JSON data and save it
            String sampleJson = "{\n" +
                                "  \"username\": \"ACFPeacekeeper\",\n" +
                                "  \"userId\": 12345,\n" +
                                "  \"preferences\": {\n" +
                                "    \"theme\": \"dark\",\n" +
                                "    \"notifications\": true\n" +
                                "  }\n" +
                                "}";
            
            try {
                vault.saveData(sampleJson);
            } catch (Exception e) {
                System.err.println("Error saving vault: " + e.getMessage());
                e.printStackTrace();
            }

            // 8. Load the data back from the encrypted file
            try {
                String loadedJson = vault.loadData();
                System.out.println("Successfully loaded and decrypted data:");
                System.out.println(loadedJson);
            } catch (Exception e) {
                System.err.println("Error loading vault: " + e.getMessage());
                e.printStackTrace();
            }
            // ------------------------------------

        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            // Security best practice: clear passwords from memory
            java.util.Arrays.fill(KEYSTORE_PASSWORD, ' ');
            java.util.Arrays.fill(KEY_PASSWORD, ' ');
        }
    }
}