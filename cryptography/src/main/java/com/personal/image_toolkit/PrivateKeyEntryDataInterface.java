package com.personal.image_toolkit;

import java.security.PrivateKey;
import java.security.cert.Certificate;

/**
 * Defines the contract for accessing data related to a PrivateKeyEntry.
 */
public interface PrivateKeyEntryDataInterface {

    /**
     * @return The alias of the key entry.
     */
    String getAlias();

    /**
     * @return The private key.
     */
    PrivateKey getPrivateKey();

    /**
     * @return The certificate chain.
     */
    Certificate[] getCertificateChain();

    /**
     * @return The password for the key.
     */
    char[] getKeyPassword();

    /**
     * Clears the key password from the internal array for security best practice.
     */
    void clearPassword();
}