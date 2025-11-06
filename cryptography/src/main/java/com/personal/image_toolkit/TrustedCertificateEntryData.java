package com.personal.image_toolkit;

import java.security.cert.Certificate;
import java.util.Objects;

/**
 * A data container class (Data Transfer Object) for bundling a trusted 
 * public certificate and its alias for KeyStore operations.
 */
public class TrustedCertificateEntryData {

    private final String alias;
    private final Certificate certificate;

    /**
     * Constructs a TrustedCertificateEntryData object.
     *
     * @param alias The unique name (alias) for this entry in the KeyStore.
     * @param certificate The trusted public Certificate object to be stored.
     */
    public TrustedCertificateEntryData(String alias, Certificate certificate) {
        this.alias = Objects.requireNonNull(alias, "Alias cannot be null.");
        this.certificate = Objects.requireNonNull(certificate, "Certificate cannot be null.");
    }

    /**
     * @return The alias of the certificate entry.
     */
    public String getAlias() {
        return alias;
    }

    /**
     * @return The trusted certificate.
     */
    public Certificate getCertificate() {
        return certificate;
    }
}