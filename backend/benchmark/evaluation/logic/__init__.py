"""Pixel-data computation for the coherence evaluation dashboard.

Pure functions operating on numpy arrays / OpenCV images — histograms,
scatter plots, heatmaps, FFT, feature matching, optical flow, and
comparison maps (diff, SSIM, overlay, checkerboard). No Qt widget classes
live here; ``evaluation.ui`` calls into this package to get figures/arrays to
display.
"""
