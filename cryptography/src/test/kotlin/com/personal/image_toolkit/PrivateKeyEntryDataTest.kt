package com.personal.image_toolkit

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import java.security.PrivateKey
import java.security.cert.Certificate

class PrivateKeyEntryDataTest {

    private lateinit var alias: String
    private lateinit var privateKey: PrivateKey
    private lateinit var certificateChain: Array<Certificate>
    private lateinit var keyPassword: CharArray

    @BeforeEach
    fun setUp() {
        alias = "test-alias"
        keyPassword = charArrayOf('p', 'a', 's', 's')

        val generatedData = KeyStoreManager.generatePrivateKeyEntry(alias, keyPassword)
        privateKey = generatedData.privateKey
        certificateChain = generatedData.certificateChain
    }

    @Test
    fun constructor_shouldSucceedWithValidArgs() {
        val data = PrivateKeyEntryData(alias, privateKey, certificateChain, keyPassword)
        assertThat(data.alias).isEqualTo(alias)
        assertThat(data.privateKey).isEqualTo(privateKey)
        assertThat(data.certificateChain).isEqualTo(certificateChain)
        assertThat(data.keyPassword).isEqualTo(keyPassword)
    }

    // Note: Kotlin's type system prevents nulls at compile time for non-nullable types.
    // Tests checking for null constructor args are often redundant in Kotlin if instantiation
    // is done directly, but could be relevant if called from Java.
    // However, assuming pure Kotlin usage, we skip "throws exception for null" tests
    // because the compiler handles it.

    @Test
    fun getCertificateChain_shouldReturnDefensiveCopy() {
        val data = PrivateKeyEntryData(alias, privateKey, certificateChain, keyPassword)
        val retrievedChain = data.certificateChain

        assertThat(retrievedChain).isEqualTo(certificateChain)
        assertThat(retrievedChain).isNotSameAs(certificateChain)

        // Modify the retrieved copy
        retrievedChain[0] = null

        // Check that the internal array is unchanged
        assertThat(data.certificateChain[0]).isNotNull
    }

    @Test
    fun getKeyPassword_shouldReturnDefensiveCopy() {
        val data = PrivateKeyEntryData(alias, privateKey, certificateChain, keyPassword)
        val retrievedPassword = data.keyPassword

        assertThat(retrievedPassword).isEqualTo(keyPassword)
        assertThat(retrievedPassword).isNotSameAs(keyPassword)

        // Modify the retrieved copy
        retrievedPassword[0] = 'X'

        // Check that the internal array is unchanged by getting a new clone
        assertThat(data.keyPassword[0]).isEqualTo('p')
        // Check that the original array is also unchanged
        assertThat(keyPassword[0]).isEqualTo('p')
    }

    @Test
    fun clearPassword_shouldWipeTheInternalPasswordArray() {
        // Use a fresh array for this test to check its state
        val originalPasswordArray = charArrayOf('p', 'a', 's', 's')
        val data = PrivateKeyEntryData(alias, privateKey, certificateChain, originalPasswordArray)

        // Act
        data.clearPassword()

        // Assert
        // The original array reference passed to the constructor should be cleared
        assertThat(originalPasswordArray).containsOnly(' ')

        // A new copy retrieved from the getter should also reflect this cleared state
        val passwordAfterClear = data.keyPassword
        assertThat(passwordAfterClear).containsOnly(' ')
    }
}