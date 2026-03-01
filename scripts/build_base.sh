source .venv/bin/activate
cd base
maturin develop --release --features python
cargo build --release --bin slideshow_daemon