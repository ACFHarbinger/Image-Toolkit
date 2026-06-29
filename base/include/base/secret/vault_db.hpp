#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/secret/vault_db.hpp
//
// Encrypted vector database operations:
//   - SQLCipher for page-level AES-256-GCM encryption
//   - sqlite-vec for cosine-similarity search
//   - Argon2id DEK derivation (see locked_secret.hpp)
//   - Apache Arrow C Data Interface for zero-copy bulk export
//
// C++ replacement for Rust secure_vector_db functions in base/src/core/.
//
// Phase 4 of the Rust → C++ migration.
// See moon/roadmaps/rust_to_cpp_migration.md §Phase 4
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include <string>
#include <vector>

namespace py = pybind11;

namespace base::secret {

// ---------------------------------------------------------------------------
// Core CRUD + search operations
// ---------------------------------------------------------------------------

/// Insert or update a listing in the encrypted database.
/// embedding must be a 1-D float32 numpy array.
void insert_listing_secure(
    const std::string&         db_path,
    const std::string&         password,
    const std::string&         listing_id,
    py::array_t<float>         embedding,
    const std::string&         metadata_json);

/// Hybrid cosine + BM25 search.
/// Returns a Python list of dicts: [{"id": str, "score": float, "metadata": str}, ...]
py::list hybrid_search_secure(
    const std::string&         db_path,
    const std::string&         password,
    py::array_t<float>         query_embedding,
    const std::string&         bm25_query,
    int                        top_k = 10);

/// Fetch all listings.
/// Returns a Python list of dicts: [{"id": str, "embedding": ndarray, "metadata": str}, ...]
py::list fetch_all_listings_secure(
    const std::string&         db_path,
    const std::string&         password);

/// Delete a listing by ID.  Returns true if the row was found and deleted.
bool delete_listing_secure(
    const std::string&         db_path,
    const std::string&         password,
    const std::string&         listing_id);

// ---------------------------------------------------------------------------
// Arrow C Data Interface export
//
// Returns (array_ptr: int, schema_ptr: int) as a Python tuple.
// Caller consumes with:
//   import pyarrow as pa
//   batch = pa.RecordBatch._import_from_c(array_ptr, schema_ptr)
// ---------------------------------------------------------------------------

py::tuple fetch_listings_as_arrow_pointers(
    const std::string&         db_path,
    const std::string&         password);

} // namespace base::secret
