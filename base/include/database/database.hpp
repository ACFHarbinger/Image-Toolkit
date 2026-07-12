#pragma once
// ---------------------------------------------------------------------------
// base/include/database/database.hpp
//
// Unified Library Database engine (Phase DB, DB.2).
//
// Session-keyed SQLCipher connection for ~/.image-toolkit/library.db:
//   - Argon2id KDF runs ONCE in the constructor (vs per-call in base.secret)
//   - generic parameterized query/execute primitives (the Python DAL in
//     backend/src/database/unified/ owns all SQL text)
//   - transactions, maintenance ops, statistics
//   - embeddings storage + brute-force cosine knn (HNSW arrives in DB.7)
//
// This module is intentionally separate from base.secret, which is
// Vault-only and must not be modified (owner decision, unified_database.md).
//
// When built without SQLCipher the class constructor raises so callers can
// detect a stub build (mirrors base.secret's stub strategy).
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

namespace py = pybind11;

void register_database(py::module_& m);
