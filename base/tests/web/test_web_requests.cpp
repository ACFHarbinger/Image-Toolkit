// ---------------------------------------------------------------------------
// batch/tests/http/test_web_requests.cpp
//
// Catch2 tests for base::web — run_web_requests_sequence.
// Phase 5 skeleton — verifies stub exception contract.
// ---------------------------------------------------------------------------

#include <catch2/catch_test_macros.hpp>

#include "web/web_requests.hpp"

#include <stdexcept>

TEST_CASE("run_web_requests_sequence: skeleton raises runtime_error", "[http][stub]") {
    auto no_op_cb = [](const std::string&) {};
    CHECK_THROWS_AS(
        base::web::run_web_requests_sequence("{}", no_op_cb),
        std::runtime_error);
}

TEST_CASE("run_web_requests_sequence: error message mentions Phase 5", "[http][stub]") {
    auto no_op_cb = [](const std::string&) {};
    try {
        base::web::run_web_requests_sequence("{}", no_op_cb);
        FAIL("expected exception not thrown");
    } catch (const std::runtime_error& e) {
        std::string msg = e.what();
        CHECK(msg.find("Phase 5") != std::string::npos);
    }
}

TEST_CASE("run_web_requests_sequence: callback is not called for stub", "[http][stub]") {
    bool called = false;
    auto cb = [&](const std::string&) { called = true; };
    try {
        base::web::run_web_requests_sequence("{}", cb);
    } catch (const std::runtime_error&) {}
    CHECK_FALSE(called);
}

TEST_CASE("run_web_requests_sequence: empty config raises immediately", "[http][stub]") {
    auto no_op_cb = [](const std::string&) {};
    CHECK_THROWS(base::web::run_web_requests_sequence("", no_op_cb));
}

TEST_CASE("run_web_requests_sequence: malformed JSON raises immediately", "[http][stub]") {
    auto no_op_cb = [](const std::string&) {};
    CHECK_THROWS(base::web::run_web_requests_sequence("{bad json}", no_op_cb));
}
