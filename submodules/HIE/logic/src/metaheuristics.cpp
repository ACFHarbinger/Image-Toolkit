/// @file metaheuristics.cpp
/// @brief PSO and Differential Evolution solver implementations.

#include "metaheuristics.hpp"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <limits>
#include <numeric>
#include <random>

namespace hybrid_image_editor {

// ─── Shared RNG ───────────────────────────────────────────────────────────────

static std::mt19937& global_rng() {
    static std::mt19937 rng{std::random_device{}()};
    return rng;
}

static float uniform(float lo, float hi) {
    std::uniform_real_distribution<float> dist(lo, hi);
    return dist(global_rng());
}

static std::size_t random_int(std::size_t lo, std::size_t hi) {
    std::uniform_int_distribution<std::size_t> dist(lo, hi);
    return dist(global_rng());
}

// ─── PSO ─────────────────────────────────────────────────────────────────────

MetaheuristicResult pso_solve(
        const ObjectiveFn&              objective_fn,
        const std::vector<ParamBound>&  bounds,
        const PSOConfig&                config) {

    MetaheuristicResult result;
    result.converged = false;

    if (bounds.empty()) {
        result.best_fitness = 0.f;
        result.iterations_run = 0;
        result.error = "Empty bounds";
        return result;
    }

    const std::size_t D = bounds.size();
    const std::size_t S = config.n_particles;

    // Initialise particle positions and velocities
    std::vector<std::vector<float>> pos(S, std::vector<float>(D));
    std::vector<std::vector<float>> vel(S, std::vector<float>(D, 0.f));
    std::vector<std::vector<float>> pbest(S);
    std::vector<float>              pbest_fit(S, std::numeric_limits<float>::infinity());
    std::vector<float>              gbest(D);
    float                           gbest_fit = std::numeric_limits<float>::infinity();

    // Random initialisation within bounds
    for (std::size_t i = 0; i < S; ++i) {
        for (std::size_t d = 0; d < D; ++d) {
            pos[i][d] = uniform(bounds[d].lower, bounds[d].upper);
            float range = bounds[d].upper - bounds[d].lower;
            vel[i][d]  = uniform(-range * 0.1f, range * 0.1f);
        }
        float fit = objective_fn(pos[i]);
        pbest[i]     = pos[i];
        pbest_fit[i] = fit;
        if (fit < gbest_fit) {
            gbest_fit = fit;
            gbest     = pos[i];
        }
    }

    float prev_gbest = gbest_fit;
    std::uint32_t stall = 0;

    for (std::uint32_t iter = 0; iter < config.max_iter; ++iter) {
        for (std::size_t i = 0; i < S; ++i) {
            for (std::size_t d = 0; d < D; ++d) {
                float r1 = uniform(0.f, 1.f);
                float r2 = uniform(0.f, 1.f);

                vel[i][d] = config.inertia_w    * vel[i][d]
                          + config.cognitive_c1 * r1 * (pbest[i][d] - pos[i][d])
                          + config.social_c2    * r2 * (gbest[d]    - pos[i][d]);

                pos[i][d] += vel[i][d];

                // Clamp to bounds
                pos[i][d] = std::clamp(pos[i][d], bounds[d].lower, bounds[d].upper);
            }

            float fit = objective_fn(pos[i]);

            if (fit < pbest_fit[i]) {
                pbest_fit[i] = fit;
                pbest[i]     = pos[i];
            }
            if (fit < gbest_fit) {
                gbest_fit = fit;
                gbest     = pos[i];
            }
        }

        // Convergence / stall check
        if (std::abs(prev_gbest - gbest_fit) < config.tolerance) {
            if (++stall >= config.patience) {
                result.converged = true;
                result.iterations_run = iter + 1;
                break;
            }
        } else {
            stall = 0;
        }
        prev_gbest = gbest_fit;

        if (iter + 1 == config.max_iter) {
            result.iterations_run = config.max_iter;
        }
    }

    result.best_params  = gbest;
    result.best_fitness = gbest_fit;
    return result;
}

// ─── Differential Evolution ───────────────────────────────────────────────────

MetaheuristicResult de_solve(
        const ObjectiveFn&              objective_fn,
        const std::vector<ParamBound>&  bounds,
        const DEConfig&                 config) {

    MetaheuristicResult result;
    result.converged = false;

    if (bounds.empty()) {
        result.best_fitness = 0.f;
        result.iterations_run = 0;
        result.error = "Empty bounds";
        return result;
    }

    const std::size_t D   = bounds.size();
    const std::size_t NP  = std::max<std::size_t>(4, config.popsize * D);

    // Initialise population
    std::vector<std::vector<float>> pop(NP, std::vector<float>(D));
    std::vector<float>              fit_pop(NP);

    for (std::size_t i = 0; i < NP; ++i) {
        for (std::size_t d = 0; d < D; ++d) {
            pop[i][d] = uniform(bounds[d].lower, bounds[d].upper);
        }
        fit_pop[i] = objective_fn(pop[i]);
    }

    // Best individual
    std::size_t best_idx = static_cast<std::size_t>(
        std::min_element(fit_pop.begin(), fit_pop.end()) - fit_pop.begin());

    float prev_best = fit_pop[best_idx];
    std::uint32_t stall = 0;

    for (std::uint32_t gen = 0; gen < config.max_iter; ++gen) {
        for (std::size_t i = 0; i < NP; ++i) {
            // Select 3 distinct random indices ≠ i (DE/rand/1)
            std::size_t a, b, c;
            do { a = random_int(0, NP - 1); } while (a == i);
            do { b = random_int(0, NP - 1); } while (b == i || b == a);
            do { c = random_int(0, NP - 1); } while (c == i || c == a || c == b);

            // Mutation: mutant = pop[a] + F * (pop[b] - pop[c])
            std::vector<float> mutant(D);
            for (std::size_t d = 0; d < D; ++d) {
                mutant[d] = pop[a][d] + config.F * (pop[b][d] - pop[c][d]);
                mutant[d] = std::clamp(mutant[d], bounds[d].lower, bounds[d].upper);
            }

            // Binomial crossover
            std::size_t j_rand = random_int(0, D - 1);
            std::vector<float> trial(D);
            for (std::size_t d = 0; d < D; ++d) {
                trial[d] = (uniform(0.f, 1.f) < config.CR || d == j_rand)
                           ? mutant[d] : pop[i][d];
            }

            // Selection
            float trial_fit = objective_fn(trial);
            if (trial_fit <= fit_pop[i]) {
                pop[i]     = trial;
                fit_pop[i] = trial_fit;
                if (trial_fit < fit_pop[best_idx]) {
                    best_idx = i;
                }
            }
        }

        // Convergence check
        float cur_best = fit_pop[best_idx];
        if (std::abs(prev_best - cur_best) < config.tolerance) {
            if (++stall >= config.patience) {
                result.converged = true;
                result.iterations_run = gen + 1;
                break;
            }
        } else {
            stall = 0;
        }
        prev_best = cur_best;

        if (gen + 1 == config.max_iter) {
            result.iterations_run = config.max_iter;
        }
    }

    result.best_params  = pop[best_idx];
    result.best_fitness = fit_pop[best_idx];
    return result;
}

}  // namespace hybrid_image_editor
