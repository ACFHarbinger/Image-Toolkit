// ---------------------------------------------------------------------------
// logic/src/metaheuristics_bindings.cpp
//
// pybind11 bindings for metaheuristics.hpp, compiled into Image-Toolkit's
// central `base` extension (base.hie.metaheuristics) per the product
// decision in .agent/cache/chat/hie_product_decisions_20260812.md
// ("follow ASP").
//
// `objective_fn` accepts a plain Python callable — pybind11/functional.h
// converts it to hybrid_image_editor::ObjectiveFn automatically, reacquiring
// the GIL for each invocation. No outer py::gil_scoped_release here (unlike
// exact_solvers_bindings.cpp): the solver loop calls back into Python on
// every iteration, so releasing the GIL around the whole call wouldn't avoid
// GIL traffic, just relocate it.
//
// Consumed from Python via
// middleware/src/hie_middleware/jobs/metaheuristics.py, which falls back to
// a pure-Python reference implementation when `base` isn't importable.
// ---------------------------------------------------------------------------

#include <pybind11/functional.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "metaheuristics.hpp"

namespace py = pybind11;
using namespace hybrid_image_editor;

void register_hie_metaheuristics(py::module_& m) {
    py::class_<ParamBound>(m, "ParamBound")
        .def(py::init([](float lower, float upper) { return ParamBound{lower, upper}; }), py::arg("lower"),
             py::arg("upper"))
        .def_readwrite("lower", &ParamBound::lower)
        .def_readwrite("upper", &ParamBound::upper);

    py::class_<MetaheuristicResult>(m, "MetaheuristicResult")
        .def_readonly("best_params", &MetaheuristicResult::best_params)
        .def_readonly("best_fitness", &MetaheuristicResult::best_fitness)
        .def_readonly("iterations_run", &MetaheuristicResult::iterations_run)
        .def_readonly("converged", &MetaheuristicResult::converged)
        .def_readonly("error", &MetaheuristicResult::error);

    py::class_<PSOConfig>(m, "PSOConfig")
        .def(py::init<>())
        .def_readwrite("n_particles", &PSOConfig::n_particles)
        .def_readwrite("max_iter", &PSOConfig::max_iter)
        .def_readwrite("inertia_w", &PSOConfig::inertia_w)
        .def_readwrite("cognitive_c1", &PSOConfig::cognitive_c1)
        .def_readwrite("social_c2", &PSOConfig::social_c2)
        .def_readwrite("tolerance", &PSOConfig::tolerance)
        .def_readwrite("patience", &PSOConfig::patience);

    m.def(
        "pso_solve",
        [](const ObjectiveFn& objective_fn, const std::vector<ParamBound>& bounds, const PSOConfig& config) {
            return pso_solve(objective_fn, bounds, config);
        },
        py::arg("objective_fn"), py::arg("bounds"), py::arg("config") = PSOConfig{},
        "Particle Swarm Optimization (see metaheuristics.hpp).");

    py::class_<DEConfig>(m, "DEConfig")
        .def(py::init<>())
        .def_readwrite("popsize", &DEConfig::popsize)
        .def_readwrite("max_iter", &DEConfig::max_iter)
        .def_readwrite("F", &DEConfig::F)
        .def_readwrite("CR", &DEConfig::CR)
        .def_readwrite("strategy", &DEConfig::strategy)
        .def_readwrite("tolerance", &DEConfig::tolerance)
        .def_readwrite("patience", &DEConfig::patience);

    m.def(
        "de_solve",
        [](const ObjectiveFn& objective_fn, const std::vector<ParamBound>& bounds, const DEConfig& config) {
            return de_solve(objective_fn, bounds, config);
        },
        py::arg("objective_fn"), py::arg("bounds"), py::arg("config") = DEConfig{},
        "Differential Evolution (see metaheuristics.hpp).");
}
