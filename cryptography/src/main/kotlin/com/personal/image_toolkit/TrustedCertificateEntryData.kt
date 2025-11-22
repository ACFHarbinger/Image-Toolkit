package com.personal.image_toolkit

import java.security.cert.Certificate

/**
 * A data container class (Data Transfer Object) for bundling a trusted
 * public certificate and its alias for KeyStore operations.
 */
data class TrustedCertificateEntryData(
    override val alias: String,
    override val certificate: Certificate
) : TrustedCertificateEntryDataInterface