#!/bin/bash
# build_base.sh — build the C++ base pybind11 extension
#
# Phase 7 (Rust→C++ migration): the Rust maturin build has been replaced
# by a cmake build. The Rust source is archived at archive/base_rust/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cmake -B "${REPO_ROOT}/build/base" "${REPO_ROOT}/base/" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="${REPO_ROOT}/opencv/install" \
    -DCMAKE_INSTALL_PREFIX="${REPO_ROOT}"

# macOS uses sysctl instead of nproc to get the core count
CORES=$(sysctl -n hw.logicalcpu)

cmake --build "${REPO_ROOT}/build/base" -j"${CORES}"
cmake --install "${REPO_ROOT}/build/base"