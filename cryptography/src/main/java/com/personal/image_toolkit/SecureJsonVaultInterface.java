package com.personal.image_toolkit;

/**
 * Defines the contract for securely saving and loading data using authenticated encryption (AES/GCM).
 */
public interface SecureJsonVaultInterface {

    /**
     * Encrypts the provided JSON data and saves it to the vault file.
     *
     * @param jsonData The string data (e.g., a JSON payload) to be encrypted and saved.
     * @throws Exception If an encryption or file writing error occurs.
     */
    void saveData(String jsonData) throws Exception;

    /**
     * Loads the encrypted data from the vault file and decrypts it.
     *
     * @return The decrypted JSON data string.
     * @throws Exception If a file reading, decryption, or authentication error occurs.
     * (An authentication error means the data was tampered with or the key is wrong).
     */
    String loadData() throws Exception;
}