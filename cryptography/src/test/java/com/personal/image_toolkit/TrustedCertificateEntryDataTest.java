package com.personal.image_toolkit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.security.cert.Certificate;
import static org.assertj.core.api.Assertions.*;

class TrustedCertificateEntryDataTest {

    private String alias;
    private Certificate certificate;

    @BeforeEach
    void setUp() throws Exception {
        alias = "trusted-cert-alias";

        PrivateKeyEntryData generatedData = KeyStoreManager.generatePrivateKeyEntry("temp-alias", "temp-pass".toCharArray());
        certificate = generatedData.getCertificateChain()[0];
    }

    @Test
    void constructor_shouldSucceedWithValidArgs() {
        TrustedCertificateEntryData data = new TrustedCertificateEntryData(alias, certificate);
        assertThat(data.getAlias()).isEqualTo(alias);
        assertThat(data.getCertificate()).isEqualTo(certificate);
    }

    @Test
    void constructor_shouldThrowExceptionForNullAlias() {
        assertThatNullPointerException()
                .isThrownBy(() -> new TrustedCertificateEntryData(null, certificate))
                .withMessage("Alias cannot be null.");
    }

    @Test
    void constructor_shouldThrowExceptionForNullCertificate() {
        assertThatNullPointerException()
                .isThrownBy(() -> new TrustedCertificateEntryData(alias, null))
                .withMessage("Certificate cannot be null.");
    }

    @Test
    void getters_shouldReturnCorrectValues() {
        TrustedCertificateEntryData data = new TrustedCertificateEntryData(alias, certificate);
        assertThat(data.getAlias()).isEqualTo(alias);
        assertThat(data.getCertificate()).isEqualTo(certificate);
        // Certificate objects are immutable, so no defensive copy is needed.
    }
}