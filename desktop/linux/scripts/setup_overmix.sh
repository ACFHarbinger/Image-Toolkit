#!/usr/bin/env bash
# Builds OvermixCli from the vendor/Overmix submodule (roadmap §0.3, GitHub
# issue #18). Overmix is GPL-3.0 — built and run as an external tool, never
# linked into our own binaries.
#
# Two environment gaps beyond the apt/pkg-config deps CMakeLists.txt already
# checks:
#
# 1. WebGPU: src/gpu/*.hpp unconditionally include <webgpu/webgpu.h> and link
#    WEBGPU_LIBRARY with no build-time feature switch, even though the CLI
#    align/render/comparator paths we use never touch the GPU code. This
#    machine's system /usr/include/webgpu/webgpu.h is an unrelated dummy stub
#    (from a different project), so we fetch a real wgpu-native release
#    instead. The *current* wgpu-native (v29+) ships a newer WebGPU API
#    (WGPUStringView labels, renamed enums) that this Overmix revision's GPU
#    code doesn't compile against — v0.19.4.1 matches the API Overmix expects
#    (plain `const char*` labels, WGPUBufferMapAsyncStatus).
# 2. Eigen3: not installed system-wide, but already present at
#    $TOOLKIT_ROOT/include/eigen3 from the base module's pixi env — reused
#    directly instead of requiring a redundant system install.
#
# There is also a one-time source patch, committed directly in the
# submodule's own local git history (not pushed upstream, since we don't own
# that repo): src/video/VideoFrame.cpp used `AVFrame::key_frame` and
# `AVFrame::display_picture_number`, both removed from newer FFmpeg. See the
# comment left at that call site.
#
# Usage: desktop/linux/scripts/setup_overmix.sh
# Produces: vendor/Overmix/build/OvermixCli (+ build/_wgpu_native/lib/*.so,
# RPATH-linked so no LD_LIBRARY_PATH is needed to run it).

set -euo pipefail

TOOLKIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OVERMIX_DIR="$TOOLKIT_ROOT/vendor/Overmix"
BUILD_DIR="$OVERMIX_DIR/build"
WGPU_DIR="$BUILD_DIR/_wgpu_native"
WGPU_VERSION="v0.19.4.1"
WGPU_URL="https://github.com/gfx-rs/wgpu-native/releases/download/${WGPU_VERSION}/wgpu-linux-x86_64-release.zip"

if [ ! -f "$OVERMIX_DIR/CMakeLists.txt" ]; then
    echo "vendor/Overmix submodule not found/initialized. Run:" >&2
    echo "  git submodule update --init vendor/Overmix" >&2
    exit 1
fi

mkdir -p "$BUILD_DIR"

if [ ! -f "$WGPU_DIR/include/webgpu/webgpu.h" ]; then
    echo "[setup_overmix] Fetching wgpu-native $WGPU_VERSION (API-compatible with this Overmix revision)…"
    mkdir -p "$WGPU_DIR/include/webgpu" "$WGPU_DIR/lib"
    TMP_ZIP="$(mktemp --suffix=.zip)"
    curl -sL -o "$TMP_ZIP" "$WGPU_URL"
    TMP_EXTRACT="$(mktemp -d)"
    unzip -oq "$TMP_ZIP" -d "$TMP_EXTRACT"
    cp "$TMP_EXTRACT/webgpu.h" "$TMP_EXTRACT/wgpu.h" "$WGPU_DIR/include/webgpu/"
    cp "$TMP_EXTRACT/libwgpu_native.so" "$WGPU_DIR/lib/"
    rm -rf "$TMP_ZIP" "$TMP_EXTRACT"
else
    echo "[setup_overmix] wgpu-native already fetched, skipping download."
fi

EIGEN_INCLUDE="$TOOLKIT_ROOT/include"
if [ ! -f "$EIGEN_INCLUDE/eigen3/Eigen/Dense" ]; then
    echo "Eigen3 not found at $EIGEN_INCLUDE/eigen3 — expected from the base module's pixi env." >&2
    exit 1
fi

echo "[setup_overmix] Configuring CMake…"
cmake -S "$OVERMIX_DIR" -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DWEBGPU_INCLUDE_DIR="$WGPU_DIR/include" \
    -DWEBGPU_LIBRARY="$WGPU_DIR/lib/libwgpu_native.so" \
    -DCMAKE_CXX_FLAGS="-I$EIGEN_INCLUDE" \
    -DCMAKE_BUILD_RPATH="$WGPU_DIR/lib"

echo "[setup_overmix] Building OvermixCli…"
cmake --build "$BUILD_DIR" --target OvermixCli -j"$(nproc)"

echo "[setup_overmix] Done: $BUILD_DIR/OvermixCli"
"$BUILD_DIR/OvermixCli" --help | head -3
