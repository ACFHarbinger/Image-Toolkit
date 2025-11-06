package com.personal.image_toolkit;

import java.math.BigInteger;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.NoSuchAlgorithmException;
import java.security.PrivateKey;
import java.security.cert.Certificate;
import java.util.Objects;

/**
 * A data container class (Data Transfer Object) for bundling all necessary
 * components of a PrivateKeyEntry needed for KeyStore operations.
 * * This simplifies passing a private key, its certificate chain, alias, 
 * and password between methods without long parameter lists.
 */
public class PrivateKeyEntryData {

    private final String alias;
    private final PrivateKey privateKey;
    private final Certificate[] certificateChain;
    private final char[] keyPassword;

    /**
     * Constructs a PrivateKeyEntryData object.
     *
     * @param alias The unique name (alias) for this entry in the KeyStore.
     * @param privateKey The actual PrivateKey object.
     * @param certificateChain The chain of certificates corresponding to the PrivateKey.
     * @param keyPassword The password used to protect this specific key entry.
     */
    public PrivateKeyEntryData(String alias, PrivateKey privateKey, Certificate[] certificateChain, char[] keyPassword) {
        this.alias = Objects.requireNonNull(alias, "Alias cannot be null.");
        this.privateKey = Objects.requireNonNull(privateKey, "PrivateKey cannot be null.");
        this.certificateChain = Objects.requireNonNull(certificateChain, "Certificate chain cannot be null.");
        this.keyPassword = Objects.requireNonNull(keyPassword, "Key password cannot be null.");
    }

    /**
     * @return The alias of the key entry.
     */
    public String getAlias() {
        return alias;
    }

    /**
     * @return The private key.
     */
    public PrivateKey getPrivateKey() {
        return privateKey;
    }

    /**
     * @return The certificate chain. Returns a defensive copy to prevent external modification.
     */
    public Certificate[] getCertificateChain() {
        return certificateChain.clone();
    }

    /**
     * @return The password for the key. Returns a defensive copy (char array) for security.
     */
    public char[] getKeyPassword() {
        return keyPassword.clone();
    }

    /**
     * Security best practice: clears the key password from the internal array.
     * This should be called when the object is no longer needed.
     */
    public void clearPassword() {
        java.util.Arrays.fill(this.keyPassword, ' ');
    }
}