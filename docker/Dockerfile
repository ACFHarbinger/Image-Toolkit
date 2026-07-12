# Image-Toolkit backend image.
#
# Builds the pybind11 C++ base extension (base/) and the Python backend
# (Django + Celery), then runs the headless web server. The PySide6 desktop GUI
# and the Tauri frontend are NOT containerized here (they are desktop apps).
#
# Build context is the repository ROOT (see docker/docker-compose.yml:
#   build: { context: .., dockerfile: docker/Dockerfile }).

# ---------------------------------------------------------------------------
# Stage 1 — builder: system toolchain + Python deps + C++ base extension
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

# Native build toolchain + the libraries base/CMakeLists.txt links against
# (OpenCV, Eigen, OpenSSL, FFTW, libsodium, SQLCipher) and libpq for psycopg.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build pkg-config git curl \
    libopencv-dev libeigen3-dev pybind11-dev \
    libssl-dev libfftw3-dev libsodium-dev libsqlcipher-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# uv for fast, reproducible dependency installation.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Dependency layer first (better caching): lockfile + manifest only.
COPY pyproject.toml uv.lock ./
RUN uv venv /opt/venv \
    && VIRTUAL_ENV=/opt/venv uv pip install -r pyproject.toml \
    && VIRTUAL_ENV=/opt/venv uv pip install gunicorn

# Now the source (everything not excluded by .dockerignore).
COPY . .

# Build the pybind11 C++ base extension (mirrors `pixi run build-base`).
RUN cmake -B build/base base/ -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INCLUDE_PATH="/usr/include/sqlcipher:/usr/include" \
    && cmake --build build/base --parallel \
    # The pybind11 module is emitted next to the package; collect it explicitly.
    && find . build/base -maxdepth 3 -name 'base*.so' -exec cp {} /app/ \; || true

# ---------------------------------------------------------------------------
# Stage 2 — runtime: slim image with the venv, the built extension, and source
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/opt/venv/bin:${PATH}" \
    VIRTUAL_ENV=/opt/venv \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Runtime shared libraries the base extension + psycopg link against.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libpq5 libssl3 libfftw3-single3 libsodium23 libsqlcipher0 \
    libopencv-core406 || \
    apt-get install -y --no-install-recommends \
    libgomp1 libpq5 libssl3 libfftw3-single3 libsodium23 libsqlcipher0 ; \
    rm -rf /var/lib/apt/lists/*

# Non-root runtime user.
RUN useradd --create-home --uid 10001 toolkit
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

RUN chown -R toolkit:toolkit /app
USER toolkit

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
# Default: the Django/Gunicorn web server. The Celery worker overrides this in
# docker-compose.yml.
CMD ["gunicorn", "api.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
