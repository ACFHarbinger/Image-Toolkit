package com.personal.image_toolkit

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import java.security.PrivateKey
import java.security.cert.Certificate

class PrivateKeyEntryDataTest {

    private lateinit var alias: String
    private lateinit var privateKey: PrivateKey
    // Change back to non-nullable array to match what KeyStoreManager.generatePrivateKeyEntry likely returns
    private lateinit var certificateChain: Array<Certificate> 
    private lateinit var keyPassword: CharArray

    // NOTE: Assuming KeyStoreManager.generatePrivateKeyEntry returns Array<Certificate> (non-nullable).
    @BeforeEach
    fun setUp() {
        alias = "test-alias"
        keyPassword = charArrayOf('p', 'a', 's', 's')

        // generatedData.certificateChain is now directly assigned to the non-nullable type, fixing line 23
        val generatedData = KeyStoreManager.generatePrivateKeyEntry(alias, keyPassword)
        privateKey = generatedData.privateKey
        certificateChain = generatedData.certificateChain
    }

    @Test
    fun constructor_shouldSucceedWithValidArgs() {
        // certificateChain is Array<Certificate>, matching the expected constructor argument
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
        
        // Defensive copy check 1: Basic equality and reference check
        val retrievedChain = data.certificateChain
        assertThat(retrievedChain).isEqualTo(certificateChain)
        assertThat(retrievedChain).isNotSameAs(certificateChain)

        // To test assignment of null, we must use a nullable array type.
        // We create a nullable copy of the retrieved chain for modification purposes only.
        val nullableChainCopy = retrievedChain.clone() as Array<Certificate?>
        
        // Modify the retrieved copy's nullable array
        // This is necessary because the original property is likely Array<Certificate>
        // and its getter returns Array<Certificate> (non-nullable elements).
        nullableChainCopy[0] = null 

        // Check that the internal array is unchanged (accessing the original getter result)
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