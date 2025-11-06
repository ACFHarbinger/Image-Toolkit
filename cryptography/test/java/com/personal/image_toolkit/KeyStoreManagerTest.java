package com.personal.image_toolkit;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.io.*;
import java.nio.file.Path;
import java.security.KeyStore;
import java.security.KeyStoreException;
import java.security.UnrecoverableEntryException;
import java.security.cert.Certificate;
import java.util.Collections;
import static org.assertj.core.api.Assertions.*;

class KeyStoreManagerTest {

    @TempDir
    Path tempDir;

    private String keyStoreFile;
    private char[] keyStorePassword;
    private char[] keyPassword;
    private KeyStoreManager keyStoreManager;

    // For capturing System.out
    private final ByteArrayOutputStream outContent = new ByteArrayOutputStream();
    private final PrintStream originalOut = System.out;

    @BeforeEach
    void setUp() {
        keyStoreFile = tempDir.resolve("test.p12").toString();
        keyStorePassword = "storePassword".toCharArray();
        keyPassword = "keyPassword".toCharArray();
        keyStoreManager = new KeyStoreManager(); // For non-static methods

        // Redirect System.out to capture console output for listEntries
        System.setOut(new PrintStream(outContent));
    }

    @AfterEach
    void tearDown() {
        // Restore System.out
        System.setOut(originalOut);
    }

    @Test
    void loadKeyStore_shouldCreateNewKeyStoreIfFileDoesNotExist() throws Exception {
        KeyStore keyStore = KeyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword);
        
        assertThat(keyStore).isNotNull();
        assertThat(Collections.list(keyStore.aliases())).isEmpty();
        assertThat(outContent.toString()).contains("Created new empty keystore");
    }

    @Test
    void saveAndLoadKeyStore_shouldPreserveEntries() throws Exception {
        // 1. Create and save a keystore
        KeyStore keyStore = KeyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword);
        KeyStoreManager.storeSecretKey(keyStore, "my-secret-key", keyPassword);
        KeyStoreManager.saveKeyStore(keyStore, keyStoreFile, keyStorePassword);
        
        assertThat(new File(keyStoreFile)).exists();
        
        // 2. Load the existing keystore
        KeyStore loadedKeyStore = KeyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword);
        
        assertThat(loadedKeyStore).isNotNull();
        assertThat(loadedKeyStore.containsAlias("my-secret-key")).isTrue();
        assertThat(outContent.toString()).contains("Loaded existing keystore");
    }

    @Test
    void loadKeyStore_shouldThrowExceptionForIncorrectPassword() throws Exception {
        // 1. Create and save a keystore
        KeyStore keyStore = KeyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword);
        KeyStoreManager.saveKeyStore(keyStore, keyStoreFile, keyStorePassword);
        
        // 2. Try to load with wrong password
        char[] wrongPassword = "wrong".toCharArray();
        
        assertThatThrownBy(() -> KeyStoreManager.loadKeyStore(keyStoreFile, wrongPassword))
            .isInstanceOf(IOException.class)
            .hasMessageContaining("keystore password was incorrect");
    }

    @Test
    void storeAndGetSecretKey_shouldRetrieveSameKey() throws Exception {
        KeyStore keyStore = KeyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword);
        String alias = "aes-key";
        
        KeyStoreManager.storeSecretKey(keyStore, alias, keyPassword);
        
        javax.crypto.SecretKey retrievedKey = KeyStoreManager.getSecretKey(keyStore, alias, keyPassword);
        
        assertThat(retrievedKey).isNotNull();
        assertThat(retrievedKey.getAlgorithm()).isEqualTo("AES");
        assertThat(retrievedKey.getEncoded().length).isEqualTo(32); // 256 bits
    }

    @Test
    void getSecretKey_shouldReturnNullForNonExistentAlias() throws Exception {
        KeyStore keyStore = KeyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword);
        javax.crypto.SecretKey retrievedKey = KeyStoreManager.getSecretKey(keyStore, "non-existent", keyPassword);
        
        assertThat(retrievedKey).isNull();
        assertThat(outContent.toString()).contains("No entry found for alias: non-existent");
    }

    @Test
    void getSecretKey_shouldThrowExceptionForIncorrectKeyPassword() throws Exception {
        KeyStore keyStore = KeyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword);
        String alias = "aes-key";
        KeyStoreManager.storeSecretKey(keyStore, alias, keyPassword);
        
        char[] wrongKeyPassword = "wrong".toCharArray();
        
        assertThatThrownBy(() -> KeyStoreManager.getSecretKey(keyStore, alias, wrongKeyPassword))
            .isInstanceOf(UnrecoverableEntryException.class);
    }
    
    @Test
    void generatePrivateKeyEntry_shouldCreateValidEntry() throws Exception {
        String alias = "rsa-key";
        PrivateKeyEntryData data = KeyStoreManager.generatePrivateKeyEntry(alias, keyPassword);

        assertThat(data).isNotNull();
        assertThat(data.getAlias()).isEqualTo(alias);
        assertThat(data.getKeyPassword()).isEqualTo(keyPassword);
        assertThat(data.getPrivateKey()).isNotNull();
        assertThat(data.getPrivateKey().getAlgorithm()).isEqualTo("RSA");
        assertThat(data.getCertificateChain()).isNotNull().hasSize(1);
        assertThat(data.getCertificateChain()[0]).isNotNull().isInstanceOf(Certificate.class);
    }

    @Test
    void storePrivateKeyEntry_shouldStoreEntryAndClearPassword() throws Exception {
        KeyStore keyStore = KeyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword);
        String alias = "rsa-key";
        char[] originalPassword = new char[]{'s', 'e', 'c', 'r', 'e', 't'};
        
        PrivateKeyEntryData data = KeyStoreManager.generatePrivateKeyEntry(alias, originalPassword);
        
        // Act
        keyStoreManager.storePrivateKeyEntry(keyStore, data);
        
        // Assert
        assertThat(keyStore.isKeyEntry(alias)).isTrue();
        assertThat(outContent.toString()).contains("Stored private key for alias: " + alias);
        
        // Verify the password in the original data object was cleared
        assertThat(originalPassword).containsOnly(' ');
    }

    @Test
    void storeTrustedCertificate_shouldStoreEntry() throws Exception {
        KeyStore keyStore = KeyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword);
        String alias = "trusted-cert";
        
        // Re-use generator to get a certificate
        PrivateKeyEntryData pkeData = KeyStoreManager.generatePrivateKeyEntry("temp", "temp".toCharArray());
        Certificate cert = pkeData.getCertificateChain()[0];
        
        TrustedCertificateEntryData data = new TrustedCertificateEntryData(alias, cert);
        
        // Act
        keyStoreManager.storeTrustedCertificate(keyStore, data);
        
        // Assert
        assertThat(keyStore.isCertificateEntry(alias)).isTrue();
        assertThat(keyStore.getCertificate(alias)).isEqualTo(cert);
        assertThat(outContent.toString()).contains("Stored trusted certificate for alias: " + alias);
    }

    @Test
    void listEntries_shouldListAllEntriesCorrectly() throws Exception {
        KeyStore keyStore = KeyStoreManager.loadKeyStore(keyStoreFile, keyStorePassword);
        
        // 1. Test empty keystore
        KeyStoreManager.listEntries(keyStore);
        assertThat(outContent.toString()).contains("Keystore is empty.");
        
        outContent.reset(); // Clear the output stream
        
        // 2. Add entries
        KeyStoreManager.storeSecretKey(keyStore, "secret-key", keyPassword);
        
        PrivateKeyEntryData pkeData = KeyStoreManager.generatePrivateKeyEntry("private-key", keyPassword);
        keyStoreManager.storePrivateKeyEntry(keyStore, pkeData);
        
        TrustedCertificateEntryData tcData = new TrustedCertificateEntryData("trusted-cert", pkeData.getCertificateChain()[0]);
        keyStoreManager.storeTrustedCertificate(keyStore, tcData);

        outContent.reset(); // Clear output from store methods
        
        // 3. Test listing
        KeyStoreManager.listEntries(keyStore);
        String output = outContent.toString();
        
        assertThat(output)
            .contains("Alias: secret-key (Key Entry)")
            .contains("Alias: private-key (Key Entry)")
            .contains("Alias: trusted-cert (Certificate Entry)");
    }
}