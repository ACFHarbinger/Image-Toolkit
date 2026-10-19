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
// Vault DB operations / stubs (require pybind11 interpreter)
// ---------------------------------------------------------------------------

// These tests are gated behind BATCH_TESTS because pybind11::embed is only
// available when BATCH_TESTS=1 is defined (the test binary links pybind11::embed).

#ifdef BATCH_TESTS

namespace {
    // Ensure a Python interpreter exists for tests that use pybind11 objects.
    struct PythonGuard {
        py::scoped_interpreter guard{};
    };
}

#ifndef HAVE_SQLCIPHER

TEST_CASE("insert_listing_secure: skeleton raises type_error", "[vault][stub]") {
    PythonGuard pg;
    py::array_t<float> dummy({4});
    CHECK_THROWS_AS(
        base::secret::insert_listing_secure("db", "pw", "salt", "id", "cat", "title", "{}", "date", dummy),
        py::type_error);
}

TEST_CASE("hybrid_search_secure: skeleton raises type_error", "[vault][stub]") {
    PythonGuard pg;
    py::array_t<float> dummy({4});
    CHECK_THROWS_AS(
        base::secret::hybrid_search_secure("db", "pw", "salt", dummy, "", 5),
        py::type_error);
}

TEST_CASE("fetch_all_listings_secure: skeleton raises type_error", "[vault][stub]") {
    PythonGuard pg;
    CHECK_THROWS_AS(
        base::secret::fetch_all_listings_secure("db", "pw", "salt"),
        py::type_error);
}

TEST_CASE("delete_listing_secure: skeleton raises type_error", "[vault][stub]") {
    PythonGuard pg;
    CHECK_THROWS_AS(
        base::secret::delete_listing_secure("db", "pw", "salt", "id"),
        py::type_error);
}

TEST_CASE("fetch_listings_as_arrow_pointers: skeleton raises type_error", "[vault][stub]") {
    PythonGuard pg;
    CHECK_THROWS_AS(
        base::secret::fetch_listings_as_arrow_pointers("db", "pw", "salt"),
        py::type_error);
}

#else // HAVE_SQLCIPHER

#include <filesystem>

struct TempDbFixture {
    const std::string db_path = "test_vault_catch2.db";
    TempDbFixture() {
        std::filesystem::remove(db_path);
    }
    ~TempDbFixture() {
        std::filesystem::remove(db_path);
    }
};

TEST_CASE_METHOD(TempDbFixture, "Vault DB full operations validation", "[vault][database]") {
    PythonGuard pg;
    py::array_t<float> dummy({4});
    {
        auto r = dummy.mutable_unchecked<1>();
        for (py::ssize_t i = 0; i < 4; ++i) r(i) = 0.25f;
    }

    // 1. insert_listing_secure
    REQUIRE_NOTHROW(base::secret::insert_listing_secure(db_path, "password", "salt_salt_salt", "id123", "cat", "title123", "{\"foo\":\"bar\"}", "2026-07-03", dummy));

    // 2. fetch_all_listings_secure
    auto listings = base::secret::fetch_all_listings_secure(db_path, "password", "salt_salt_salt");
    REQUIRE(py::len(listings) == 1);
    auto item = listings[0].cast<py::tuple>();
    CHECK(item[0].cast<std::string>() == "id123");
    CHECK(item[1].cast<std::string>() == "cat");
    CHECK(item[2].cast<std::string>() == "title123");
    CHECK(item[3].cast<std::string>() == "{\"foo\":\"bar\"}");
    CHECK(item[4].cast<std::string>() == "2026-07-03");

    // 3. hybrid_search_secure
    auto search_res = base::secret::hybrid_search_secure(db_path, "password", "salt_salt_salt", dummy, "title", 5);
    REQUIRE(py::len(search_res) == 1);
    auto search_item = search_res[0].cast<py::tuple>();
    CHECK(search_item[0].cast<std::string>() == "id123");

    // 4. fetch_listings_as_arrow_pointers
    auto arrow_res = base::secret::fetch_listings_as_arrow_pointers(db_path, "password", "salt_salt_salt");
    REQUIRE(py::len(arrow_res) == 2);
    // Release the pointers since Arrow format expects caller to release them
    struct ArrowArray {
        int64_t  length;
        int64_t  null_count;
        int64_t  offset;
        int64_t  n_buffers;
        int64_t  n_children;
        const void** buffers;
        ArrowArray** children;
        ArrowArray*  dictionary;
        void (*release)(ArrowArray*);
        void*         private_data;
    };
    struct ArrowSchema {
        const char* format;
        const char* name;
        const char* metadata;
        int64_t     flags;
        int64_t     n_children;
        ArrowSchema** children;
        ArrowSchema*  dictionary;
        void (*release)(ArrowSchema*);
        void*         private_data;
    };
    auto arr_ptr = reinterpret_cast<ArrowArray*>(arrow_res[0].cast<uintptr_t>());
    auto sch_ptr = reinterpret_cast<ArrowSchema*>(arrow_res[1].cast<uintptr_t>());
    if (arr_ptr && arr_ptr->release) arr_ptr->release(arr_ptr);
    if (sch_ptr && sch_ptr->release) sch_ptr->release(sch_ptr);

    // 5. delete_listing_secure
    REQUIRE_NOTHROW(base::secret::delete_listing_secure(db_path, "password", "salt_salt_salt", "id123"));
    auto listings_post = base::secret::fetch_all_listings_secure(db_path, "password", "salt_salt_salt");
    CHECK(listings_post.empty());
}

#endif // HAVE_SQLCIPHER

#endif // BATCH_TESTS
