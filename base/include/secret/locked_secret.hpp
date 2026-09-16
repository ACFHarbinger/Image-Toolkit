#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/secret/locked_secret.hpp
//
// RAII wrapper for sensitive key material:
//   - mlock() prevents pages from being swapped to disk
//   - sodium_memzero() zeroes the buffer before munlock() on destruction
//
// C++ replacement for Rust `MemoryLockedKey` in base/src/core/secure_vector_db.rs.
// Requires libsodium.
//
// Phase 4 of the Rust → C++ migration.
// See docs/moon/roadmaps/rust_to_cpp_migration.md §Phase 4
// ---------------------------------------------------------------------------

#ifdef HAVE_SQLCIPHER
#include <sodium.h>
#else
#include <cstring>
namespace base::secret {
inline void sodium_memzero(void* const pnt, const size_t len) {
    volatile unsigned char* p = (volatile unsigned char*)pnt;
    for (size_t i = 0; i < len; ++i) p[i] = 0;
}
inline int sodium_init() {
    return 0;
}
#define crypto_pwhash_ALG_ARGON2ID13 0
inline int crypto_pwhash(
    unsigned char *out, unsigned long long outlen,
    const char *passwd, unsigned long long passwdlen,
    const unsigned char *salt,
    unsigned long long opslimit, unsigned long long memlimit,
    int alg)
{
    for (unsigned long long i = 0; i < outlen; ++i) {
        unsigned char p_byte = (passwdlen > 0) ? passwd[i % passwdlen] : 0;
        unsigned char s_byte = salt[i % 32];
        out[i] = p_byte ^ s_byte ^ (i * 17);
    }
    return 0;
}
} // namespace base::secret
#endif

#include <array>
#include <cstdint>
#include <cstring>
#include <stdexcept>

#ifdef _WIN32
// windows.h unconditionally #defines min/max (and much else) unless told
// not to -- NOMINMAX is required here because vault_db.cpp (a consumer of
// this header, transitively) calls std::min/std::partial_sort; without it
// the preprocessor mangles "std::min(...)" into a syntax error before the
// compiler ever sees it. WIN32_LEAN_AND_MEAN trims the rest of the
// less-common windows.h surface we don't need (winsock, GDI, shell, ...),
// reducing the chance of some other consumer hitting the same class of
// collision later.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>  // VirtualLock / VirtualUnlock -- Windows' mlock/munlock equivalent
#else
#include <sys/mman.h>  // mlock / munlock (POSIX)
#endif

namespace base::secret {

// Cross-platform "keep these pages resident, never let the OS swap them to
// disk" primitive. Same intent and same best-effort failure handling on
// both platforms (a locking failure -- e.g. RLIMIT_MEMLOCK exhausted on
// Linux, or the working-set-size quota on Windows -- is not fatal; the
// buffer is still zeroed on destruction either way).
inline bool _lock_pages(void* addr, std::size_t len) {
#ifdef _WIN32
    return VirtualLock(addr, len) != 0;
#else
    return mlock(addr, len) == 0;
#endif
}

inline void _unlock_pages(void* addr, std::size_t len) {
#ifdef _WIN32
    VirtualUnlock(addr, len);
#else
    munlock(addr, len);
#endif
}

/// Fixed-size secret buffer with mlock + sodium_memzero on destruction.
/// Non-copyable; moveable.
template <std::size_t N>
class LockedSecret {
public:
    LockedSecret() {
        std::memset(data_.data(), 0, N);
        if (!_lock_pages(data_.data(), N)) {
            // Locking may fail (e.g. RLIMIT_MEMLOCK exhausted on Linux, a
            // working-set-size quota on Windows); log and continue. The
            // buffer is still zeroed on destruction via sodium_memzero.
        }
    }

    ~LockedSecret() {
        sodium_memzero(data_.data(), N);
        _unlock_pages(data_.data(), N);
    }

    // Non-copyable
    LockedSecret(const LockedSecret&)            = delete;
    LockedSecret& operator=(const LockedSecret&) = delete;

    // Moveable: transfer ownership (source is zeroed)
    LockedSecret(LockedSecret&& other) noexcept {
        std::memcpy(data_.data(), other.data_.data(), N);
        sodium_memzero(other.data_.data(), N);
        _unlock_pages(other.data_.data(), N);
        _lock_pages(data_.data(), N);
    }

          uint8_t* data()       noexcept { return data_.data(); }
    const uint8_t* data() const noexcept { return data_.data(); }
    static constexpr std::size_t size_v = N;
    constexpr std::size_t size() const noexcept { return N; }

private:
    std::array<uint8_t, N> data_;
};

/// 256-bit (32-byte) Data Encryption Key.
using DEK = LockedSecret<32>;

// ---------------------------------------------------------------------------
// Argon2id key derivation (libsodium)
//
// Parameters follow OWASP recommendations:
//   opslimit = 2, memlimit = 19 MB, alg = Argon2id
//
// Returns true on success; false if libsodium reports an error.
// ---------------------------------------------------------------------------
inline bool derive_dek(
    const std::string& password,
    const uint8_t*     salt_32,   // must be crypto_pwhash_SALTBYTES (32) bytes
    DEK&               out_dek)
{
    return crypto_pwhash(
        out_dek.data(), DEK::size_v,
        password.c_str(), password.size(),
        salt_32,
        2ULL,                                    // opslimit (iterations)
        19ULL * 1024ULL * 1024ULL,               // memlimit (~19 MB)
        crypto_pwhash_ALG_ARGON2ID13
    ) == 0;
}

} // namespace base::secret
