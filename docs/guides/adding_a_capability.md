# Adding a capability

The Convert pilot (#894) is the worked example.

1. Add `contracts/schemas/capability/<name>.json` and `[[method]]` rows in `contracts/methods.toml`. Regenerate with `python contracts/generate.py`.
2. Implement the service under `middleware/src/services/<name>/`. Convert already lives in `middleware/src/services/convert/`.
3. Register the methods on `SidecarServer._dispatch`. Convert uses `middleware/src/sidecar/handlers/convert.py`.
4. Add a typed method on `HostClient` and a view that receives the shell's client. The shell owns one `RustTransport` (`bridge_request`) for the window lifetime and passes that client into `CatalogView`. `bridge_request` starts `scripts/stage_sidecar_runtime.py`'s packaged runtime (or `IMAGE_TOOLKIT_RUNTIME`); it does not embed the checkout path. A single conversion sends `output_format` from the output suffix. `convert.convert_batch` returns a job id and checks cancel between files.
5. Point the `migration/features.toml` row at the service, contract, docs, and Tauri view.
6. Delete the retired Rust command once the bridge path is the one the view calls. `convert_image_batch` is that stub.
