package com.personal.image_toolkit;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Manages an encrypted file vault for storing and retrieving sensitive data
 * as a JSON string.
 *
 * This class uses AES/GCM (Galois/Counter Mode), which is an authenticated
 * encryption (AEAD) mode. It encrypts the data and also provides integrity
 * and authenticity, protecting it from being tampered with.
 */
public class SecureJsonVault {

    /**
     * The algorithm specification for authenticated encryption.
     * AES/GCM/NoPadding is the modern standard.
     */
    private static final String ALGORITHM = "AES/GCM/NoPadding";
    
    /**
     * The recommended length for the GCM Initialization Vector (IV) in bytes.
     * 96 bits (12 bytes) is standard for GCM.
     */
    private static final int GCM_IV_LENGTH_BYTES = 12;
    
    /**
     * The length of the GCM authentication tag in bits.
     * 128 bits is standard for high security.
     */
    private static final int GCM_TAG_LENGTH_BITS = 128;

    private final SecretKey secretKey;
    private final File vaultFile;
    private final SecureRandom secureRandom;

    /**
     * Creates a new SecureJsonVault instance linked to a specific file.
     *
     * @param secretKey The AES {@code SecretKey} used for encryption and decryption.
     * @param vaultFilePath The path to the file where the encrypted data will be stored.
     */
    public SecureJsonVault(SecretKey secretKey, String vaultFilePath) {
        if (!secretKey.getAlgorithm().equalsIgnoreCase("AES")) {
            throw new IllegalArgumentException("Key must be an AES key for this vault.");
        }
        this.secretKey = secretKey;
        this.vaultFile = new File(vaultFilePath);
        this.secureRandom = new SecureRandom();
    }

    /**
     * Encrypts a JSON string and saves it to the vault file.
     *
     * The file format is: [IV_LENGTH (int)][IV_DATA][ENCRYPTED_DATA]
     *
     * @param jsonData The plaintext JSON string to save.
     * @throws Exception If an encryption or I/O error occurs.
     */
    public void saveData(String jsonData) throws Exception {
        // 1. Generate a new, unique Initialization Vector (IV) for each encryption.
        // This is critical for GCM's security.
        byte[] iv = new byte[GCM_IV_LENGTH_BYTES];
        secureRandom.nextBytes(iv);
        
        // 2. Get a Cipher instance
        Cipher cipher = Cipher.getInstance(ALGORITHM);
        
        // 3. Create the GCM parameters with the IV and tag length
        GCMParameterSpec gcmSpec = new GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv);
        
        // 4. Initialize the cipher for encryption
        cipher.init(Cipher.ENCRYPT_MODE, secretKey, gcmSpec);
        
        // 5. Encrypt the data
        byte[] plainTextBytes = jsonData.getBytes(StandardCharsets.UTF_8);
        byte[] cipherText = cipher.doFinal(plainTextBytes);
        
        // 6. Write the IV and the ciphertext to the file
        try (FileOutputStream fos = new FileOutputStream(vaultFile);
             DataOutputStream dos = new DataOutputStream(fos)) {
            
            // Write the IV length (so we know how much to read back)
            dos.writeInt(iv.length);
            // Write the IV itself
            dos.write(iv);
            // Write the encrypted data
            dos.write(cipherText);
        }
        System.out.println("Secure data saved to: " + vaultFile.getAbsolutePath());
    }

    /**
     * Loads and decrypts the JSON data from the vault file.
     *
     * @return The plaintext JSON string.
     * @throws Exception If the file doesn't exist, or if decryption or I/O fails.
     * A failure here can also mean the data was tampered with
     * (AuthenticationTagMismatchException).
     */
    public String loadData() throws Exception {
        if (!vaultFile.exists()) {
            throw new java.io.FileNotFoundException("Vault file not found: " + vaultFile.getAbsolutePath());
        }

        byte[] iv;
        byte[] cipherText;

        // 1. Read the IV and ciphertext from the file
        try (FileInputStream fis = new FileInputStream(vaultFile);
             DataInputStream dis = new DataInputStream(fis)) {

            int ivLength = dis.readInt();
            if (ivLength != GCM_IV_LENGTH_BYTES) {
                throw new SecurityException("Invalid IV length in vault file.");
            }
            iv = new byte[ivLength];
            dis.readFully(iv);
            
            // Read the remaining bytes as the ciphertext
            cipherText = dis.readAllBytes();
        }

        // 2. Get a Cipher instance
        Cipher cipher = Cipher.getInstance(ALGORITHM);
        
        // 3. Create the GCM parameters from the loaded IV
        GCMParameterSpec gcmSpec = new GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv);
        
        // 4. Initialize the cipher for decryption
        cipher.init(Cipher.DECRYPT_MODE, secretKey, gcmSpec);
        
        // 5. Decrypt the data
        byte[] plainTextBytes = cipher.doFinal(cipherText);
        
        // 6. Return the data as a string
        return new String(plainTextBytes, StandardCharsets.UTF_8);
    }
}