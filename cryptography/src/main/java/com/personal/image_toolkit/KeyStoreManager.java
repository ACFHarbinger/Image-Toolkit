package com.personal.image_toolkit;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.math.BigInteger;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.KeyStoreException;
import java.security.NoSuchAlgorithmException;
import java.security.PrivateKey;
import java.security.SecureRandom;
import java.security.Security;
import java.security.UnrecoverableEntryException;
import java.security.cert.Certificate;
import java.security.cert.CertificateException;
import java.util.Date;
import java.util.Enumeration;
import java.util.UUID;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.cert.X509v3CertificateBuilder;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.OperatorCreationException;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;

/**
 * A comprehensive example for managing a Java KeyStore.
 * This class demonstrates loading, saving, storing keys, and retrieving keys.
 */
public class KeyStoreManager {

    /**
     * The type of KeyStore instance to use, typically "PKCS12".
     */
    private static final String KEYSTORE_TYPE = "PKCS12";

    // Register the Bouncy Castle Provider if it hasn't been already
    static {
        if (Security.getProvider(BouncyCastleProvider.PROVIDER_NAME) == null) {
            Security.addProvider(new BouncyCastleProvider());
        }
    }

    /**
     * Loads a KeyStore from a file. If the file doesn't exist,
     * it creates a new, empty KeyStore of type {@link #KEYSTORE_TYPE}.
     *
     * @param fileName The path to the KeyStore file.
     * @param password The password for the KeyStore.
     * @return A loaded or newly created {@code KeyStore} instance.
     * @throws KeyStoreException If no implementation for the KeyStore type is found.
     * @throws IOException If an I/O error occurs while loading the file.
     * @throws NoSuchAlgorithmException If the algorithm for checking the integrity of the KeyStore cannot be found.
     * @throws CertificateException If any of the certificates in the KeyStore could not be loaded.
     */
    public static KeyStore loadKeyStore(String fileName, char[] password)
            throws KeyStoreException, IOException, NoSuchAlgorithmException, CertificateException {

        KeyStore keyStore = KeyStore.getInstance(KEYSTORE_TYPE);
        File file = new File(fileName);

        if (file.exists()) {
            try (FileInputStream fis = new FileInputStream(file)) {
                keyStore.load(fis, password);
                System.out.println("Loaded existing keystore: " + fileName);
            }
        } else {
            keyStore.load(null, password);
            System.out.println("Created new empty keystore: " + fileName);
        }
        return keyStore;
    }

    /**
     * Saves the KeyStore content to a file.
     *
     * @param keyStore The {@code KeyStore} instance to save.
     * @param fileName The path to the KeyStore file.
     * @param password The password used to protect the KeyStore.
     * @throws KeyStoreException If an error occurs while writing the KeyStore to the output stream.
     * @throws IOException If an I/O error occurs while writing to the file.
     * @throws NoSuchAlgorithmException If the algorithm for creating the integrity protection of the KeyStore cannot be found.
     * @throws CertificateException If any of the certificates in the KeyStore could not be stored.
     */
    public static void saveKeyStore(KeyStore keyStore, String fileName, char[] password)
            throws KeyStoreException, IOException, NoSuchAlgorithmException, CertificateException {

        try (FileOutputStream fos = new FileOutputStream(fileName)) {
            keyStore.store(fos, password);
        }
    }

    /**
     * Generates a new AES-256 {@code SecretKey} and stores it in the KeyStore under the given alias.
     *
     * @param keyStore The {@code KeyStore} instance to store the key in.
     * @param alias The alias to associate with the secret key entry.
     * @param keyPassword The password to protect the individual key entry.
     * @throws NoSuchAlgorithmException If the AES algorithm for key generation is not available.
     * @throws KeyStoreException If an error occurs while setting the key entry in the KeyStore.
     */
    public static void storeSecretKey(KeyStore keyStore, String alias, char[] keyPassword)
            throws NoSuchAlgorithmException, KeyStoreException {

        KeyGenerator keyGen = KeyGenerator.getInstance("AES");
        keyGen.init(256);
        SecretKey secretKey = keyGen.generateKey();

        KeyStore.SecretKeyEntry secretKeyEntry = new KeyStore.SecretKeyEntry(secretKey);

        KeyStore.ProtectionParameter protParam = new KeyStore.PasswordProtection(keyPassword);

        keyStore.setEntry(alias, secretKeyEntry, protParam);
    }

    /**
     * Retrieves a {@code SecretKey} from the KeyStore associated with the given alias.
     *
     * @param keyStore The {@code KeyStore} instance to retrieve the key from.
     * @param alias The alias of the key entry.
     * @param keyPassword The password used to protect the individual key entry.
     * @return The retrieved {@code SecretKey}, or {@code null} if the entry is not found or is not a {@code SecretKeyEntry}.
     * @throws NoSuchAlgorithmException If the algorithm needed to recover the key cannot be found.
     * @throws UnrecoverableEntryException If the entry could not be recovered (e.g., incorrect key password).
     * @throws KeyStoreException If an error occurs while attempting to access the entry.
     */
    public static SecretKey getSecretKey(KeyStore keyStore, String alias, char[] keyPassword)
            throws NoSuchAlgorithmException, UnrecoverableEntryException, KeyStoreException {

        KeyStore.ProtectionParameter protParam = new KeyStore.PasswordProtection(keyPassword);

        KeyStore.Entry entry = keyStore.getEntry(alias, protParam);

        if (entry == null) {
            System.err.println("No entry found for alias: " + alias);
            return null;
        }
        if (!(entry instanceof KeyStore.SecretKeyEntry)) {
            System.err.println("Entry for " + alias + " is not a SecretKeyEntry.");
            return null;
        }

        KeyStore.SecretKeyEntry secretKeyEntry = (KeyStore.SecretKeyEntry) entry;
        return secretKeyEntry.getSecretKey();
    }

    /**
     * Lists all aliases and their corresponding entry types in the keystore.
     *
     * @param keyStore The {@code KeyStore} instance to list entries from.
     * @throws KeyStoreException If an error occurs while enumerating aliases or checking entry types.
     */
    public static void listEntries(KeyStore keyStore) throws KeyStoreException {
        Enumeration<String> aliases = keyStore.aliases();
        if (!aliases.hasMoreElements()) {
            System.out.println("Keystore is empty.");
            return;
        }

        while (aliases.hasMoreElements()) {
            String alias = aliases.nextElement();
            System.out.print("  - Alias: " + alias);

            if (keyStore.isKeyEntry(alias)) {
                System.out.println(" (Key Entry)");
            } else if (keyStore.isCertificateEntry(alias)) {
                System.out.println(" (Certificate Entry)");
            } else {
                System.out.println(" (Unknown Entry)");
            }
        }
    }

    /**
     * (Example) Stores a PrivateKey and its Certificate chain in the KeyStore using the bundled data.
     *
     * @param keyStore The KeyStore instance to store the key in.
     * @param data The data container holding the alias, private key, chain, and password.
     * @throws KeyStoreException If an error occurs while setting the private key entry in the KeyStore.
     */
    public void storePrivateKeyEntry(KeyStore keyStore, PrivateKeyEntryData data) throws KeyStoreException {

        KeyStore.ProtectionParameter protParam = new KeyStore.PasswordProtection(data.getKeyPassword());
        KeyStore.PrivateKeyEntry privateKeyEntry = new KeyStore.PrivateKeyEntry(
            data.getPrivateKey(),
            data.getCertificateChain()
        );

        keyStore.setEntry(data.getAlias(), privateKeyEntry, protParam);
        System.out.println("Stored private key for alias: " + data.getAlias());
        
        data.clearPassword(); 
    }

    /**
     * (Example) Stores a trusted public certificate in the KeyStore.
     *
     * @param keyStore The {@code KeyStore} instance to store the certificate in.
     * @param data The data container holding the alias and the trusted certificate.
     * @throws KeyStoreException If an error occurs while setting the certificate entry in the KeyStore.
     */
    public void storeTrustedCertificate(KeyStore keyStore, TrustedCertificateEntryData data)
            throws KeyStoreException {
        
        keyStore.setCertificateEntry(data.getAlias(), data.getCertificate());
        System.out.println("Stored trusted certificate for alias: " + data.getAlias());
    }

    /**
     * Generates a new RSA PrivateKey and wraps it with a Bouncy Castle self-signed
     * X.509 Certificate into a PrivateKeyEntryData object.
     *
     * @param alias The alias for the key.
     * @param keyPassword The password to protect the key entry.
     * @return A PrivateKeyEntryData object containing the new KeyPair and a self-signed certificate.
     * @throws NoSuchAlgorithmException If the RSA algorithm is not supported.
     * @throws OperatorCreationException If there's an issue creating the certificate signer.
     * @throws Exception For errors during certificate creation or conversion.
     */
    public static PrivateKeyEntryData generatePrivateKeyEntry(String alias, char[] keyPassword) 
            throws NoSuchAlgorithmException, OperatorCreationException, Exception {

        // 1. Generate the KeyPair
        KeyPairGenerator keyGen = KeyPairGenerator.getInstance("RSA", BouncyCastleProvider.PROVIDER_NAME);
        keyGen.initialize(2048, new SecureRandom());
        KeyPair keyPair = keyGen.generateKeyPair();

        // 2. Define Certificate Parameters
        Date validityStart = new Date();
        // Valid for 1 year
        Date validityEnd = new Date(validityStart.getTime() + (365L * 24L * 60L * 60L * 1000L)); 
        
        // Unique serial number
        BigInteger serialNumber = BigInteger.valueOf(UUID.randomUUID().getMostSignificantBits()).abs();

        // Subject/Issuer Name (Self-signed, so Subject and Issuer are the same)
        X500Name subjectName = new X500Name("CN=" + alias + ", O=Image-Toolkit");

        // 3. Create the Certificate Builder
        X509v3CertificateBuilder certBuilder = new JcaX509v3CertificateBuilder(
            subjectName,              // Issuer
            serialNumber,             // Serial Number
            validityStart,            // Not Before
            validityEnd,              // Not After
            subjectName,              // Subject
            keyPair.getPublic()       // Subject Public Key
        );

        // 4. Create the Content Signer
        // Use SHA256withRSA for the signature, signing with the generated private key
        ContentSigner contentSigner = new JcaContentSignerBuilder("SHA256WithRSAEncryption")
            .setProvider(BouncyCastleProvider.PROVIDER_NAME)
            .build(keyPair.getPrivate());

        // 5. Generate and Convert the Certificate
        Certificate cert = new JcaX509CertificateConverter()
            .setProvider(BouncyCastleProvider.PROVIDER_NAME)
            .getCertificate(certBuilder.build(contentSigner));

        // 6. Bundle and Return
        Certificate[] chain = new Certificate[]{cert};
        
        return new PrivateKeyEntryData(alias, keyPair.getPrivate(), chain, keyPassword);
    }
}