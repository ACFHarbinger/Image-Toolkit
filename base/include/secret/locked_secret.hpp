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
// See moon/roadmaps/rust_to_cpp_migration.md §Phase 4
// ---------------------------------------------------------------------------

#include <sodium.h>

#include <array>
#include <cstring>
#include <stdexcept>
#include <sys/mman.h>  // mlock / munlock (POSIX)

namespace base::secret {

/// Fixed-size secret buffer with mlock + sodium_memzero on destruction.
/// Non-copyable; moveable.
template <std::size_t N>
class LockedSecret {
public:
    LockedSecret() {
        std::memset(data_.data(), 0, N);
        if (mlock(data_.data(), N) != 0) {
            // mlock may fail if RLIMIT_MEMLOCK is exhausted; log and continue.
            // The buffer is still zeroed on destruction via sodium_memzero.
        }
    }

    ~LockedSecret() {
        sodium_memzero(data_.data(), N);
        munlock(data_.data(), N);
    }

    // Non-copyable
    LockedSecret(const LockedSecret&)            = delete;
    LockedSecret& operator=(const LockedSecret&) = delete;

    // Moveable: transfer ownership (source is zeroed)
    LockedSecret(LockedSecret&& other) noexcept {
        std::memcpy(data_.data(), other.data_.data(), N);
        sodium_memzero(other.data_.data(), N);
        munlock(other.data_.data(), N);
        mlock(data_.data(), N);
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
