package com.personal.image_toolkit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.AEADBadTagException;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileNotFoundException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import static org.assertj.core.api.Assertions.*;

class SecureJsonVaultTest {

    @TempDir
    Path tempDir;

    private SecretKey aesKey;
    private String vaultFilePath;
    private SecureJsonVault vault;
    private final String testJson = "{\"name\":\"test-user\", \"id\":123}";

    @BeforeEach
    void setUp() throws Exception {
        // Generate a 256-bit AES key
        KeyGenerator keyGen = KeyGenerator.getInstance("AES");
        keyGen.init(256);
        aesKey = keyGen.generateKey();

        vaultFilePath = tempDir.resolve("test.vault").toString();
        vault = new SecureJsonVault(aesKey, vaultFilePath);
    }

    @Test
    void constructor_shouldThrowExceptionForNonAesKey() throws Exception {
        // Generate a DES key (not AES)
        KeyGenerator keyGen = KeyGenerator.getInstance("DES");
        keyGen.init(56);
        SecretKey desKey = keyGen.generateKey();

        assertThatIllegalArgumentException()
                .isThrownBy(() -> new SecureJsonVault(desKey, vaultFilePath))
                .withMessage("Key must be an AES key for this vault.");
    }

    @Test
    void saveData_shouldCreateEncryptedFile() throws Exception {
        vault.saveData(testJson);
        
        File vaultFile = new File(vaultFilePath);
        assertThat(vaultFile).exists().isFile().isNotEmpty();
        
        // Check that content is not plaintext
        byte[] fileContent = Files.readAllBytes(vaultFile.toPath());
        String fileString = new String(fileContent);
        assertThat(fileString).doesNotContain(testJson);
    }

    @Test
    void loadData_shouldDecryptDataSuccessfully() throws Exception {
        // 1. Save
        vault.saveData(testJson);
        
        // 2. Load
        String loadedData = vault.loadData();
        
        // 3. Assert
        assertThat(loadedData).isEqualTo(testJson);
    }

    @Test
    void loadData_shouldThrowExceptionIfFileDoesNotExist() {
        // Don't save, just try to load
        assertThatThrownBy(() -> vault.loadData())
                .isInstanceOf(FileNotFoundException.class)
                .hasMessageContaining("Vault file not found");
    }

    @Test
    void saveData_shouldOverwriteExistingData() throws Exception {
        String json1 = "{\"data\":\"first\"}";
        String json2 = "{\"data\":\"second\"}";

        // 1. Save first time
        vault.saveData(json1);
        String loaded1 = vault.loadData();
        assertThat(loaded1).isEqualTo(json1);

        // 2. Save second time (overwrite)
        vault.saveData(json2);
        String loaded2 = vault.loadData();
        assertThat(loaded2).isEqualTo(json2);
    }

    @Test
    void loadData_shouldThrowExceptionIfDataIsTampered() throws Exception {
        // 1. Save good data
        vault.saveData(testJson);
        
        // 2. Read raw bytes and tamper with the ciphertext
        byte[] originalBytes = Files.readAllBytes(Path.of(vaultFilePath));
        
        // File format is: [IV_LENGTH (int 4 bytes)][IV (12 bytes)][CIPHERTEXT]
        // We want to flip a bit in the ciphertext, not the IV.
        // Let's flip the first byte of ciphertext.
        int ivLength = 12;
        int ciphertextStartIndex = 4 + ivLength; 
        
        // Make sure we have ciphertext to tamper with
        assertThat(originalBytes.length).isGreaterThan(ciphertextStartIndex);

        // Copy and tamper
        byte[] tamperedBytes = Arrays.copyOf(originalBytes, originalBytes.length);
        tamperedBytes[ciphertextStartIndex] = (byte) (tamperedBytes[ciphertextStartIndex] + 1); // Flip a bit
        
        // 3. Write tampered data back to file
        Files.write(Path.of(vaultFilePath), tamperedBytes);
        
        // 4. Try to load
        // GCM's authentication tag check should fail
        assertThatThrownBy(() -> vault.loadData())
            .isInstanceOf(AEADBadTagException.class);
    }

    @Test
    void loadData_shouldThrowExceptionIfIvIsTampered() throws Exception {
        // 1. Save good data
        vault.saveData(testJson);

        // 2. Read raw bytes and tamper with the IV
        byte[] originalBytes = Files.readAllBytes(Path.of(vaultFilePath));

        // File format is: [IV_LENGTH (int 4 bytes)][IV (12 bytes)][CIPHERTEXT]
        // We want to flip a bit in the IV.
        // Let's flip the first byte of IV (index 4).
        int ivStartIndex = 4;
        
        // Copy and tamper
        byte[] tamperedBytes = Arrays.copyOf(originalBytes, originalBytes.length);
        tamperedBytes[ivStartIndex] = (byte) (tamperedBytes[ivStartIndex] + 1); // Flip a bit
        
        // 3. Write tampered data back
        Files.write(Path.of(vaultFilePath), tamperedBytes);

        // 4. Try to load
        // Decryption should fail because the IV is wrong
        assertThatThrownBy(() -> vault.loadData())
            .isInstanceOf(AEADBadTagException.class);
    }

    @Test
    void loadData_shouldThrowExceptionForInvalidIvLength() throws Exception {
        // Manually write a file with an invalid IV length
        try (FileOutputStream fos = new FileOutputStream(vaultFilePath);
             DataOutputStream dos = new DataOutputStream(fos)) {
            
            dos.writeInt(99); // Invalid length (should be 12)
            dos.write(new byte[]{1, 2, 3});
        }
        
        assertThatThrownBy(() -> vault.loadData())
            .isInstanceOf(SecurityException.class)
            .hasMessage("Invalid IV length in vault file.");
    }
}