# Android Kotlin API (Dokka GFM)

The Android module (`app/android/`) is documented via
[Dokka](https://kotlinlang.org/docs/dokka-introduction.html) in
GitHub-Flavoured Markdown format.

## Generating the docs locally

```bash
cd app/android
./gradlew dokkaGfm
# Output → app/android/build/dokka/gfm/
open app/android/build/dokka/gfm/index.md
```

## CI artifact

In GitHub Actions, the `docs-kotlin` job runs `./gradlew dokkaGfm` and
uploads the output as the **`kotlin-api-docs`** artifact (7-day retention).
Download it from the Actions run to browse the full reference.

## Module overview

| Package | Purpose |
|---------|---------|
| `com.personal.image_toolkit` | Application entry point (`AppActivity`) |
| `com.personal.image_toolkit.classes` | Abstract base fragments (`BaseSingleGalleryFragment`, `BaseTwoGalleriesFragment`, `BaseGenerativeFragment`) |
| `com.personal.image_toolkit.ui` | Feature screens — slideshow, settings, convert, wallpaper |
| `com.personal.image_toolkit.ui.windows` | Full-screen windows — login, image preview, log |

!!! note "Dokka configuration"
    The Dokka Gradle plugin (`org.jetbrains.dokka`) is declared in
    `app/android/build.gradle.kts`. Run `./gradlew dokkaHtml` for the richer
    interactive HTML reference; `./gradlew dokkaGfm` for the Markdown version
    that integrates with this portal.
