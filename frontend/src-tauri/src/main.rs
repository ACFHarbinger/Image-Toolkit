// Placeholder Tauri entry point — see ../../README.md. Not yet wired to
// the ../src/ solvers.

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running Cel-Shaded-Generator frontend");
}
