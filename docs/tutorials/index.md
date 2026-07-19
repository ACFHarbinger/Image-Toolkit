# :material-compass: Tab Tutorials

Task-oriented tutorials for every tab in the Image-Toolkit GUI, organized by the categories in the main window's *Select Category* dropdown — plus cross-category workflows and the app-wide Login/Settings windows. Each tutorial explains what a tab is for, how to use it, what its parameters mean, and shows the actual UI — **179 screenshots** across seven pages, plus diagrams and reference tables.

```mermaid
flowchart LR
    subgraph Local["Local files"]
        direction TB
        ST[":material-tools: System Tools"]
        LD[":material-database: Library Database"]
    end
    subgraph Net["Network"]
        WI[":material-web: Web Integration"]
    end
    subgraph AI["Models"]
        DL[":material-brain: Deep Learning"]
        IS[":material-image-multiple: Image Stitching"]
    end

    ST -->|catalogue & tag| LD
    LD -->|search results feed| ST
    WI -->|downloaded images| ST
    LD -->|training data| DL
    ST -->|frames| IS

    style ST fill:#0f766e,stroke:#2dd4bf,color:#ecfeff
    style LD fill:#1d4ed8,stroke:#93c5fd,color:#eff6ff
    style WI fill:#1e3a8a,stroke:#60a5fa,color:#eff6ff
    style DL fill:#7c3aed,stroke:#c4b5fd,color:#f5f3ff
    style IS fill:#be185d,stroke:#f9a8d4,color:#fdf2f8
```

<div class="grid cards" markdown>

-   :material-tools:{ .lg .middle } **[System Tools](system_tools.md)**

    ---

    Convert (Format · Codec · Sampler) · Merge · Similarity · Extractor (Video · Image) · Wallpaper (System Display(s) · Monitor Display)

    *38 screenshots · 3 diagrams*

-   :material-database:{ .lg .middle } **[Library Database](library_database.md)**

    ---

    Listings (Content · Entity) · Image Search · Scan and Tag · Maintenance

    *25 screenshots · covers the new Metadata Editor, side-by-side filter lists, and Image Registry*

-   :material-web:{ .lg .middle } **[Web Integration](web_integration.md)**

    ---

    Crawler · Requests · Cloud Synchronization · Reverse Search · Entity Reconnaissance

    *23 screenshots · privacy trade-offs called out explicitly*

-   :material-brain:{ .lg .middle } **[Deep Learning](deep_learning.md)**

    ---

    Training · Generation · Evaluation · Inference · ComfyUI

    *8 screenshots · GAN metric reference table*

-   :material-image-multiple:{ .lg .middle } **[Image Stitching](image_stitching.md)**

    ---

    Stitch · Graph · Adjust · Canvas · Statistics · Sequence Builder · Hybrid Stitch · Animation Clusters

    *19 screenshots · the full ASP pipeline workflow*

-   :material-map-marker-path:{ .lg .middle } **[Typical Workflows](workflows.md)**

    ---

    Six complete, click-by-click walkthroughs — multi-site crawling, smart-selection panorama stitching (automated / semi-automated / full HITL), wallpaper (two ways), cataloguing a folder, dedupe, train-then-generate a LoRA — with every parameter's technical mechanics, trade-offs, and links to the underlying papers/docs

    *41 annotated screenshots with numbered step badges and click targets*

-   :material-cog:{ .lg .middle } **[Settings and Login](settings_and_login.md)**

    ---

    The Login Window and every Application Settings tab: Account and Vault · Startup and Profiles · Tab Configs · Display and Media · System and Logging · Shortcuts · Bulk Update

    *25 screenshots · app-wide configuration, not tied to one category*

</div>

!!! tip "Tab layouts evolve"
    When a control described here has moved, its group-box title (quoted in the tutorials) is the fastest thing to search for in the UI. Sections marked :material-new-box: **New** document behavior that changed recently — check those first if something doesn't match what you see.

!!! info "How these were built"
    Every screenshot was captured live against the running app (not mocked up), and every described behavior was cross-checked against the current widget source and recent commits/changelog entries — not written from memory. If a tutorial and the app ever disagree, the app is right; please flag the mismatch.
