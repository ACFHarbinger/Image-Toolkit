// ---------------------------------------------------------------------------
// backend/src/vault/vault.cpp
//
// Vault in the C++ core (Issue #879, Wave 0e W0-15):
//   - Unlock keystore / password + salt held in C++ memory
//   - Master DEK and derived store DEKs held in LockedSecret<32>
//   - Session handles returned to webview / sidecar (e.g. "vses_<hex>")
//   - Sealed per-store leases for daemons (e.g. cloud_jobs, library)
//   - Tamper-proof, process-bound, TTL-expiring AEAD lease tokens
// ---------------------------------------------------------------------------

#include "vault/vault.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <sodium.h>
#include <argon2.h>

#include <cstdint>
#include <cstring>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <vector>

#ifdef _WIN32
#include <io.h>
#include <process.h>
#define GETPID _getpid
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#define GETPID getpid
#endif

namespace py = pybind11;
namespace fs = std::filesystem;

extern "C" {
    int itk_keystore_get_key(const char *path, const char *alias, const char *pass,
                             unsigned char **out, size_t *out_len);
    void itk_free(void *p);
    const char *itk_last_error(void);
}

namespace base::vault {

namespace {

constexpr int OPSLIMIT  = 2;     // crypto_pwhash_OPSLIMIT_INTERACTIVE
constexpr int MEM_KB    = 19456; // 19 MB — matches base.secret and base.database parameters
const unsigned char LEASE_AEAD_AD[] = "ITK_LEASE";

// Portable Big-Endian packing helpers
inline void pack_u16_be(uint8_t* p, uint16_t v) {
    p[0] = static_cast<uint8_t>((v >> 8) & 0xFF);
    p[1] = static_cast<uint8_t>(v & 0xFF);
}

inline uint16_t unpack_u16_be(const uint8_t* p) {
    return (static_cast<uint16_t>(p[0]) << 8) | static_cast<uint16_t>(p[1]);
}

inline void pack_u64_be(uint8_t* p, uint64_t v) {
    for (int i = 7; i >= 0; --i) {
        p[i] = static_cast<uint8_t>(v & 0xFF);
        v >>= 8;
    }
}

inline uint64_t unpack_u64_be(const uint8_t* p) {
    uint64_t v = 0;
    for (int i = 0; i < 8; ++i) {
        v = (v << 8) | static_cast<uint64_t>(p[i]);
    }
    return v;
}

inline void pack_i64_be(uint8_t* p, int64_t v) {
    pack_u64_be(p, static_cast<uint64_t>(v));
}

inline int64_t unpack_i64_be(const uint8_t* p) {
    return static_cast<int64_t>(unpack_u64_be(p));
}

// ---------------------------------------------------------------------------
// Base64URL Encoding & Decoding (RFC 4648 §5, unpadded)
// ---------------------------------------------------------------------------

static const char B64_CHARS[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

std::string base64url_encode(const uint8_t* data, size_t len) {
    std::string out;
    out.reserve(((len + 2) / 3) * 4);
    size_t full_groups = len / 3;
    size_t rem = len % 3;
    size_t i = 0;

    for (size_t g = 0; g < full_groups; ++g) {
        uint32_t b0 = data[i++];
        uint32_t b1 = data[i++];
        uint32_t b2 = data[i++];
        uint32_t triple = (b0 << 16) | (b1 << 8) | b2;

        out.push_back(B64_CHARS[(triple >> 18) & 0x3F]);
        out.push_back(B64_CHARS[(triple >> 12) & 0x3F]);
        out.push_back(B64_CHARS[(triple >> 6) & 0x3F]);
        out.push_back(B64_CHARS[triple & 0x3F]);
    }

    if (rem == 1) {
        uint32_t b0 = data[i++];
        uint32_t val = (b0 << 4);
        out.push_back(B64_CHARS[(val >> 6) & 0x3F]);
        out.push_back(B64_CHARS[val & 0x3F]);
    } else if (rem == 2) {
        uint32_t b0 = data[i++];
        uint32_t b1 = data[i++];
        uint32_t val = (b0 << 10) | (b1 << 2);
        out.push_back(B64_CHARS[(val >> 12) & 0x3F]);
        out.push_back(B64_CHARS[(val >> 6) & 0x3F]);
        out.push_back(B64_CHARS[val & 0x3F]);
    }

    return out;
}

std::vector<uint8_t> base64url_decode(const std::string& in) {
    std::vector<uint8_t> out;
    if (in.empty()) return out;

    auto decode_char = [](char c) -> int {
        if (c >= 'A' && c <= 'Z') return c - 'A';
        if (c >= 'a' && c <= 'z') return c - 'a' + 26;
        if (c >= '0' && c <= '9') return c - '0' + 52;
        if (c == '-' || c == '+') return 62;
        if (c == '_' || c == '/') return 63;
        if (c == '=') return -2; // padding
        return -1;               // invalid
    };

    uint32_t buf = 0;
    int bits = 0;
    for (char c : in) {
        int val = decode_char(c);
        if (val == -2) break; // stop at padding
        if (val < 0) throw std::runtime_error("base.vault: invalid character in base64url token");
        buf = (buf << 6) | static_cast<uint32_t>(val);
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            out.push_back(static_cast<uint8_t>((buf >> bits) & 0xFF));
        }
    }
    return out;
}

// ---------------------------------------------------------------------------
// Global Vault State
// ---------------------------------------------------------------------------

std::mutex g_session_mutex;
std::unordered_map<std::string, std::shared_ptr<base::secret::LockedSecret<32>>> g_sessions;

std::mutex g_transit_mutex;
std::shared_ptr<base::secret::LockedSecret<32>> g_in_memory_transit_key;

void ensure_sodium_init() {
    static std::once_flag init_flag;
    std::call_once(init_flag, []() {
        if (sodium_init() < 0) {
            throw std::runtime_error("base.vault: libsodium initialization failed");
        }
    });
}

// Generate random session handle: "vses_" + 32 hex chars
std::string generate_session_handle() {
    ensure_sodium_init();
    unsigned char rnd[16];
    randombytes_buf(rnd, sizeof(rnd));
    std::ostringstream oss;
    oss << "vses_";
    for (int i = 0; i < 16; ++i) {
        oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(rnd[i]);
    }
    return oss.str();
}

} // namespace

// ---------------------------------------------------------------------------
// Session Management Implementation
// ---------------------------------------------------------------------------

std::string unlock_direct(const std::string& password, const std::string& salt_str) {
    ensure_sodium_init();
    auto dek = std::make_shared<base::secret::LockedSecret<32>>();

    std::vector<uint8_t> salt(32, 0);
    crypto_hash_sha256(salt.data(),
                       reinterpret_cast<const unsigned char*>(salt_str.c_str()),
                       salt_str.size());

    int rc = argon2id_hash_raw(OPSLIMIT, MEM_KB, 1,
                               password.c_str(), password.size(),
                               salt.data(), salt.size(),
                               dek->data(), dek->size());
    if (rc != ARGON2_OK) {
        throw std::runtime_error("base.vault: Argon2id key derivation failed");
    }

    std::string handle = generate_session_handle();
    {
        std::lock_guard<std::mutex> lock(g_session_mutex);
        g_sessions[handle] = dek;
    }
    return handle;
}

std::string unlock_keystore(const std::string& keystore_path,
                            const std::string& alias,
                            const std::string& password) {
    ensure_sodium_init();
    unsigned char* raw_key = nullptr;
    size_t key_len = 0;

    int rc = itk_keystore_get_key(keystore_path.c_str(), alias.c_str(), password.c_str(),
                                  &raw_key, &key_len);
    if (rc != 0) {
        const char* err = itk_last_error();
        throw std::runtime_error(std::string("base.vault: failed to unlock keystore: ") +
                                 (err ? err : "wrong password or alias not found"));
    }

    if (!raw_key || key_len != 32) {
        if (raw_key) {
            sodium_memzero(raw_key, key_len);
            itk_free(raw_key);
        }
        throw std::runtime_error("base.vault: keystore key is not 32 bytes (expected AES-256)");
    }

    auto dek = std::make_shared<base::secret::LockedSecret<32>>();
    std::memcpy(dek->data(), raw_key, 32);
    sodium_memzero(raw_key, key_len);
    itk_free(raw_key);

    std::string handle = generate_session_handle();
    {
        std::lock_guard<std::mutex> lock(g_session_mutex);
        g_sessions[handle] = dek;
    }
    return handle;
}

bool is_unlocked(const std::string& session_handle) {
    if (session_handle.empty()) return false;
    std::lock_guard<std::mutex> lock(g_session_mutex);
    return g_sessions.find(session_handle) != g_sessions.end();
}

bool lock(const std::string& session_handle) {
    if (session_handle.empty()) return false;
    std::lock_guard<std::mutex> lock(g_session_mutex);
    auto it = g_sessions.find(session_handle);
    if (it != g_sessions.end()) {
        g_sessions.erase(it);
        return true;
    }
    return false;
}

void lock_all() {
    std::lock_guard<std::mutex> lock(g_session_mutex);
    g_sessions.clear();
}

std::vector<std::string> active_sessions() {
    std::lock_guard<std::mutex> lock(g_session_mutex);
    std::vector<std::string> res;
    res.reserve(g_sessions.size());
    for (const auto& [handle, _] : g_sessions) {
        res.push_back(handle);
    }
    return res;
}

std::shared_ptr<base::secret::LockedSecret<32>> get_session_master_dek(
    const std::string& session_handle) {
    std::lock_guard<std::mutex> lock(g_session_mutex);
    auto it = g_sessions.find(session_handle);
    if (it == g_sessions.end()) {
        throw std::runtime_error("base.vault: active session not found or locked: " + session_handle);
    }
    return it->second;
}

std::shared_ptr<base::secret::LockedSecret<32>> derive_store_dek(
    const std::string& session_handle,
    const std::string& store_name) {
    auto master = get_session_master_dek(session_handle);
    auto store_dek = std::make_shared<base::secret::LockedSecret<32>>();

    if (store_name == "library" || store_name == "master") {
        std::memcpy(store_dek->data(), master->data(), 32);
        return store_dek;
    }

    // Derive deterministic store subkey via BLAKE2b keyed hash
    ensure_sodium_init();
    std::string ctx = "itk_store_dek:" + store_name;
    if (crypto_generichash(store_dek->data(), 32,
                           reinterpret_cast<const unsigned char*>(ctx.c_str()),
                           ctx.size(),
                           master->data(), 32) != 0) {
        throw std::runtime_error("base.vault: store subkey derivation failed for: " + store_name);
    }
    return store_dek;
}

// ---------------------------------------------------------------------------
// Transit Key Implementation
// ---------------------------------------------------------------------------

std::string get_transit_key_path() {
    const char* env_path = std::getenv("ITK_TRANSIT_KEY_FILE");
    if (env_path && env_path[0]) {
        return env_path;
    }

    std::string root;
    const char* itk_dir = std::getenv("IMAGE_TOOLKIT_DIR");
    if (itk_dir && itk_dir[0]) {
        root = itk_dir;
    } else {
        const char* home = std::getenv("HOME");
        if (home && home[0]) {
            root = std::string(home) + "/.image-toolkit";
        } else {
            root = ".";
        }
    }
    return root + "/secrets/.lease_transit.key";
}

void set_transit_key(const std::vector<uint8_t>& key) {
    if (key.size() != 32) {
        throw std::invalid_argument("base.vault: transit key must be exactly 32 bytes");
    }
    std::lock_guard<std::mutex> lock(g_transit_mutex);
    g_in_memory_transit_key = std::make_shared<base::secret::LockedSecret<32>>();
    std::memcpy(g_in_memory_transit_key->data(), key.data(), 32);
}

void clear_transit_key() {
    std::lock_guard<std::mutex> lock(g_transit_mutex);
    g_in_memory_transit_key.reset();
}

static std::shared_ptr<base::secret::LockedSecret<32>> get_or_create_transit_key() {
    std::lock_guard<std::mutex> lock(g_transit_mutex);
    if (g_in_memory_transit_key) {
        return g_in_memory_transit_key;
    }

    ensure_sodium_init();

    // Check env var ITK_TRANSIT_KEY (hex 64 chars)
    const char* env_raw = std::getenv("ITK_TRANSIT_KEY");
    if (env_raw && env_raw[0]) {
        std::string raw_s(env_raw);
        if (raw_s.size() == 64) {
            auto k = std::make_shared<base::secret::LockedSecret<32>>();
            for (size_t i = 0; i < 32; ++i) {
                unsigned int byte_val = 0;
                std::stringstream ss;
                ss << std::hex << raw_s.substr(i * 2, 2);
                ss >> byte_val;
                k->data()[i] = static_cast<uint8_t>(byte_val);
            }
            g_in_memory_transit_key = k;
            return g_in_memory_transit_key;
        }
    }

    std::string key_path = get_transit_key_path();
    fs::path p(key_path);

    if (fs::exists(p)) {
        std::ifstream ifs(key_path, std::ios::binary);
        if (!ifs) {
            throw std::runtime_error("base.vault: cannot read transit key file at: " + key_path);
        }
        auto k = std::make_shared<base::secret::LockedSecret<32>>();
        ifs.read(reinterpret_cast<char*>(k->data()), 32);
        if (ifs.gcount() != 32) {
            throw std::runtime_error("base.vault: corrupt transit key file (expected 32 bytes): " + key_path);
        }
        g_in_memory_transit_key = k;
        return g_in_memory_transit_key;
    }

    // File does not exist — create parent dir and file with 0600 permissions
    fs::create_directories(p.parent_path());
    auto k = std::make_shared<base::secret::LockedSecret<32>>();
    randombytes_buf(k->data(), 32);

#ifdef _WIN32
    std::ofstream ofs(key_path, std::ios::binary);
    if (!ofs) {
        throw std::runtime_error("base.vault: cannot create transit key file at: " + key_path);
    }
    ofs.write(reinterpret_cast<const char*>(k->data()), 32);
    ofs.close();
#else
    int fd = open(key_path.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (fd < 0) {
        if (errno == EEXIST) {
            std::ifstream ifs(key_path, std::ios::binary);
            if (!ifs) throw std::runtime_error("base.vault: cannot read existing transit key: " + key_path);
            ifs.read(reinterpret_cast<char*>(k->data()), 32);
            if (ifs.gcount() != 32) throw std::runtime_error("base.vault: corrupt transit key: " + key_path);
        } else {
            throw std::runtime_error("base.vault: failed to create transit key file at: " + key_path);
        }
    } else {
        ssize_t written = write(fd, k->data(), 32);
        close(fd);
        if (written != 32) {
            fs::remove(p);
            throw std::runtime_error("base.vault: incomplete write to transit key file");
        }
    }
#endif

    g_in_memory_transit_key = k;
    return g_in_memory_transit_key;
}

// ---------------------------------------------------------------------------
// Sealed Leases Implementation
// ---------------------------------------------------------------------------

static std::string seal_store_payload(
    const std::string& store_name,
    const uint8_t* store_dek_bytes,
    int64_t pid,
    uint64_t ttl_seconds,
    const std::string& supervisor_session) {
    ensure_sodium_init();

    uint64_t now = static_cast<uint64_t>(std::time(nullptr));
    uint64_t expires_at = (ttl_seconds > 0) ? (now + ttl_seconds) : 0;

    uint8_t flags = 0;
    if (expires_at > 0) flags |= 0x01;
    if (pid > 0) flags |= 0x02;
    if (!supervisor_session.empty()) flags |= 0x04;

    if (store_name.size() > 1024 || supervisor_session.size() > 1024) {
        throw std::invalid_argument("base.vault: store name or supervisor session is too long");
    }
    uint16_t store_len = static_cast<uint16_t>(store_name.size());
    uint16_t sup_len = static_cast<uint16_t>(supervisor_session.size());

    // Payload construction:
    // [Magic: 4 ('I','T','K','L')][Version: 1][Flags: 1]
    // [store_len: 2 BE][store_name: N]
    // [store_dek: 32]
    // [created_at: 8 BE][expires_at: 8 BE]
    // [bound_pid: 8 BE]
    // [sup_len: 2 BE][supervisor_session: M]
    // [nonce_entropy: 16]

    size_t payload_len = 4 + 1 + 1 + 2 + store_len + 32 + 8 + 8 + 8 + 2 + sup_len + 16;
    std::vector<uint8_t> payload(payload_len, 0);
    uint8_t* ptr = payload.data();

    ptr[0] = 'I'; ptr[1] = 'T'; ptr[2] = 'K'; ptr[3] = 'L';
    ptr[4] = 0x01; // version 1
    ptr[5] = flags;
    ptr += 6;

    pack_u16_be(ptr, store_len);
    ptr += 2;
    std::memcpy(ptr, store_name.data(), store_len);
    ptr += store_len;

    std::memcpy(ptr, store_dek_bytes, 32);
    ptr += 32;

    pack_u64_be(ptr, now);
    ptr += 8;
    pack_u64_be(ptr, expires_at);
    ptr += 8;
    pack_i64_be(ptr, pid);
    ptr += 8;

    pack_u16_be(ptr, sup_len);
    ptr += 2;
    if (sup_len > 0) {
        std::memcpy(ptr, supervisor_session.data(), sup_len);
        ptr += sup_len;
    }

    randombytes_buf(ptr, 16);
    ptr += 16;

    // Sealing with AEAD XChaCha20-Poly1305
    auto transit_key = get_or_create_transit_key();
    uint8_t nonce[crypto_aead_xchacha20poly1305_ietf_NPUBBYTES];
    randombytes_buf(nonce, sizeof(nonce));

    std::vector<uint8_t> ciphertext(payload_len + crypto_aead_xchacha20poly1305_ietf_ABYTES);
    unsigned long long clen = 0;

    int rc = crypto_aead_xchacha20poly1305_ietf_encrypt(
        ciphertext.data(), &clen,
        payload.data(), payload.size(),
        LEASE_AEAD_AD, sizeof(LEASE_AEAD_AD) - 1,
        nullptr, nonce, transit_key->data());

    sodium_memzero(payload.data(), payload.size());

    if (rc != 0) {
        throw std::runtime_error("base.vault: AEAD encryption failed for store lease");
    }

    // Combine: [nonce: 24 bytes][ciphertext: clen bytes]
    std::vector<uint8_t> blob;
    blob.reserve(sizeof(nonce) + clen);
    blob.insert(blob.end(), nonce, nonce + sizeof(nonce));
    blob.insert(blob.end(), ciphertext.data(), ciphertext.data() + clen);

    return "itkl_v1_" + base64url_encode(blob.data(), blob.size());
}

std::string unlock_raw(const std::vector<uint8_t>& key) {
    if (key.size() != 32) {
        throw std::invalid_argument("base.vault: raw key must be exactly 32 bytes");
    }
    ensure_sodium_init();
    auto dek = std::make_shared<base::secret::LockedSecret<32>>();
    std::memcpy(dek->data(), key.data(), 32);
    std::string handle = generate_session_handle();
    {
        std::lock_guard<std::mutex> lock(g_session_mutex);
        g_sessions[handle] = dek;
    }
    return handle;
}

std::string create_store_lease(
    const std::string& session_handle,
    const std::string& store_name,
    int64_t pid,
    uint64_t ttl_seconds,
    const std::string& supervisor_session) {
    if (store_name.empty()) {
        throw std::invalid_argument("base.vault: store_name cannot be empty");
    }
    auto store_dek = derive_store_dek(session_handle, store_name);
    return seal_store_payload(store_name, store_dek->data(), pid, ttl_seconds, supervisor_session);
}

std::string create_raw_store_lease(
    const std::string& store_name,
    const std::vector<uint8_t>& raw_key,
    int64_t pid,
    uint64_t ttl_seconds,
    const std::string& supervisor_session) {
    if (store_name.empty()) {
        throw std::invalid_argument("base.vault: store_name cannot be empty");
    }
    if (raw_key.size() != 32) {
        throw std::invalid_argument("base.vault: raw_key must be exactly 32 bytes");
    }
    return seal_store_payload(store_name, raw_key.data(), pid, ttl_seconds, supervisor_session);
}

StoreLeaseInfo unseal_store_lease(
    const std::string& lease_token,
    const std::string& expected_store,
    bool enforce_validity) {
    ensure_sodium_init();

    constexpr const char* PREFIX = "itkl_v1_";
    constexpr size_t PREFIX_LEN = 8;
    if (lease_token.rfind(PREFIX, 0) != 0) {
        throw std::runtime_error("base.vault: invalid lease token format (missing itkl_v1_ prefix)");
    }

    std::string b64_payload = lease_token.substr(PREFIX_LEN);
    std::vector<uint8_t> blob = base64url_decode(b64_payload);

    constexpr size_t NONCE_LEN = crypto_aead_xchacha20poly1305_ietf_NPUBBYTES;
    constexpr size_t TAG_LEN = crypto_aead_xchacha20poly1305_ietf_ABYTES;
    constexpr size_t MIN_PAYLOAD = 4 + 1 + 1 + 2 + 32 + 8 + 8 + 8 + 2 + 16; // 82 bytes

    if (blob.size() < NONCE_LEN + TAG_LEN + MIN_PAYLOAD) {
        throw std::runtime_error("base.vault: lease token too short or truncated");
    }

    const uint8_t* nonce = blob.data();
    const uint8_t* cipher = blob.data() + NONCE_LEN;
    size_t cipher_len = blob.size() - NONCE_LEN;

    auto transit_key = get_or_create_transit_key();
    std::vector<uint8_t> decrypted(cipher_len - TAG_LEN);
    unsigned long long decrypted_len = 0;

    int rc = crypto_aead_xchacha20poly1305_ietf_decrypt(
        decrypted.data(), &decrypted_len, nullptr,
        cipher, cipher_len,
        LEASE_AEAD_AD, sizeof(LEASE_AEAD_AD) - 1,
        nonce, transit_key->data());

    if (rc != 0) {
        throw std::runtime_error("base.vault: failed to decrypt lease token (invalid key, expired, or tampered token)");
    }

    if (decrypted_len < MIN_PAYLOAD) {
        sodium_memzero(decrypted.data(), decrypted_len);
        throw std::runtime_error("base.vault: decrypted lease payload is truncated");
    }

    const uint8_t* ptr = decrypted.data();
    if (ptr[0] != 'I' || ptr[1] != 'T' || ptr[2] != 'K' || ptr[3] != 'L') {
        sodium_memzero(decrypted.data(), decrypted_len);
        throw std::runtime_error("base.vault: invalid lease magic header");
    }
    if (ptr[4] != 0x01) {
        sodium_memzero(decrypted.data(), decrypted_len);
        throw std::runtime_error("base.vault: unsupported lease version: " + std::to_string(ptr[4]));
    }
    // uint8_t flags = ptr[5];
    ptr += 6;

    const uint8_t* payload_end = decrypted.data() + decrypted_len;
    auto need = [&](size_t nbytes) {
        if (ptr < decrypted.data() || static_cast<size_t>(payload_end - ptr) < nbytes) {
            sodium_memzero(decrypted.data(), decrypted_len);
            throw std::runtime_error("base.vault: corrupted lease payload length");
        }
    };

    need(2);
    uint16_t store_len = unpack_u16_be(ptr);
    ptr += 2;
    need(static_cast<size_t>(store_len) + 32 + 8 + 8 + 8 + 2);

    std::string store_name(reinterpret_cast<const char*>(ptr), store_len);
    ptr += store_len;

    if (!expected_store.empty() && store_name != expected_store) {
        sodium_memzero(decrypted.data(), decrypted_len);
        throw std::runtime_error("base.vault: store lease mismatch: expected '" +
                                 expected_store + "', got '" + store_name + "'");
    }

    StoreLeaseInfo info;
    info.store_name = store_name;
    info.store_dek = std::make_shared<base::secret::LockedSecret<32>>();
    std::memcpy(info.store_dek->data(), ptr, 32);
    ptr += 32;

    info.created_at = unpack_u64_be(ptr);
    ptr += 8;
    info.expires_at = unpack_u64_be(ptr);
    ptr += 8;
    info.bound_pid = unpack_i64_be(ptr);
    ptr += 8;

    need(2);
    uint16_t sup_len = unpack_u16_be(ptr);
    ptr += 2;
    need(static_cast<size_t>(sup_len) + 16);
    if (sup_len > 0) {
        info.supervisor_session = std::string(reinterpret_cast<const char*>(ptr), sup_len);
        ptr += sup_len;
    }

    sodium_memzero(decrypted.data(), decrypted_len);

    // Validate constraints
    uint64_t now = static_cast<uint64_t>(std::time(nullptr));
    if (enforce_validity) {
        if (info.expires_at > 0 && now >= info.expires_at) {
            throw std::runtime_error("base.vault: store lease for '" + store_name +
                                     "' has expired (expired at " + std::to_string(info.expires_at) +
                                     ", current time " + std::to_string(now) + ")");
        }

        if (info.bound_pid > 0) {
            int64_t current_pid = static_cast<int64_t>(GETPID());
            if (info.bound_pid != current_pid) {
                throw std::runtime_error("base.vault: store lease is bound to PID " +
                                         std::to_string(info.bound_pid) +
                                         ", but current PID is " +
                                         std::to_string(current_pid));
            }
        }
    }

    return info;
}

pybind11::dict verify_store_lease(
    const std::string& lease_token,
    const std::string& expected_store) {
    StoreLeaseInfo info = unseal_store_lease(lease_token, expected_store, false);
    uint64_t now = static_cast<uint64_t>(std::time(nullptr));
    int64_t current_pid = static_cast<int64_t>(GETPID());

    bool is_exp = (info.expires_at > 0 && now >= info.expires_at);
    bool pid_ok = (info.bound_pid == 0 || info.bound_pid == current_pid);

    py::dict d;
    d["store_name"] = info.store_name;
    d["created_at"] = info.created_at;
    d["expires_at"] = info.expires_at;
    d["bound_pid"] = info.bound_pid;
    d["supervisor_session"] = info.supervisor_session;
    d["is_expired"] = is_exp;
    d["pid_matches"] = pid_ok;
    d["valid"] = (!is_exp && pid_ok);
    return d;
}

} // namespace base::vault

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_vault(py::module_& m) {
    using namespace base::vault;

    m.doc() =
        "Vault in the C++ core (Issue #879, W0-15): "
        "unlock, session handles, and sealed per-store leases for daemons.";

    m.def("unlock", &unlock_keystore,
          py::arg("keystore_path"), py::arg("alias"), py::arg("password"),
          "Unlock vault via PKCS#12 keystore in C++ memory; returns session handle ('vses_<hex>').");

    m.def("unlock_direct", &unlock_direct,
          py::arg("password"), py::arg("salt"),
          "Unlock vault via password + salt (Argon2id KDF); returns session handle ('vses_<hex>').");

    m.def("unlock_raw",
          [](py::bytes raw_key) {
              std::string s = raw_key;
              std::vector<uint8_t> key(s.begin(), s.end());
              if (!s.empty()) {
                  sodium_memzero(&s[0], s.size());
              }
              std::string handle = unlock_raw(key);
              if (!key.empty()) {
                  sodium_memzero(key.data(), key.size());
              }
              return handle;
          },
          py::arg("raw_key"),
          "Install an existing 32-byte keystore key as the session DEK. Does not re-hash it.");

    m.def("is_unlocked", &is_unlocked,
          py::arg("session_handle"),
          "Return True if the given session handle is currently unlocked and valid.");

    m.def("lock", &lock,
          py::arg("session_handle"),
          "Lock/close an active vault session. Securely wipes keys via sodium_memzero.");

    m.def("lock_all", &lock_all,
          "Lock/close all active vault sessions.");

    m.def("active_sessions", &active_sessions,
          "List currently active session handles.");

    m.def("create_store_lease", &create_store_lease,
          py::arg("session_handle"), py::arg("store_name"),
          py::arg("pid") = 0, py::arg("ttl_seconds") = 0,
          py::arg("supervisor_session") = "",
          "Create a sealed per-store lease token (e.g. for 'cloud_jobs' or 'library').");

    m.def("create_raw_store_lease",
          [](const std::string& store_name, py::bytes raw_key, int64_t pid, uint64_t ttl_seconds, const std::string& supervisor_session) {
              std::string s = raw_key;
              return create_raw_store_lease(store_name, std::vector<uint8_t>(s.begin(), s.end()), pid, ttl_seconds, supervisor_session);
          },
          py::arg("store_name"), py::arg("raw_key"),
          py::arg("pid") = 0, py::arg("ttl_seconds") = 0,
          py::arg("supervisor_session") = "",
          "Create a sealed lease token directly from a raw 32-byte key.");

    m.def("verify_store_lease", &verify_store_lease,
          py::arg("lease_token"), py::arg("expected_store") = "",
          "Verify and inspect a sealed lease token metadata without exposing the secret key.");

    m.def("set_transit_key",
          [](py::bytes key) {
              std::string s = key;
              set_transit_key(std::vector<uint8_t>(s.begin(), s.end()));
          },
          py::arg("key"),
          "Set an in-memory transit key override (must be 32 bytes).");

    m.def("clear_transit_key", &clear_transit_key,
          "Clear the in-memory transit key override.");

    m.def("get_transit_key_path", &get_transit_key_path,
          "Return the path to the lease transit key file.");
}
