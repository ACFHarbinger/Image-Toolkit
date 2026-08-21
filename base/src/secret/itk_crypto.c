// Native replacement for the Kotlin/JVM cryptography module (issue #XXX).
//
// Implements the exact storage formats the JVM module used, so existing
// keystores and vault files keep working with no migration:
//
//   * Keystore: PKCS#12 containing a single AES secret key stored as a
//     shrouded key bag (pkcs8ShroudedKeyBag, PBES2/PBKDF2/AES-256-CBC,
//     friendlyName = alias, localKeyID) -- the layout Java's SunJCE
//     "PKCS12" KeyStore writes (verified empirically against a
//     JVM-generated keystore).
//   * Vault:   [IV_LENGTH:int32 BE][IV:12][AES-256-GCM ciphertext + 16-byte
//     tag] -- byte-identical to Kotlin SecureJsonVault.saveData().
//
// C ABI so Python loads it with ctypes (no build-time Python/C++ glue).
//
// Build: cc -O2 -fPIC -shared -o build/crypto/libitk_crypto.so itk_crypto.c -lcrypto

#include <openssl/err.h>
#include <openssl/evp.h>
#include <openssl/pkcs12.h>
#include <openssl/rand.h>
#include <openssl/x509.h>

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

static _Thread_local char g_errbuf[512];

static void set_error(const char *fmt, const char *detail)
{
    (void)ERR_get_error(); /* clear the per-thread error queue */
    const char *errstr = detail ? detail : "";
    snprintf(g_errbuf, sizeof(g_errbuf), fmt, errstr);
}

const char *itk_last_error(void)
{
    return g_errbuf;
}

void itk_free(void *p)
{
    free(p);
}

/* ------------------------------------------------------------------ */
/* PKCS#12 keystore helpers                                            */
/* ------------------------------------------------------------------ */

static int ascii_to_bmp(const char *ascii, unsigned char **out, size_t *out_len)
{
    size_t n = strlen(ascii);
    unsigned char *bmp = malloc(n * 2);
    if (!bmp)
        return -1;
    for (size_t i = 0; i < n; i++) {
        bmp[2 * i] = 0;
        bmp[2 * i + 1] = (unsigned char)ascii[i];
    }
    *out = bmp;
    *out_len = n * 2;
    return 0;
}

static int bag_matches_alias(const PKCS12_SAFEBAG *bag, const char *alias)
{
    if (!alias || !alias[0])
        return 1; /* no alias filter: first key bag wins */
    const ASN1_TYPE *attr = PKCS12_SAFEBAG_get0_attr(bag, NID_friendlyName);
    if (!attr)
        return 0;
    const ASN1_STRING *str = NULL;
    switch (attr->type) {
    case V_ASN1_BMPSTRING:
        str = attr->value.bmpstring;
        break;
    case V_ASN1_UTF8STRING:
        str = attr->value.utf8string;
        break;
    case V_ASN1_IA5STRING:
        str = attr->value.ia5string;
        break;
    default:
        return 0;
    }
    unsigned char *bmp = NULL;
    size_t bmp_len = 0;
    if (str->type == V_ASN1_BMPSTRING) {
        bmp = (unsigned char *)str->data;
        bmp_len = (size_t)str->length;
    } else if (ascii_to_bmp((const char *)str->data, &bmp, &bmp_len) != 0) {
        return 0;
    }
    unsigned char *want = NULL;
    size_t want_len = 0;
    if (ascii_to_bmp(alias, &want, &want_len) != 0) {
        if (bmp != str->data)
            free(bmp);
        return 0;
    }
    int match = (bmp_len == want_len) && (memcmp(bmp, want, bmp_len) == 0);
    if (want != NULL)
        free(want);
    if (bmp != str->data)
        free(bmp);
    return match;
}

/* Extracts the raw key bytes from a PKCS#12 secret bag. Java (SunJCE
 * "PKCS12") stores secret keys in a secretBag whose DER is:
 *
 *   SAFEBAG  ::= SEQUENCE { bagId OID, bagValue [0] EXPLICIT ANY, ... }
 *   SECRETBAG ::= SEQUENCE { secretTypeId OBJECT IDENTIFIER,
 *                            secretValue [0] EXPLICIT OCTET STRING }
 *
 * Java's secretTypeId is pkcs8ShroudedKeyBag and secretValue holds the DER
 * of the EncryptedPrivateKeyInfo (PBES2/PBKDF2/AES-256-CBC) -- the same
 * payload a shrouded key bag would carry directly. OpenSSL-written
 * keystores (via PKCS12_SAFEBAG_create_secret) instead put the raw key
 * bytes straight into secretValue; both layouts are handled here.
 *
 * OpenSSL exposes no accessor for secret-bag values, so re-serialize the
 * bag and walk the DER with low-level ASN1 primitives. Returns malloc'd
 * key in *out (caller itk_free()s). */
static int secret_bag_get_key(const PKCS12_SAFEBAG *bag, const char *pass,
                              unsigned char **out, size_t *out_len)
{
    int len = i2d_PKCS12_SAFEBAG(bag, NULL);
    if (len <= 0)
        return -1;
    unsigned char *der = malloc((size_t)len);
    if (!der)
        return -1;
    unsigned char *p = der;
    i2d_PKCS12_SAFEBAG(bag, &p);

    int rc = -1;
    const unsigned char *q = der;
    long avail = (long)len;
    long clen;
    int tag, cls;

    /* SAFEBAG SEQUENCE */
    if (ASN1_get_object(&q, &clen, &tag, &cls, avail) != 0x80 &&
        tag == V_ASN1_SEQUENCE) {
        avail = clen;
        ASN1_OBJECT *bagid = d2i_ASN1_OBJECT(NULL, &q, avail);
        int bag_nid = bagid ? OBJ_obj2nid(bagid) : 0;
        ASN1_OBJECT_free(bagid);
        if (bag_nid == NID_secretBag &&
            /* bagValue [0] EXPLICIT */
            ASN1_get_object(&q, &clen, &tag, &cls, avail) != 0x80 &&
            tag == 0 && cls == V_ASN1_CONTEXT_SPECIFIC) {
            avail = clen;
            /* SECRETBAG SEQUENCE */
            if (ASN1_get_object(&q, &clen, &tag, &cls, avail) != 0x80 &&
                tag == V_ASN1_SEQUENCE) {
                avail = clen;
                ASN1_OBJECT *tid = d2i_ASN1_OBJECT(NULL, &q, avail);
                int tid_nid = tid ? OBJ_obj2nid(tid) : 0;
                ASN1_OBJECT_free(tid);
                /* secretValue [0] EXPLICIT OCTET STRING */
                if (ASN1_get_object(&q, &clen, &tag, &cls, avail) != 0x80 &&
                    tag == 0 && cls == V_ASN1_CONTEXT_SPECIFIC) {
                    ASN1_OCTET_STRING *oct =
                        d2i_ASN1_OCTET_STRING(NULL, &q, clen);
                    if (oct && oct->data && oct->length > 0) {
                        if (tid_nid == NID_pkcs8ShroudedKeyBag &&
                            oct->length > 0) {
                            /* Java layout: EncryptedPrivateKeyInfo DER */
                            const unsigned char *vp = oct->data;
                            X509_SIG *sig = d2i_X509_SIG(NULL, &vp,
                                                         oct->length);
                            if (sig) {
                                const X509_ALGOR *algor = NULL;
                                const ASN1_OCTET_STRING *sig_oct = NULL;
                                X509_SIG_get0(sig, &algor, &sig_oct);
                                PKCS8_PRIV_KEY_INFO *p8 =
                                    (PKCS8_PRIV_KEY_INFO *)PKCS12_item_decrypt_d2i(
                                        algor,
                                        ASN1_ITEM_rptr(PKCS8_PRIV_KEY_INFO),
                                        pass, -1, sig_oct, 0);
                                if (p8) {
                                    const unsigned char *key = NULL;
                                    int key_len = 0;
                                    if (PKCS8_pkey_get0(NULL, &key, &key_len,
                                                        NULL, p8) &&
                                        key && key_len > 0) {
                                        unsigned char *copy =
                                            malloc((size_t)key_len);
                                        if (copy) {
                                            memcpy(copy, key,
                                                   (size_t)key_len);
                                            *out = copy;
                                            *out_len = (size_t)key_len;
                                            rc = 0;
                                        }
                                    }
                                    PKCS8_PRIV_KEY_INFO_free(p8);
                                }
                                X509_SIG_free(sig);
                            }
                        } else if (oct->length == 16 || oct->length == 24 ||
                                   oct->length == 32) {
                            /* OpenSSL layout: raw key bytes */
                            unsigned char *copy = malloc((size_t)oct->length);
                            if (copy) {
                                memcpy(copy, oct->data,
                                       (size_t)oct->length);
                                *out = copy;
                                *out_len = (size_t)oct->length;
                                rc = 0;
                            }
                        }
                    }
                    ASN1_OCTET_STRING_free(oct);
                }
            }
        }
    }
    free(der);
    return rc;
}

/* Extracts the raw AES key bytes for `alias` from a PKCS#12 file.
 * Returns 0 + malloc'd *out on success, -1 on error (or key not found). */
static int keystore_get_key(const char *path, const char *alias,
                            const char *pass, unsigned char **out,
                            size_t *out_len)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        if (errno == ENOENT) {
            set_error("No secret key found for alias: %s", alias);
            return -1;
        }
        set_error("Failed to open keystore: %s", strerror(errno));
        return -1;
    }
    PKCS12 *p12 = d2i_PKCS12_fp(fp, NULL);
    fclose(fp);
    if (!p12) {
        set_error("Keystore is not a valid PKCS#12 file (or password wrong): %s", "");
        return -1;
    }

    STACK_OF(PKCS7) *safes = PKCS12_unpack_authsafes(p12);
    if (!safes) {
        PKCS12_free(p12);
        set_error("Keystore contains no safe contents: %s", "");
        return -1;
    }

    int found = 0;
    int n_safes = sk_PKCS7_num(safes);
    for (int s = 0; s < n_safes && !found; s++) {
        PKCS7 *safe = sk_PKCS7_value(safes, s);
        STACK_OF(PKCS12_SAFEBAG) *bags = PKCS12_unpack_p7data(safe);
        if (!bags)
            continue;
        int n_bags = sk_PKCS12_SAFEBAG_num(bags);
        for (int b = 0; b < n_bags && !found; b++) {
            PKCS12_SAFEBAG *bag = sk_PKCS12_SAFEBAG_value(bags, b);
            int bag_nid = OBJ_obj2nid(PKCS12_SAFEBAG_get0_type(bag));
            if (bag_nid != NID_secretBag && bag_nid != NID_pkcs8ShroudedKeyBag)
                continue;
            if (!bag_matches_alias(bag, alias))
                continue;
            if (bag_nid == NID_secretBag) {
                if (secret_bag_get_key(bag, pass, out, out_len) != 0)
                    continue;
                found = 1;
            } else {
                const X509_SIG *sig = PKCS12_SAFEBAG_get0_pkcs8(bag);
                const X509_ALGOR *algor = NULL;
                const ASN1_OCTET_STRING *oct = NULL;
                X509_SIG_get0(sig, &algor, &oct);
                PKCS8_PRIV_KEY_INFO *p8 = (PKCS8_PRIV_KEY_INFO *)PKCS12_item_decrypt_d2i(
                    algor, ASN1_ITEM_rptr(PKCS8_PRIV_KEY_INFO), pass, -1, oct, 0);
                if (!p8)
                    continue;
                const unsigned char *key = NULL;
                int key_len = 0;
                if (PKCS8_pkey_get0(NULL, &key, &key_len, NULL, p8) && key && key_len > 0) {
                    unsigned char *copy = malloc((size_t)key_len);
                    if (copy) {
                        memcpy(copy, key, (size_t)key_len);
                        *out = copy;
                        *out_len = (size_t)key_len;
                        found = 1;
                    }
                }
                PKCS8_PRIV_KEY_INFO_free(p8);
            }
        }
        sk_PKCS12_SAFEBAG_pop_free(bags, PKCS12_SAFEBAG_free);
    }
    sk_PKCS7_pop_free(safes, PKCS7_free);
    PKCS12_free(p12);

    if (!found) {
        set_error("No secret key found for alias (or password wrong): %s", alias);
        return -1;
    }
    return 0;
}

/* Creates a PKCS#12 keystore with the given raw AES key under `alias`,
 * using Java's exact secret-bag layout: secretBag { secretTypeId =
 * pkcs8ShroudedKeyBag, secretValue = EncryptedPrivateKeyInfo DER }.
 * Overwrites `path`. */
static int keystore_write(const char *path, const char *alias, const char *pass,
                          const unsigned char *key, size_t key_len)
{
    if (key_len != 16 && key_len != 24 && key_len != 32) {
        set_error("Unsupported AES key length: %zu", "");
        return -1;
    }

    PKCS8_PRIV_KEY_INFO *p8 = PKCS8_PRIV_KEY_INFO_new();
    if (!p8)
        goto fail;
    /* pkeyalg: AES-256 (OID 2.16.840.1.101.3.4.1.42), no parameters;
     * pkey: raw key bytes (PKCS8_pkey_set0 takes ownership of penc) */
    unsigned char *key_copy = malloc(key_len);
    if (!key_copy)
        goto fail;
    memcpy(key_copy, key, key_len);
    if (PKCS8_pkey_set0(p8, OBJ_nid2obj(NID_aes_256_cbc), 0, V_ASN1_UNDEF,
                        NULL, key_copy, (int)key_len) != 1)
        goto fail;

    unsigned char salt[20];
    if (RAND_bytes(salt, sizeof(salt)) != 1)
        goto fail;
    X509_SIG *sig = PKCS8_encrypt(-1, EVP_aes_256_cbc(), pass, -1,
                                  salt, (int)sizeof(salt), 10000, p8);
    PKCS8_PRIV_KEY_INFO_free(p8);
    p8 = NULL;
    if (!sig)
        goto fail;
    int sig_len = i2d_X509_SIG(sig, NULL);
    unsigned char *sig_der = NULL;
    if (sig_len <= 0)
        goto fail;
    sig_der = malloc((size_t)sig_len);
    if (!sig_der)
        goto fail;
    unsigned char *sp = sig_der;
    i2d_X509_SIG(sig, &sp);
    X509_SIG_free(sig);

    PKCS12_SAFEBAG *bag = PKCS12_SAFEBAG_create_secret(
        NID_pkcs8ShroudedKeyBag, V_ASN1_OCTET_STRING, sig_der, sig_len);
    free(sig_der);
    if (!bag)
        goto fail;
    if (!PKCS12_add_friendlyname_asc(bag, alias, -1))
        goto fail;
    unsigned char keyid[20];
    if (RAND_bytes(keyid, sizeof(keyid)) != 1)
        goto fail;
    if (!PKCS12_add_localkeyid(bag, keyid, (int)sizeof(keyid)))
        goto fail;

    STACK_OF(PKCS12_SAFEBAG) *bags = sk_PKCS12_SAFEBAG_new_null();
    if (!bags || !sk_PKCS12_SAFEBAG_push(bags, bag))
        goto fail;
    PKCS7 *p7 = PKCS12_pack_p7data(bags);
    if (!p7)
        goto fail;
    STACK_OF(PKCS7) *safes = sk_PKCS7_new_null();
    if (!safes || !sk_PKCS7_push(safes, p7))
        goto fail;
    PKCS12 *p12 = PKCS12_add_safes(safes, NID_pkcs7_data);
    if (!p12)
        goto fail;
    unsigned char mac_salt[20];
    if (RAND_bytes(mac_salt, sizeof(mac_salt)) != 1)
        goto fail;
    if (!PKCS12_set_mac(p12, pass, -1, mac_salt, (int)sizeof(mac_salt), 10000,
                        EVP_sha256()))
        goto fail;

    FILE *fp = fopen(path, "wb");
    if (!fp) {
        set_error("Failed to write keystore: %s", strerror(errno));
        PKCS12_free(p12);
        return -1;
    }
    int ok = i2d_PKCS12_fp(fp, p12);
    fclose(fp);
    PKCS12_free(p12);
    if (ok != 1) {
        set_error("Failed to serialize keystore: %s", "");
        return -1;
    }
    return 0;

fail:
    if (p8)
        PKCS8_PRIV_KEY_INFO_free(p8);
    char ebuf[256];
    unsigned long e;
    while ((e = ERR_get_error()) != 0) {
        ERR_error_string_n(e, ebuf, sizeof(ebuf));
        set_error("Failed to write keystore: %s", ebuf);
    }
    return -1;
}

/* ------------------------------------------------------------------ */
/* Exported C API                                                      */
/* ------------------------------------------------------------------ */

/* 1 if the keystore holds `alias`, 0 if not, -1 on error. */
/* 1 if the alias holds a secret key decryptable with pass, 0 if not,
 * -1 on hard errors (missing/corrupt file). */
int itk_keystore_has_alias(const char *path, const char *alias, const char *pass)
{
    unsigned char *key = NULL;
    size_t key_len = 0;
    if (keystore_get_key(path, alias, pass, &key, &key_len) != 0) {
        if (strstr(g_errbuf, "No secret key found"))
            return 0;
        return -1;
    }
    free(key);
    return 1;
}

/* 0 if the PKCS#12 file parses and the store password verifies (MAC check),
 * -1 otherwise (missing/corrupt file or wrong password). */
int itk_keystore_password_valid(const char *path, const char *pass)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        set_error("Failed to open keystore: %s", strerror(errno));
        return -1;
    }
    PKCS12 *p12 = d2i_PKCS12_fp(fp, NULL);
    fclose(fp);
    if (!p12) {
        set_error("Keystore is not a valid PKCS#12 file: %s", "");
        return -1;
    }
    int ok = PKCS12_verify_mac(p12, pass, -1);
    PKCS12_free(p12);
    if (ok != 1) {
        set_error("Password incorrect for keystore: %s", "");
        return -1;
    }
    return 0;
}

/* 0 on success; *out receives a malloc'd copy of the raw AES key (caller
 * must itk_free()). -1 on error. */
int itk_keystore_get_key(const char *path, const char *alias, const char *pass,
                         unsigned char **out, size_t *out_len)
{
    unsigned char *key = NULL;
    size_t key_len = 0;
    if (keystore_get_key(path, alias, pass, &key, &key_len) != 0)
        return -1;
    *out = key;
    *out_len = key_len;
    return 0;
}

/* Load-or-create semantics matching Kotlin KeyInitializer.initializeKeystore():
 * if the alias already holds a usable secret key, leaves the file untouched;
 * otherwise (re)generates a 256-bit AES key and writes the keystore. */
int itk_keystore_ensure(const char *path, const char *alias, const char *pass)
{
    unsigned char *key = NULL;
    size_t key_len = 0;
    if (keystore_get_key(path, alias, pass, &key, &key_len) == 0) {
        free(key);
        return 0;
    }
    if (strstr(g_errbuf, "No secret key found") == NULL)
        return -1; /* exists but unreadable -> real error */

    unsigned char new_key[32];
    if (RAND_bytes(new_key, sizeof(new_key)) != 1) {
        set_error("RAND_bytes failed: %s", "");
        return -1;
    }
    if (keystore_write(path, alias, pass, new_key, sizeof(new_key)) != 0)
        return -1;
    return 0;
}

/* Vault file format: [int32 BE IV_LEN][IV][AES-GCM ciphertext][16-byte tag]. */
int itk_vault_encrypt(const unsigned char *key, size_t key_len,
                      const char *vault_path, const unsigned char *plain,
                      size_t plain_len)
{
    const EVP_CIPHER *cipher = NULL;
    if (key_len == 16)
        cipher = EVP_aes_128_gcm();
    else if (key_len == 24)
        cipher = EVP_aes_192_gcm();
    else if (key_len == 32)
        cipher = EVP_aes_256_gcm();
    else {
        set_error("Unsupported AES key length: %zu", "");
        return -1;
    }

    unsigned char iv[12];
    if (RAND_bytes(iv, sizeof(iv)) != 1) {
        set_error("RAND_bytes failed: %s", "");
        return -1;
    }

    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    if (!ctx) {
        set_error("Out of memory: %s", "");
        return -1;
    }
    int ok = 0;
    do {
        if (EVP_EncryptInit_ex(ctx, cipher, NULL, NULL, NULL) != 1)
            break;
        if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, (int)sizeof(iv), NULL) != 1)
            break;
        if (EVP_EncryptInit_ex(ctx, NULL, NULL, key, iv) != 1)
            break;

        unsigned char *ct = malloc(plain_len + 16);
        if (!ct)
            break;
        int ct_len = 0, final_len = 0;
        if (EVP_EncryptUpdate(ctx, ct, &ct_len, plain, (int)plain_len) != 1) {
            free(ct);
            break;
        }
        if (EVP_EncryptFinal_ex(ctx, ct + ct_len, &final_len) != 1) {
            free(ct);
            break;
        }
        ct_len += final_len;
        if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, 16, ct + ct_len) != 1) {
            free(ct);
            break;
        }
        ct_len += 16;

        FILE *fp = fopen(vault_path, "wb");
        if (!fp) {
            set_error("Failed to write vault: %s", strerror(errno));
            free(ct);
            break;
        }
        unsigned char be[4] = {0, 0, 0, 12};
        fwrite(be, 1, 4, fp); /* IV length, big-endian */
        fwrite(iv, 1, sizeof(iv), fp);
        fwrite(ct, 1, (size_t)ct_len, fp);
        fclose(fp);
        free(ct);
        ok = 1;
    } while (0);
    EVP_CIPHER_CTX_free(ctx);
    if (!ok)
        set_error("Encryption failed: %s", "");
    return ok ? 0 : -1;
}

/* 0 on success; *out receives a malloc'd plaintext (caller must
 * itk_free()). -1 on error (incl. authentication failure / missing file). */
int itk_vault_decrypt(const unsigned char *key, size_t key_len,
                      const char *vault_path, unsigned char **out,
                      size_t *out_len)
{
    const EVP_CIPHER *cipher = NULL;
    if (key_len == 16)
        cipher = EVP_aes_128_gcm();
    else if (key_len == 24)
        cipher = EVP_aes_192_gcm();
    else if (key_len == 32)
        cipher = EVP_aes_256_gcm();
    else {
        set_error("Unsupported AES key length: %zu", "");
        return -1;
    }

    FILE *fp = fopen(vault_path, "rb");
    if (!fp) {
        set_error("Vault file not found: %s", strerror(errno));
        return -1;
    }
    unsigned char be_len[4] = {0};
    if (fread(be_len, 1, 4, fp) != 4) {
        fclose(fp);
        set_error("Vault file is empty or truncated: %s", "");
        return -1;
    }
    int iv_len = (int)((be_len[0] << 24) | (be_len[1] << 16) | (be_len[2] << 8) | be_len[3]);
    if (iv_len != 12) {
        fclose(fp);
        set_error("Invalid IV length in vault file: %s", "");
        return -1;
    }
    unsigned char iv[12];
    if (fread(iv, 1, sizeof(iv), fp) != sizeof(iv)) {
        fclose(fp);
        set_error("Vault file is truncated: %s", "");
        return -1;
    }
    fseek(fp, 0, SEEK_END);
    long file_len = ftell(fp);
    if (file_len <= 4 + (long)sizeof(iv)) {
        fclose(fp);
        set_error("Vault file is empty or truncated: %s", "");
        return -1;
    }
    long ct_len = file_len - 4 - (long)sizeof(iv);
    fseek(fp, 4 + (long)sizeof(iv), SEEK_SET);
    unsigned char *buf = malloc((size_t)ct_len);
    if (!buf) {
        fclose(fp);
        set_error("Out of memory: %s", "");
        return -1;
    }
    if (fread(buf, 1, (size_t)ct_len, fp) != (size_t)ct_len) {
        free(buf);
        fclose(fp);
        set_error("Vault file read failed: %s", "");
        return -1;
    }
    fclose(fp);

    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    if (!ctx) {
        free(buf);
        set_error("Out of memory: %s", "");
        return -1;
    }
    int ok = 0;
    do {
        if (EVP_DecryptInit_ex(ctx, cipher, NULL, NULL, NULL) != 1)
            break;
        if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, (int)sizeof(iv), NULL) != 1)
            break;
        if (EVP_DecryptInit_ex(ctx, NULL, NULL, key, iv) != 1)
            break;
        if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, 16, buf + (ct_len - 16)) != 1)
            break;

        unsigned char *pt = malloc((size_t)ct_len);
        if (!pt)
            break;
        int pt_len = 0, final_len = 0;
        if (EVP_DecryptUpdate(ctx, pt, &pt_len, buf, (int)(ct_len - 16)) != 1) {
            free(pt);
            break;
        }
        if (EVP_DecryptFinal_ex(ctx, pt + pt_len, &final_len) != 1) {
            free(pt);
            break;
        }
        pt_len += final_len;
        free(buf);
        *out = pt;
        *out_len = (size_t)pt_len;
        ok = 1;
    } while (0);
    EVP_CIPHER_CTX_free(ctx);
    if (!ok) {
        free(buf);
        set_error("Vault decryption failed (wrong key or tampered data): %s", "");
    }
    return ok ? 0 : -1;
}

#ifdef __cplusplus
}
#endif
