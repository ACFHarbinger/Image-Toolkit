#pragma once

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

/// @file metaheuristics.hpp
/// @brief Particle Swarm Optimization (PSO) and Differential Evolution (DE)
///        solvers for automated multi-parameter image filter stack tuning.

namespace hybrid_image_editor {

// ─── Shared Types ─────────────────────────────────────────────────────────────

/// A bounded parameter dimension: [lower, upper].
struct ParamBound {
    float lower;
    float upper;
};

/// Objective function signature: maps a parameter vector → scalar fitness.
/// Lower is better (minimization).
using ObjectiveFn = std::function<float(const std::vector<float>&)>;

/// Common result for all metaheuristic solvers.
struct MetaheuristicResult {
    std::vector<float> best_params;   ///< Optimal parameter vector found
    float              best_fitness;  ///< Best objective value achieved
    std::uint32_t      iterations_run;
    bool               converged;
    std::string        error;
};

// ─── PSO Configuration ────────────────────────────────────────────────────────

/// Hyper-parameters for Particle Swarm Optimization.
struct PSOConfig {
    std::uint32_t n_particles   = 30;    ///< Swarm size
    std::uint32_t max_iter      = 100;   ///< Maximum iterations
    float         inertia_w     = 0.72f; ///< Inertia weight ω
    float         cognitive_c1  = 1.49f; ///< Cognitive (personal best) coefficient c₁
    float         social_c2     = 1.49f; ///< Social (global best) coefficient c₂
    float         tolerance     = 1e-6f; ///< Convergence tolerance on fitness delta
    std::uint32_t patience      = 15;    ///< Iterations without improvement before early stop
};

/// @brief Particle Swarm Optimization.
///
/// Minimizes `objective_fn` over `bounds`-constrained parameter space.
/// Suitable for non-convex, multi-parameter image processing filter stacks
/// (curves, exposure, local contrast, sharpening, noise suppression).
///
/// @param objective_fn  Scalar fitness function to minimize (lower == better).
/// @param bounds        Parameter search bounds; determines dimensionality.
/// @param config        PSO hyper-parameters.
/// @return MetaheuristicResult  Best parameter vector found and diagnostics.
MetaheuristicResult pso_solve(
    const ObjectiveFn&           objective_fn,
    const std::vector<ParamBound>& bounds,
    const PSOConfig&             config = PSOConfig{});

// ─── DE Configuration ─────────────────────────────────────────────────────────

/// Hyper-parameters for Differential Evolution.
struct DEConfig {
    std::uint32_t popsize    = 15;    ///< Population size (× dimensionality)
    std::uint32_t max_iter   = 200;   ///< Maximum generations
    float         F          = 0.8f;  ///< Mutation scaling factor F ∈ [0, 2]
    float         CR         = 0.9f;  ///< Crossover probability CR ∈ [0, 1]
    std::string   strategy   = "rand/1/bin"; ///< DE strategy variant
    float         tolerance  = 1e-6f; ///< Convergence tolerance
    std::uint32_t patience   = 20;    ///< Stall tolerance (generations)
};

/// @brief Differential Evolution.
///
/// Solves non-convex spatial element placement and layout packing.
/// Maximizes aesthetic composition metrics (rule-of-thirds, visual weight
/// distribution) when the objective is negated.
///
/// @param objective_fn  Scalar fitness function to minimize.
/// @param bounds        Search bounds per parameter dimension.
/// @param config        DE hyper-parameters.
/// @return MetaheuristicResult  Best parameter vector found and diagnostics.
MetaheuristicResult de_solve(
    const ObjectiveFn&           objective_fn,
    const std::vector<ParamBound>& bounds,
    const DEConfig&              config = DEConfig{});

}  // namespace hybrid_image_editor
