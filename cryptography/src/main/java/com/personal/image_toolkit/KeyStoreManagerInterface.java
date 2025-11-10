package com.personal.image_toolkit;

import java.io.IOException;
import java.security.KeyStore;
import java.security.KeyStoreException;
import java.security.NoSuchAlgorithmException;
import java.security.UnrecoverableEntryException;
import java.security.cert.CertificateException;
import java.util.Enumeration;
import javax.crypto.SecretKey;
import org.bouncycastle.operator.OperatorCreationException;

/**
 * Defines the contract for a component responsible for managing Java KeyStore operations,
 * including loading, saving, storing, and retrieving various types of cryptographic entries.
 */
public interface KeyStoreManagerInterface {

    /**
     * Loads a KeyStore from the specified path. If the file does not exist, an empty KeyStore is created.
     *
     * @param storePassword The password protecting the KeyStore file.
     * @param storePath The file path to the KeyStore.
     * @return A loaded or newly created KeyStore instance.
     * @throws KeyStoreException If there is an issue with the KeyStore format or loading.
     * @throws IOException If the file cannot be read.
     * @throws NoSuchAlgorithmException If the KeyStore algorithm is not supported.
     * @throws CertificateException If any certificates in the KeyStore are invalid.
     */
    KeyStore loadKeyStore(char[] storePassword, String storePath) throws KeyStoreException, IOException, NoSuchAlgorithmException, CertificateException;

    /**
     * Saves the current KeyStore instance to the specified path.
     *
     * @param keyStore The KeyStore instance to save.
     * @param storePassword The password protecting the KeyStore file.
     * @param storePath The file path where the KeyStore should be saved.
     * @throws KeyStoreException If there is an issue with the KeyStore.
     * @throws IOException If the file cannot be written to.
     * @throws NoSuchAlgorithmException If the KeyStore algorithm is not supported.
     * @throws CertificateException If any certificates in the KeyStore are invalid.
     */
    void saveKeyStore(KeyStore keyStore, char[] storePassword, String storePath) throws KeyStoreException, IOException, NoSuchAlgorithmException, CertificateException;

    /**
     * Stores a PrivateKeyEntry into the KeyStore.
     *
     * @param keyStore The KeyStore to store the entry in.
     * @param keyEntryData The DTO containing the alias, private key, certificate chain, and key password.
     * @throws KeyStoreException If there is an issue storing the entry.
     */
    void storePrivateKey(KeyStore keyStore, PrivateKeyEntryData keyEntryData) throws KeyStoreException;

    /**
     * Retrieves a PrivateKeyEntry from the KeyStore.
     *
     * @param keyStore The KeyStore to retrieve the entry from.
     * @param alias The alias of the entry.
     * @param keyPassword The password protecting the specific key entry.
     * @return The DTO containing the retrieved private key and chain.
     * @throws KeyStoreException If there is an issue with the KeyStore.
     * @throws NoSuchAlgorithmException If the algorithm is not supported.
     * @throws UnrecoverableEntryException If the entry cannot be recovered with the given password.
     */
    PrivateKeyEntryData getPrivateKeyEntry(KeyStore keyStore, String alias, char[] keyPassword) throws KeyStoreException, NoSuchAlgorithmException, UnrecoverableEntryException;

    /**
     * Stores a SecretKey (Symmetric Key) into the KeyStore.
     *
     * @param keyStore The KeyStore to store the entry in.
     * @param alias The alias for the secret key entry.
     * @param secretKey The secret key object.
     * @param keyPassword The password protecting the specific key entry.
     * @throws KeyStoreException If there is an issue storing the entry.
     */
    void storeSecretKey(KeyStore keyStore, String alias, SecretKey secretKey, char[] keyPassword) throws KeyStoreException;

    /**
     * Retrieves a SecretKey from the KeyStore.
     *
     * @param keyStore The KeyStore to retrieve the entry from.
     * @param alias The alias of the entry.
     * @param keyPassword The password protecting the specific key entry.
     * @return The retrieved SecretKey.
     * @throws KeyStoreException If there is an issue with the KeyStore.
     * @throws NoSuchAlgorithmException If the algorithm is not supported.
     * @throws UnrecoverableEntryException If the entry cannot be recovered with the given password.
     */
    SecretKey getSecretKey(KeyStore keyStore, String alias, char[] keyPassword) throws KeyStoreException, NoSuchAlgorithmException, UnrecoverableEntryException;

    /**
     * Stores a TrustedCertificateEntry into the KeyStore.
     *
     * @param keyStore The KeyStore to store the entry in.
     * @param certEntryData The DTO containing the alias and trusted certificate.
     * @throws KeyStoreException If there is an issue storing the entry.
     */
    void storeTrustedCertificate(KeyStore keyStore, TrustedCertificateEntryData certEntryData) throws KeyStoreException;

    /**
     * Retrieves a TrustedCertificateEntry from the KeyStore.
     *
     * @param keyStore The KeyStore to retrieve the entry from.
     * @param alias The alias of the entry.
     * @return The DTO containing the retrieved certificate.
     * @throws KeyStoreException If there is an issue with the KeyStore.
     */
    TrustedCertificateEntryData getTrustedCertificate(KeyStore keyStore, String alias) throws KeyStoreException;

    /**
     * Deletes an entry from the KeyStore by its alias.
     *
     * @param keyStore The KeyStore to modify.
     * @param alias The alias of the entry to delete.
     * @throws KeyStoreException If the KeyStore has not been initialized.
     */
    void deleteEntry(KeyStore keyStore, String alias) throws KeyStoreException;

    /**
     * Returns an enumeration of all aliases in the KeyStore.
     *
     * @param keyStore The KeyStore to query.
     * @return An enumeration of all aliases.
     * @throws KeyStoreException If the KeyStore has not been initialized.
     */
    Enumeration<String> getAliases(KeyStore keyStore) throws KeyStoreException;

    /**
     * Generates a new SecretKey of the specified algorithm and key size.
     *
     * @param algorithm The cryptographic algorithm (e.g., "AES").
     * @param keySize The desired key size in bits (e.g., 256).
     * @return The generated SecretKey.
     * @throws NoSuchAlgorithmException If the algorithm is not supported.
     */
    SecretKey generateSecretKey(String algorithm, int keySize) throws NoSuchAlgorithmException;

    /**
     * Generates a new self-signed X.509 certificate and private key pair.
     *
     * @param alias The alias for the new key pair.
     * @param keyPassword The password to protect the private key entry.
     * @return A DTO containing the new private key, certificate chain, alias, and key password.
     * @throws NoSuchAlgorithmException If RSA is not available.
     * @throws OperatorCreationException If the BouncyCastle provider fails to create the signer.
     * @throws CertificateException If certificate creation fails.
     */
    PrivateKeyEntryData generateSelfSignedCertificate(String alias, char[] keyPassword) throws NoSuchAlgorithmException, OperatorCreationException, CertificateException;
}