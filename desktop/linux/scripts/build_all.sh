#!/usr/bin/env bash
# Build C++ module on Linux.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build
