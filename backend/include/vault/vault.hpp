#pragma once
// ---------------------------------------------------------------------------
// backend/include/vault/vault.hpp
//
// Vault in the C++ core (Issue #879, Wave 0e W0-15):
//   - Unlock keystore / password + salt held in C++ memory
//   - Master DEK and derived store DEKs held in LockedSecret<32> (mlock + sodium_memzero)
//   - Session handles returned to webview / sidecar (e.g. "vses_<hex>")
//   - Sealed per-store leases for daemons (e.g. cloud_jobs, library)
//   - Tamper-proof, process-bound, TTL-expiring AEAD lease tokens
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "secret/locked_secret.hpp"

namespace base::vault {

struct StoreLeaseInfo {
    std::string store_name;
    std::shared_ptr<base::secret::LockedSecret<32>> store_dek;
    uint64_t created_at{0};
    uint64_t expires_at{0};
    int64_t bound_pid{0};
    std::string supervisor_session;
};

// ---------------------------------------------------------------------------
// Session lifecycle
// ---------------------------------------------------------------------------

/// Unlock vault directly via password + salt (Argon2id KDF runs in C++).
/// Returns an opaque session handle: "vses_<hex>".
std::string unlock_direct(const std::string& password, const std::string& salt);

/// Install an existing 32-byte key as the session DEK. Does not run Argon2id.
std::string unlock_raw(const std::vector<uint8_t>& key);

/// Unlock vault via PKCS#12 keystore file.
/// Key is extracted and held strictly in LockedSecret<32> in C++ memory.
/// Returns an opaque session handle: "vses_<hex>".
std::string unlock_keystore(const std::string& keystore_path,
                            const std::string& alias,
                            const std::string& password);

/// Query whether a session handle is currently unlocked and valid.
bool is_unlocked(const std::string& session_handle);

/// Lock / close an active session. Securely wipes key material via sodium_memzero.
bool lock(const std::string& session_handle);

/// Lock / close all active sessions in the registry.
void lock_all();

/// List active session handles.
std::vector<std::string> active_sessions();

// ---------------------------------------------------------------------------
// Store key derivation & sealed leases
// ---------------------------------------------------------------------------

/// Get session master DEK in C++. Throws std::runtime_error if session invalid.
std::shared_ptr<base::secret::LockedSecret<32>> get_session_master_dek(
    const std::string& session_handle);

/// Derive store-specific 32-byte DEK (e.g. for "library" or "cloud_jobs").
std::shared_ptr<base::secret::LockedSecret<32>> derive_store_dek(
    const std::string& session_handle,
    const std::string& store_name);

/// Create a sealed lease token for a store.
/// Token is AEAD-encrypted with the machine/supervisor transit key.
/// ttl_seconds: 0 for unbounded / session lifetime, > 0 for expiry TTL.
/// pid: 0 for unbound, > 0 to bind lease strictly to caller process PID.
std::string create_store_lease(
    const std::string& session_handle,
    const std::string& store_name,
    int64_t pid = 0,
    uint64_t ttl_seconds = 0,
    const std::string& supervisor_session = "");

/// Mint a sealed per-store lease with a per-daemon transit secret in native C++.
/// 1. Verifies session_handle exists in C++ memory.
/// 2. Derives store DEK (held in LockedSecret<32>).
/// 3. Generates a fresh random 32-byte per-daemon transit key K_daemon (held in LockedSecret<32>).
/// 4. Seals store DEK with K_daemon via AEAD XChaCha20-Poly1305, binding store_name, bound_pid,
///    ttl_seconds, and supervisor_session.
/// 5. Writes K_daemon into <data_dir>/supervisor/keys/<daemon_name>.key with 0600 permissions.
/// 6. Returns the sealed lease token ("itkl_v1_...").
std::string mint_daemon_lease(
    const std::string& session_handle,
    const std::string& store_name,
    const std::string& daemon_name,
    const std::string& data_dir,
    int64_t pid = 0,
    uint64_t ttl_seconds = 0,
    const std::string& supervisor_session = "");

/// Unseal and verify a store lease token inside C++.
/// Extracts store DEK into LockedSecret<32>, enforces TTL, PID, and supervisor session binding.
StoreLeaseInfo unseal_store_lease(
    const std::string& lease_token,
    const std::string& expected_store = "",
    const std::string& expected_supervisor_session = "",
    const std::string& daemon_key_path = "",
    bool enforce_validity = true);

/// Verify store lease token from Python / webview.
/// Returns metadata dictionary WITHOUT exposing the secret key.
pybind11::dict verify_store_lease(
    const std::string& lease_token,
    const std::string& expected_store = "",
    const std::string& expected_supervisor_session = "",
    const std::string& daemon_key_path = "");

// ---------------------------------------------------------------------------
// Transit key management
// ---------------------------------------------------------------------------

/// Generate a fresh random in-memory transit key override in LockedSecret<32>.
/// Never exposes raw key bytes to callers/Python. Useful for isolated tests.
void rotate_transit_key();

/// Load a daemon transit key from a secure 0600 file into in-memory LockedSecret<32>.
void load_daemon_key(const std::string& key_path);

/// Clear in-memory transit key override.
void clear_transit_key();

/// Resolve filesystem path of the lease transit key.
std::string get_transit_key_path();

} // namespace base::vault

void register_vault(pybind11::module_& m);
