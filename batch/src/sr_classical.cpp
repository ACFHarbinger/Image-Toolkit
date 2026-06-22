// ---------------------------------------------------------------------------
// batch/src/sr_classical.cpp
//
// Classical super-resolution: DCT restoration, PSO sub-pixel registration,
// de-seam frequency suppression, Overmix-inspired L1 sparse SR.
//
// Replaces:
//   mfsr/dct_restoration.py   :: DCT-II deblocking
//   mfsr/de_seam.py           :: seam de-ringing
//   mfsr/pso_registration.py  :: PSO optimizer
//
// Optional FFTW3 acceleration guarded by HAVE_FFTW3.
//
// Implementation roadmap: Phase 5.
// See moon/roadmaps/asp_cpp_migration.md §batch::sr_classical
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// dct_restore
//
// DCT-II deblocking:
//   1. Tile-mode 2D DCT via cv::dft(DFT_ROWS) or FFTW FFTW_REDFT10
//   2. PatternRemove: subtract modular periodic mean from tile grid
//   3. Block deblocking: regularize 8×8 boundaries in DCT domain
//
// Args
// ----
// frame      : uint8 or float32 (H, W) or (H, W, C)
// block_size : int — DCT block size (default 8)
//
// Returns same dtype/shape as input.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> dct_restore(
    py::array_t<uint8_t> frame,
    int                  block_size = 8)
{
    // TODO (Phase 5): tile DCT, pattern removal, deblocking.
    // Use FFTW FFTW_REDFT10 if HAVE_FFTW3, else cv::dft.
    BATCH_NOT_IMPLEMENTED("sr_classical.dct_restore");
}

// ---------------------------------------------------------------------------
// pso_register
//
// Particle swarm optimizer for sub-pixel affine alignment:
//   - N_particles particles, each [dx, dy, angle, scale]
//   - Fitness: MAD of warped source vs reference (Overmix simpleAlpha style)
//   - T_max iterations, inertia w decays 0.9 → 0.4, cognitive c1=2.0, social c2=2.0
//   - OpenMP parallel particle fitness evaluation
//
// Args
// ----
// reference  : uint8 (H, W, C) — reference frame
// source     : uint8 (H, W, C) — frame to align
// n_particles : int — swarm size (default 30)
// t_max      : int — iteration limit (default 100)
//
// Returns dict {"tx","ty","angle","scale","fitness"}.
// ---------------------------------------------------------------------------
static py::dict pso_register(
    py::array_t<uint8_t> reference,
    py::array_t<uint8_t> source,
    int                  n_particles = 30,
    int                  t_max       = 100)
{
    // TODO (Phase 5): PSO with OpenMP parallel fitness eval.
    BATCH_NOT_IMPLEMENTED("sr_classical.pso_register");
}

// ---------------------------------------------------------------------------
// de_seam
//
// Frequency-domain seam ringing suppression:
//   1. 1D FFT along seam direction
//   2. Zero notch filter at seam frequency
//   3. IFFT
//
// Args
// ----
// frame     : uint8 (H, W, C) — frame containing seam artifact
// seam_axis : int — 0 = horizontal seam (FFT along rows), 1 = vertical
//
// Returns uint8 ndarray same shape.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> de_seam(
    py::array_t<uint8_t> frame,
    int                  seam_axis = 1)
{
    // TODO (Phase 5): 1D FFT + notch + IFFT.
    BATCH_NOT_IMPLEMENTED("sr_classical.de_seam");
}

// ---------------------------------------------------------------------------
// robust_sr
//
// Overmix-inspired L1 sparse super-resolution (RobustSrRender::compute port):
//   - Build Eigen sparse DHF matrix H[pixel_hr, pixel_lr]
//     = bilinear weights from LR pixel s to HR pixel at (i/scale, j/scale)
//   - L1 sub-gradient descent: x -= β · sign(H·x − y) · H^T, nr_iterations
//   - Applied to background regions only (where pixel-identical averaging valid)
//   - Handles JPEG block noise via L1 loss
//
// Args
// ----
// lr_frames  : list[ndarray uint8 (H, W, C)] — low-res input frames
// affines    : list[dict] — AffineParams dicts
// scale      : int — upscale factor (2 or 4)
// beta       : float — L1 sub-gradient step
// nr_iterations : int — descent iterations
//
// Returns uint8 ndarray (H*scale, W*scale, C).
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> robust_sr(
    py::list lr_frames,
    py::list affines,
    int      scale         = 2,
    float    beta          = 0.01f,
    int      nr_iterations = 50)
{
    // TODO (Phase 5): Eigen sparse DHF + L1 sub-gradient descent.
    // Reference: Overmix/src/renders/FloatRender.cpp RobustSrRender::compute().
    BATCH_NOT_IMPLEMENTED("sr_classical.robust_sr");
}

// ---------------------------------------------------------------------------
// register_sr_classical — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_sr_classical(py::module_& m) {
    m.doc() = R"doc(
        batch.sr_classical — Classical super-resolution (non-neural).

        Functions
        ---------
        dct_restore(frame, block_size) -> ndarray
        pso_register(reference, source, n_particles, t_max) -> dict
        de_seam(frame, seam_axis) -> ndarray
        robust_sr(lr_frames, affines, scale, beta, nr_iterations) -> ndarray
    )doc";

    m.def("dct_restore", &dct_restore,
        py::arg("frame"),
        py::arg("block_size") = 8,
        R"doc(
            DCT-II deblocking with pattern removal.

            Uses FFTW3 if compiled with HAVE_FFTW3, else cv::dft.

            Returns uint8 ndarray, same shape as input.
        )doc");

    m.def("pso_register", &pso_register,
        py::arg("reference"),
        py::arg("source"),
        py::arg("n_particles") = 30,
        py::arg("t_max")       = 100,
        R"doc(
            Particle swarm optimizer for sub-pixel affine alignment.

            N_particles (default 30) each encode [dx, dy, angle, scale].
            Fitness = MAD(warp(source, params), reference).
            OpenMP parallelizes particle fitness evaluation.

            Returns dict {"tx","ty","angle","scale","fitness"}.
        )doc");

    m.def("de_seam", &de_seam,
        py::arg("frame"),
        py::arg("seam_axis") = 1,
        R"doc(
            1D FFT notch filter to suppress seam ringing artifacts.

            seam_axis: 0 = horizontal seam, 1 = vertical seam.
            Returns uint8 ndarray, same shape as input.
        )doc");

    m.def("robust_sr", &robust_sr,
        py::arg("lr_frames"),
        py::arg("affines"),
        py::arg("scale")         = 2,
        py::arg("beta")          = 0.01f,
        py::arg("nr_iterations") = 50,
        R"doc(
            Overmix-inspired L1 sparse super-resolution (RobustSrRender port).

            Builds Eigen sparse DHF matrix; L1 sub-gradient descent.
            Applied to background-only regions. Handles JPEG block noise.

            Returns uint8 ndarray (H*scale, W*scale, C).
        )doc");
}
