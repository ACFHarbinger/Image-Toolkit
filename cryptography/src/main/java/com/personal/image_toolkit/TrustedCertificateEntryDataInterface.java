package com.personal.image_toolkit;

import java.security.cert.Certificate;

/**
 * Defines the contract for accessing data related to a Trusted Certificate Entry.
 */
public interface TrustedCertificateEntryDataInterface {

    /**
     * @return The alias of the certificate entry.
     */
    String getAlias();

    /**
     * @return The trusted certificate.
     */
    Certificate getCertificate();
}