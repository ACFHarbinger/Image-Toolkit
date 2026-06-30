#pragma once
// ---------------------------------------------------------------------------
// base/include/utils/migration.hpp
// Legacy JSON → SQLCipher migration — Phase 10.
// Only compiled when HAVE_SQLCIPHER is defined.
// ---------------------------------------------------------------------------
#include <string>
#include <pybind11/pybind11.h>

namespace base::utils {

bool run_legacy_migration(
    const std::string& username,
    const std::string& password,
    const std::string& json_path,
    const std::string& db_path);

void register_migration(pybind11::module_& m);

} // namespace base::utils
