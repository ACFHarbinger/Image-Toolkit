package com.personal.image_toolkit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.NoSuchAlgorithmException;
import java.security.PrivateKey;
import java.security.cert.Certificate;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.mock;

class PrivateKeyEntryDataTest {

    private String alias;
    private PrivateKey privateKey;
    private Certificate[] certificateChain;
    private char[] keyPassword;

    @BeforeEach
    void setUp() throws NoSuchAlgorithmException {
        alias = "test-alias";
        // Generate a dummy key pair
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
        kpg.initialize(512); // Use 512 for speed in tests
        KeyPair kp = kpg.generateKeyPair();
        privateKey = kp.getPrivate();
        
        // Mock a certificate chain
        certificateChain = new Certificate[]{mock(Certificate.class)};
        keyPassword = new char[]{'p', 'a', 's', 's'};
    }

    @Test
    void constructor_shouldSucceedWithValidArgs() {
        PrivateKeyEntryData data = new PrivateKeyEntryData(alias, privateKey, certificateChain, keyPassword);
        assertThat(data.getAlias()).isEqualTo(alias);
        assertThat(data.getPrivateKey()).isEqualTo(privateKey);
        assertThat(data.getCertificateChain()).isEqualTo(certificateChain);
        assertThat(data.getKeyPassword()).isEqualTo(keyPassword);
    }

    @Test
    void constructor_shouldThrowExceptionForNullAlias() {
        assertThatNullPointerException()
                .isThrownBy(() -> new PrivateKeyEntryData(null, privateKey, certificateChain, keyPassword))
                .withMessage("Alias cannot be null.");
    }

    @Test
    void constructor_shouldThrowExceptionForNullPrivateKey() {
        assertThatNullPointerException()
                .isThrownBy(() -> new PrivateKeyEntryData(alias, null, certificateChain, keyPassword))
                .withMessage("PrivateKey cannot be null.");
    }

    @Test
    void constructor_shouldThrowExceptionForNullCertificateChain() {
        assertThatNullPointerException()
                .isThrownBy(() -> new PrivateKeyEntryData(alias, privateKey, null, keyPassword))
                .withMessage("Certificate chain cannot be null.");
    }

    @Test
    void constructor_shouldThrowExceptionForNullKeyPassword() {
        assertThatNullPointerException()
                .isThrownBy(() -> new PrivateKeyEntryData(alias, privateKey, certificateChain, null))
                .withMessage("Key password cannot be null.");
    }

    @Test
    void getCertificateChain_shouldReturnDefensiveCopy() {
        PrivateKeyEntryData data = new PrivateKeyEntryData(alias, privateKey, certificateChain, keyPassword);
        Certificate[] retrievedChain = data.getCertificateChain();

        assertThat(retrievedChain).isEqualTo(certificateChain);
        assertThat(retrievedChain).isNotSameAs(certificateChain);

        // Modify the retrieved copy
        retrievedChain[0] = null;

        // Check that the internal array is unchanged
        assertThat(data.getCertificateChain()[0]).isNotNull();
    }

    @Test
    void getKeyPassword_shouldReturnDefensiveCopy() {
        PrivateKeyEntryData data = new PrivateKeyEntryData(alias, privateKey, certificateChain, keyPassword);
        char[] retrievedPassword = data.getKeyPassword();

        assertThat(retrievedPassword).isEqualTo(keyPassword);
        assertThat(retrievedPassword).isNotSameAs(keyPassword);

        // Modify the retrieved copy
        retrievedPassword[0] = 'X';

        // Check that the internal array is unchanged by getting a new clone
        assertThat(data.getKeyPassword()[0]).isEqualTo('p');
        // Check that the original array is also unchanged
        assertThat(keyPassword[0]).isEqualTo('p');
    }

    @Test
    void clearPassword_shouldWipeTheInternalPasswordArray() {
        // Use a fresh array for this test to check its state
        char[] originalPasswordArray = new char[]{'p', 'a', 's', 's'};
        PrivateKeyEntryData data = new PrivateKeyEntryData(alias, privateKey, certificateChain, originalPasswordArray);

        // Act
        data.clearPassword();

        // Assert
        // The original array reference passed to the constructor should be cleared
        assertThat(originalPasswordArray).containsOnly(' ');

        // A new copy retrieved from the getter should also reflect this cleared state
        char[] passwordAfterClear = data.getKeyPassword();
        assertThat(passwordAfterClear).containsOnly(' ');
    }
}