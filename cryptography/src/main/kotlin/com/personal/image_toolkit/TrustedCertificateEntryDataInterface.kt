package com.personal.image_toolkit

import java.security.cert.Certificate

/**
 * Defines the contract for accessing data related to a Trusted Certificate Entry.
 */
interface TrustedCertificateEntryDataInterface {
    /**
     * @return The alias of the certificate entry.
     */
    val alias: String

    /**
     * @return The trusted certificate.
     */
    val certificate: Certificate
}