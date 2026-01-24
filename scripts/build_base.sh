cd base
source .venv/bin/activate
maturin develop --release
cargo build --release --bin slideshow_daemon