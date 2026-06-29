// ---------------------------------------------------------------------------
// batch/src/vault/locked_secret.cpp
//
// LockedSecret implementation support and libsodium initialisation.
//
// The LockedSecret<N> class itself is header-only (locked_secret.hpp).
// This translation unit ensures sodium_init() is called exactly once.
//
// Phase 4 of the Rust → C++ migration.
// ---------------------------------------------------------------------------

#include "base/secret/locked_secret.hpp"

#include <stdexcept>

namespace base::secret {

namespace {

// Calls sodium_init() on first access.  libsodium is safe to initialise
// multiple times (returns 1 for "already initialised"), but it must be
// called at least once before any crypto function.
struct SodiumInitGuard {
    SodiumInitGuard() {
        if (sodium_init() < 0)
            throw std::runtime_error("base::secret: libsodium initialisation failed");
    }
};

const SodiumInitGuard kSodiumInit;

} // anonymous namespace

} // namespace base::secret
