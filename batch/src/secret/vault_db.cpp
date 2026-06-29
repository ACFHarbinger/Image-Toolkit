// ---------------------------------------------------------------------------
// batch/src/vault/vault_db.cpp
//
// Encrypted vector database operations (skeleton).
//
// Dependencies (Phase 4 implementation):
//   - SQLCipher: link -lsqlcipher (provides sqlite3_key + AES-256 encryption)
//   - sqlite-vec: loadable extension (sqlite3_load_extension)
//   - libsodium: Argon2id KDF, memzero (via locked_secret.hpp)
//   - Arrow C Data Interface: ArrowArray / ArrowSchema structs (nanoarrow)
//
// Phase 4 of the Rust → C++ migration.
// See moon/roadmaps/rust_to_cpp_migration.md §Phase 4
// ---------------------------------------------------------------------------

#include "batch/secret/vault_db.hpp"
#include "batch/secret/locked_secret.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <stdexcept>

namespace py = pybind11;

namespace batch::secret {

// ---------------------------------------------------------------------------
// All functions below are skeleton stubs.  Each raises NotImplementedError
// so the Python dispatch shim falls back to the Rust implementation.
// Replace with full implementations in Phase 4.
// ---------------------------------------------------------------------------

void insert_listing_secure(
    const std::string&  /*db_path*/,
    const std::string&  /*password*/,
    const std::string&  /*listing_id*/,
    py::array_t<float>  /*embedding*/,
    const std::string&  /*metadata_json*/)
{
    throw py::type_error(
        "batch.vault.insert_listing_secure: Phase 4 not yet implemented. "
        "Falling back to Rust base module.");
}

py::list hybrid_search_secure(
    const std::string& /*db_path*/,
    const std::string& /*password*/,
    py::array_t<float> /*query_embedding*/,
    const std::string& /*bm25_query*/,
    int                /*top_k*/)
{
    throw py::type_error(
        "batch.vault.hybrid_search_secure: Phase 4 not yet implemented. "
        "Falling back to Rust base module.");
}

py::list fetch_all_listings_secure(
    const std::string& /*db_path*/,
    const std::string& /*password*/)
{
    throw py::type_error(
        "batch.vault.fetch_all_listings_secure: Phase 4 not yet implemented. "
        "Falling back to Rust base module.");
}

bool delete_listing_secure(
    const std::string& /*db_path*/,
    const std::string& /*password*/,
    const std::string& /*listing_id*/)
{
    throw py::type_error(
        "batch.vault.delete_listing_secure: Phase 4 not yet implemented. "
        "Falling back to Rust base module.");
}

py::tuple fetch_listings_as_arrow_pointers(
    const std::string& /*db_path*/,
    const std::string& /*password*/)
{
    throw py::type_error(
        "batch.vault.fetch_listings_as_arrow_pointers: Phase 4 not yet implemented. "
        "Falling back to Rust base module.");
}

} // namespace batch::secret

// ---------------------------------------------------------------------------
// pybind11 registration (called from bindings.cpp)
// ---------------------------------------------------------------------------

void register_secret(py::module_& m) {
    m.doc() =
        "Encrypted vector database (SQLCipher + sqlite-vec + Argon2id + Arrow). "
        "Phase 4 skeleton — all functions raise until implementation is complete.";

    m.def("insert_listing_secure",
          &batch::secret::insert_listing_secure,
          py::arg("db_path"),
          py::arg("password"),
          py::arg("listing_id"),
          py::arg("embedding"),
          py::arg("metadata_json") = "{}",
          "Insert or update a listing in the encrypted database.");

    m.def("hybrid_search_secure",
          &batch::secret::hybrid_search_secure,
          py::arg("db_path"),
          py::arg("password"),
          py::arg("query_embedding"),
          py::arg("bm25_query")    = "",
          py::arg("top_k")         = 10,
          "Hybrid cosine + BM25 search over encrypted listings.");

    m.def("fetch_all_listings_secure",
          &batch::secret::fetch_all_listings_secure,
          py::arg("db_path"),
          py::arg("password"),
          "Fetch all listings from the encrypted database.");

    m.def("delete_listing_secure",
          &batch::secret::delete_listing_secure,
          py::arg("db_path"),
          py::arg("password"),
          py::arg("listing_id"),
          "Delete a listing by ID.  Returns True if found and deleted.");

    m.def("fetch_listings_as_arrow_pointers",
          &batch::secret::fetch_listings_as_arrow_pointers,
          py::arg("db_path"),
          py::arg("password"),
          "Zero-copy bulk export via Apache Arrow C Data Interface. "
          "Returns (array_ptr: int, schema_ptr: int).");
}
