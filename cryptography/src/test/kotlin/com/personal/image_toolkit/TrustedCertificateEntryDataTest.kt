package com.personal.image_toolkit

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import java.security.cert.Certificate

class TrustedCertificateEntryDataTest {

    private lateinit var alias: String
    private lateinit var certificate: Certificate

    @BeforeEach
    fun setUp() {
        alias = "trusted-cert-alias"

        val generatedData = KeyStoreManager.generatePrivateKeyEntry("temp-alias", "temp-pass".toCharArray())
        certificate = generatedData.certificateChain[0]
    }

    @Test
    fun constructor_shouldSucceedWithValidArgs() {
        val data = TrustedCertificateEntryData(alias, certificate)
        assertThat(data.alias).isEqualTo(alias)
        assertThat(data.certificate).isEqualTo(certificate)
    }

    // Note: Null checks are typically handled by Kotlin compiler or require explicitly passing null from Java.
    // Pure Kotlin usage ensures non-nullability via type system.

    @Test
    fun getters_shouldReturnCorrectValues() {
        val data = TrustedCertificateEntryData(alias, certificate)
        assertThat(data.alias).isEqualTo(alias)
        assertThat(data.certificate).isEqualTo(certificate)
        // Certificate objects are immutable, so no defensive copy is needed.
    }
}