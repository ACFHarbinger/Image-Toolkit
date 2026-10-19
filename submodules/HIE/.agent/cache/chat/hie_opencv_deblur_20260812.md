# HIE OpenCV Deblur Baseline — Chat

Date: 2026-08-12

Added `opencv_deblur_runner`, a bounded Gaussian high-frequency restoration
baseline behind the existing cancellable job contract. The CLI now supports
explicit `deblur --backend pillow|opencv`; Pillow remains the default and
OpenCV requires the root `restoration-opencv` UV environment. This baseline is
not a trained blind-deconvolution model; neural deblurring remains an optional
future backend.
