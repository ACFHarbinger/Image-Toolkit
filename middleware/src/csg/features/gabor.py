"""Screentone texture features via a Gabor filter bank (roadmap §1.3, issue
#185).

Manga screentones (dense arrays of pure black/white dots, cross-hatching)
consist entirely of extreme binary pixels, which artificially maximizes
local intensity variance and breaks the intensity-continuity assumption the
plain Levin scribble colorizer (``colorization.py``) relies on -- see
``research/Manga Colorization and Animation Research.md`` §5.2. Projecting
the image into a Gabor texture-feature space (local spatial
frequency/orientation response) gives a signature that represents the
*structural rhythm* of a screentone rather than its raw pixel intensity, so
two pixels inside the same halftone pattern score as similar even though
their raw intensities may be polar opposites (a dot vs. the gap beside it).
"""

from __future__ import annotations

import cv2
import numpy as np

__all__ = ["gabor_feature_bank"]


def gabor_feature_bank(
    gray: np.ndarray,
    orientations: int = 4,
    frequencies: tuple[float, ...] = (0.15, 0.3),
    ksize: int = 15,
    sigma: float = 4.0,
) -> np.ndarray:
    """Per-pixel Gabor texture signature.

    Args:
        gray: HxW uint8 (or float) grayscale image.
        orientations: number of evenly-spaced angles in [0, pi) to filter at.
        frequencies: spatial wavelengths (in pixels^-1) to filter at; cel_shaded_generator
            screentone dot pitches are typically small (a few pixels), so
            the defaults favor higher spatial frequencies.
        ksize: Gabor kernel size (odd; larger catches lower-frequency
            patterns but costs more per-pixel convolution).
        sigma: Gaussian envelope standard deviation for the Gabor kernels.

    Returns:
        HxWxN float32 array, N = ``orientations * len(frequencies)`` -- one
        channel per (orientation, frequency) filter response magnitude,
        each independently normalized to zero mean / unit variance so no
        single filter's raw response scale dominates a later distance
        computation between two pixels' feature vectors.
    """
    if gray.ndim != 2:
        raise ValueError(f"gray must be a 2-D HxW array, got shape {gray.shape}")

    gray_f32 = gray.astype(np.float32)
    if gray_f32.max() > 1.0:
        gray_f32 = gray_f32 / 255.0

    thetas = np.linspace(0, np.pi, orientations, endpoint=False)
    responses = []
    for theta in thetas:
        for freq in frequencies:
            wavelength = 1.0 / freq
            kernel = cv2.getGaborKernel(
                (ksize, ksize), sigma, theta, wavelength, gamma=0.5, psi=0, ktype=cv2.CV_32F
            )
            response = cv2.filter2D(gray_f32, cv2.CV_32F, kernel)
            # Raw Gabor magnitude is phase-sensitive at the pixel level --
            # two adjacent pixels within the *same* halftone pattern can
            # still land on opposite phases of the underlying dot grid and
            # score very differently. Locally averaging the energy (a
            # standard "Gabor energy map" post-process in texture
            # segmentation) turns per-pixel phase noise into a genuine
            # regional texture signature, which is what a screentone-vs-
            # screentone (or screentone-vs-flat) *boundary* detector needs.
            energy = cv2.GaussianBlur(np.abs(response), (0, 0), sigmaX=sigma)
            responses.append(energy)

    features = np.stack(responses, axis=-1)

    # Per-channel standardization (zero mean, unit variance) so every
    # (orientation, frequency) filter contributes comparably to a later
    # Euclidean feature-space distance, regardless of that filter's own raw
    # response magnitude.
    # A perfectly flat input (or a degenerate tiny image) can produce an
    # all-zero response for some/all channels -- errstate suppresses the
    # transient "invalid value in divide"/"degrees of freedom <= 0" numpy
    # warnings that can fire before the std-floor below replaces the
    # resulting 0/0 with a defined value; the output is still always finite
    # (see test_uniform_image_has_near_zero_energy).
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = features.mean(axis=(0, 1), keepdims=True)
        std = features.std(axis=(0, 1), keepdims=True)
    std = np.where((std < 1e-8) | ~np.isfinite(std), 1.0, std)
    mean = np.where(np.isfinite(mean), mean, 0.0)
    result = (features - mean) / std
    return np.where(np.isfinite(result), result, 0.0)
