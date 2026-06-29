// ---------------------------------------------------------------------------
// batch/tests/vault/test_vault_db.cpp
//
// Catch2 tests for base::secret database operations.
// Phase 4 skeleton — tests verify stub exception contract until implementation.
// ---------------------------------------------------------------------------

#include <catch2/catch_test_macros.hpp>

#include "secret/vault_db.hpp"
#include "secret/locked_secret.hpp"

#include <pybind11/embed.h>
#include <pybind11/numpy.h>

namespace py = pybind11;

// ---------------------------------------------------------------------------
// LockedSecret (no Python required)
// ---------------------------------------------------------------------------

TEST_CASE("LockedSecret: zero-initialised on construction", "[vault][locked_secret]") {
    base::secret::LockedSecret<16> s;
    for (std::size_t i = 0; i < 16; ++i)
        CHECK(s.data()[i] == 0);
}

TEST_CASE("LockedSecret: size_v matches template parameter", "[vault][locked_secret]") {
    CHECK(base::secret::LockedSecret<32>::size_v == 32);
    CHECK(base::secret::LockedSecret<16>::size_v == 16);
}

TEST_CASE("LockedSecret: data can be written and read back", "[vault][locked_secret]") {
    base::secret::LockedSecret<8> s;
    for (std::size_t i = 0; i < 8; ++i) s.data()[i] = static_cast<uint8_t>(i * 3);
    for (std::size_t i = 0; i < 8; ++i)
        CHECK(s.data()[i] == static_cast<uint8_t>(i * 3));
}

// ---------------------------------------------------------------------------
// Vault DB stubs (require pybind11 interpreter for py::type_error)
// ---------------------------------------------------------------------------

// These tests are gated behind BATCH_TESTS because pybind11::embed is only
// available when BATCH_TESTS=1 is defined (the test binary links pybind11::embed).

#ifdef BATCH_TESTS

namespace {
    // Ensure a Python interpreter exists for tests that use py::type_error.
    struct PythonGuard {
        py::scoped_interpreter guard{};
    };
}

TEST_CASE("insert_listing_secure: skeleton raises type_error", "[vault][stub]") {
    PythonGuard pg;
    py::array_t<float> dummy({4});
    CHECK_THROWS_AS(
        base::secret::insert_listing_secure("db", "pw", "id", dummy, "{}"),
        py::type_error);
}

TEST_CASE("hybrid_search_secure: skeleton raises type_error", "[vault][stub]") {
    PythonGuard pg;
    py::array_t<float> dummy({4});
    CHECK_THROWS_AS(
        base::secret::hybrid_search_secure("db", "pw", dummy, "", 5),
        py::type_error);
}

TEST_CASE("fetch_all_listings_secure: skeleton raises type_error", "[vault][stub]") {
    PythonGuard pg;
    CHECK_THROWS_AS(
        base::secret::fetch_all_listings_secure("db", "pw"),
        py::type_error);
}

TEST_CASE("delete_listing_secure: skeleton raises type_error", "[vault][stub]") {
    PythonGuard pg;
    CHECK_THROWS_AS(
        base::secret::delete_listing_secure("db", "pw", "id"),
        py::type_error);
}

TEST_CASE("fetch_listings_as_arrow_pointers: skeleton raises type_error", "[vault][stub]") {
    PythonGuard pg;
    CHECK_THROWS_AS(
        base::secret::fetch_listings_as_arrow_pointers("db", "pw"),
        py::type_error);
}

#endif // BATCH_TESTS
