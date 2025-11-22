package com.personal.image_toolkit

import org.bouncycastle.asn1.x500.X500Name
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder
import org.bouncycastle.jce.provider.BouncyCastleProvider
import org.bouncycastle.operator.OperatorCreationException
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.math.BigInteger
import java.security.*
import java.security.cert.Certificate
import java.security.cert.CertificateException
import java.util.*
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey

/**
 * A comprehensive example for managing a Java KeyStore.
 * This class demonstrates loading, saving, storing keys, and retrieving keys.
 */
class KeyStoreManager : KeyStoreManagerInterface {

    /**
     * Loads a KeyStore from a file. If the file doesn't exist,
     * it creates a new, empty KeyStore of type [KEYSTORE_TYPE].
     */
    @Throws(
        KeyStoreException::class,
        IOException::class,
        NoSuchAlgorithmException::class,
        CertificateException::class
    )
    override fun loadKeyStore(fileName: String, password: CharArray): KeyStore {
        val keyStore = KeyStore.getInstance(KEYSTORE_TYPE)
        val file = File(fileName)

        if (file.exists()) {
            FileInputStream(file).use { fis ->
                keyStore.load(fis, password)
                println("Loaded existing keystore: $fileName")
            }
        } else {
            keyStore.load(null, password)
            println("Created new empty keystore: $fileName")
        }
        return keyStore
    }

    /**
     * Saves the KeyStore content to a file.
     */
    @Throws(
        KeyStoreException::class,
        IOException::class,
        NoSuchAlgorithmException::class,
        CertificateException::class
    )
    override fun saveKeyStore(keyStore: KeyStore, fileName: String, password: CharArray) {
        FileOutputStream(fileName).use { fos ->
            keyStore.store(fos, password)
        }
    }

    /**
     * Generates a new AES-256 [SecretKey] and stores it in the KeyStore under the given alias.
     */
    @Throws(NoSuchAlgorithmException::class, KeyStoreException::class)
    override fun storeSecretKey(keyStore: KeyStore, alias: String, keyPassword: CharArray) {
        val keyGen = KeyGenerator.getInstance("AES")
        keyGen.init(256)
        val secretKey = keyGen.generateKey()

        val secretKeyEntry = KeyStore.SecretKeyEntry(secretKey)
        val protParam = KeyStore.PasswordProtection(keyPassword)

        keyStore.setEntry(alias, secretKeyEntry, protParam)
    }

    /**
     * Retrieves a [SecretKey] from the KeyStore associated with the given alias.
     */
    @Throws(
        NoSuchAlgorithmException::class,
        UnrecoverableEntryException::class,
        KeyStoreException::class
    )
    override fun getSecretKey(keyStore: KeyStore, alias: String, keyPassword: CharArray): SecretKey? {
        val protParam = KeyStore.PasswordProtection(keyPassword)
        val entry = keyStore.getEntry(alias, protParam)

        if (entry == null) {
            System.err.println("No entry found for alias: $alias")
            return null
        }
        if (entry !is KeyStore.SecretKeyEntry) {
            System.err.println("Entry for $alias is not a SecretKeyEntry.")
            return null
        }

        return entry.secretKey
    }

    /**
     * Stores a PrivateKey and its Certificate chain in the KeyStore using the bundled data.
     */
    @Throws(KeyStoreException::class)
    override fun storePrivateKeyEntry(keyStore: KeyStore, data: PrivateKeyEntryData) {
        val protParam = KeyStore.PasswordProtection(data.keyPassword)
        val privateKeyEntry = KeyStore.PrivateKeyEntry(
            data.privateKey,
            data.certificateChain
        )

        keyStore.setEntry(data.alias, privateKeyEntry, protParam)
        println("Stored private key for alias: " + data.alias)

        data.clearPassword()
    }

    /**
     * Stores a trusted public certificate in the KeyStore.
     */
    @Throws(KeyStoreException::class)
    override fun storeTrustedCertificate(
        keyStore: KeyStore,
        certEntryData: TrustedCertificateEntryData
    ) {
        keyStore.setCertificateEntry(certEntryData.alias, certEntryData.certificate)
        println("Stored trusted certificate for alias: " + certEntryData.alias)
    }

    companion object {
        /**
         * The type of KeyStore instance to use, typically "PKCS12".
         */
        private const val KEYSTORE_TYPE = "PKCS12"

        // Register the Bouncy Castle Provider if it hasn't been already
        init {
            if (Security.getProvider(BouncyCastleProvider.PROVIDER_NAME) == null) {
                Security.addProvider(BouncyCastleProvider())
            }
        }

        /**
         * Lists all aliases and their corresponding entry types in the keystore.
         */
        @Throws(KeyStoreException::class)
        fun listEntries(keyStore: KeyStore) {
            val aliases = keyStore.aliases()
            if (!aliases.hasMoreElements()) {
                println("Keystore is empty.")
                return
            }

            while (aliases.hasMoreElements()) {
                val alias = aliases.nextElement()
                print("  - Alias: $alias")

                if (keyStore.isKeyEntry(alias)) {
                    println(" (Key Entry)")
                } else if (keyStore.isCertificateEntry(alias)) {
                    println(" (Certificate Entry)")
                } else {
                    println(" (Unknown Entry)")
                }
            }
        }

        /**
         * Generates a new RSA PrivateKey and wraps it with a Bouncy Castle self-signed
         * X.509 Certificate into a PrivateKeyEntryData object.
         */
        @Throws(NoSuchAlgorithmException::class, OperatorCreationException::class, Exception::class)
        fun generatePrivateKeyEntry(alias: String, keyPassword: CharArray): PrivateKeyEntryData {
            // 1. Generate the KeyPair
            val keyGen = KeyPairGenerator.getInstance("RSA", BouncyCastleProvider.PROVIDER_NAME)
            keyGen.initialize(2048, SecureRandom())
            val keyPair = keyGen.generateKeyPair()

            // 2. Define Certificate Parameters
            val validityStart = Date()
            // Valid for 1 year
            val validityEnd = Date(validityStart.time + 365L * 24L * 60L * 60L * 1000L)

            // Unique serial number
            val serialNumber = BigInteger.valueOf(UUID.randomUUID().mostSignificantBits).abs()

            // Subject/Issuer Name (Self-signed, so Subject and Issuer are the same)
            val subjectName = X500Name("CN=$alias, O=Image-Toolkit")

            // 3. Create the Certificate Builder
            val certBuilder = JcaX509v3CertificateBuilder(
                subjectName,              // Issuer
                serialNumber,             // Serial Number
                validityStart,            // Not Before
                validityEnd,              // Not After
                subjectName,              // Subject
                keyPair.public            // Subject Public Key
            )

            // 4. Create the Content Signer
            // Use SHA256withRSA for the signature, signing with the generated private key
            val contentSigner = JcaContentSignerBuilder("SHA256WithRSAEncryption")
                .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                .build(keyPair.private)

            // 5. Generate and Convert the Certificate
            val cert = JcaX509CertificateConverter()
                .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                .getCertificate(certBuilder.build(contentSigner))

            // 6. Bundle and Return
            val chain = arrayOf<Certificate>(cert)

            return PrivateKeyEntryData(alias, keyPair.private, chain, keyPassword)
        }
    }
}