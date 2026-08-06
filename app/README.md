# app/

**Scaffold — not yet implemented.** Native mobile UIs for Manga
Colorization & Animation.

```
app/
  ios/       Swift/SwiftUI app skeleton
  android/   Kotlin/Jetpack Compose app skeleton
```

Both are expected to talk to `../src/`'s solvers through a remote API
rather than running them on-device (the ML-heavy modes — optimal transport,
graph-cut — assume a desktop-class CPU/GPU). See each subdirectory's README
for status.
