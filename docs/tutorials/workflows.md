# :material-map-marker-path: Typical Workflows

The category tutorials ([System Tools](system_tools.md), [Library Database](library_database.md), [Web Integration](web_integration.md), [Deep Learning](deep_learning.md), [Image Stitching](image_stitching.md)) document every tab in isolation. This page instead walks through complete, goal-oriented tasks — several of which cross tab categories — from the **Main Window** through to a finished result.

!!! info "Windows referenced in this app"
    - **Login Window** — the vault-unlock prompt shown once per session, before the Main Window appears. Every workflow below assumes you're already past it.
    - **Main Window** — the window with the **Select Category** dropdown and the tab strip; this is where every step below happens unless stated otherwise.
    - **Settings Window** — opened from the Main Window's menu; only referenced where a workflow depends on a setting living there.
    - **Auxiliary windows/dialogs** — file pickers, the **Edit Metadata** editor, import wizards, etc. — pop up over the Main Window when a step opens one; each is captioned explicitly below.

!!! tip "How to read the annotated screenshots"
    Each screenshot below has an **amber numbered badge** marking which workflow step it illustrates, and a colored box/arrow pointing at the exact control to interact with.

    | Marking | Meaning |
    |---|---|
    | `1`, `2`, `3`… | A single required step — do these in order. |
    | `2a` / `2b` / `2c` | Alternative ways to accomplish the same step — pick one path, not all. |
    | :material-square-outline:{ style="color:#ff2d95" } Magenta box | The primary control for this step. |
    | :material-square-outline:{ style="color:#39ff14" } Green box | The control for an alternate path (the "b"/"c" option). |
    | :material-square-outline:{ style="color:#ffd700" } Gold box | A checkbox/toggle to set before proceeding. |
    | :material-arrow-top-right:{ style="color:#ff2d95" } Arrow | Drag/assignment direction between two elements. |

---

## Workflow 1 — Download images, then stitch a panorama

Crawl a set of images from an imageboard into a folder, then feed that folder straight into the automatic stitching pipeline — with three ways to finish depending on how much control you want.

**Start from:** Main Window → **Select Category: Web Integration** → **Crawler** tab.

```mermaid
flowchart LR
    A["1. Configure crawler\n(Web Integration → Crawler)"] --> B["2. Run Crawler"]
    B --> C["3. Add downloaded images\n(Image Stitching → Stitch)"]
    C --> D{4. Generate panorama}
    D -->|4a| E([Automated])
    D -->|4b| F([Automated + Adjust touch-up])
    D -->|4c| G([Full HITL])

    style D fill:#7c3aed,stroke:#c4b5fd,color:#f5f3ff
```

1. Pick **Crawler Type: Image Board Crawler**, fill in **Board URL**/**Tags**, and set **Download Dir** to the folder you want the images saved into.

    ![Step 1: configure the Image Board Crawler's Board URL/Tags and Download Dir](images/workflows/01_crawl_configure.png)

2. Scroll down and click **Run Crawler**. Wait for the crawl to finish (**Ready.** reappears in the status line).

    ![Step 2: click Run Crawler at the bottom of the Crawler tab](images/workflows/02_crawl_run.png)

3. Switch to **Select Category: Image Stitching** → **Stitch** tab. In **Source Frames**, click **Add** and select the images the crawler just downloaded — this opens a standard file picker.

    ![Step 3: click Add in the Stitch tab's Source Frames pane](images/workflows/03_stitch_add_frames.png)

4. Generate the panorama — three pathways depending on how much control you want:

    === "4a — Fully automated"
        Leave every **Pipeline Stage** at its default and click **▶ Stitch Panorama**. Fastest path; best for clean, well-overlapping frames.

        ![Step 4a: click Stitch Panorama with default settings](images/workflows/04a_stitch_run_automated.png)

    === "4b — Automated + manual touch-up"
        If the first automated run has a flawed frame (bad exposure, wrong crop), switch to the **Adjust** tab, fix that one frame, then click **→ Add to Stitch** to swap the corrected version back into the Stitch tab's frame list before re-running **▶ Stitch Panorama**.

        ![Step 4b: in Adjust, click "Add to Stitch" to push the corrected frame back](images/workflows/04b_adjust_add_to_stitch.png)

    === "4c — Full HITL"
        For heavy parallax or effects layers the automatic pipeline can't handle cleanly, check **Human-in-the-loop review** in the **HITL** box before clicking **▶ Stitch Panorama** — the pipeline now pauses at each checkpoint (frame exclusion, edge-graph review, canvas nudging, coverage inspection) for your input instead of running straight through.

        ![Step 4c: check Human-in-the-loop review in the HITL group box](images/workflows/04c_stitch_hitl_checkbox.png)

        !!! tip "Going fully manual"
            If even HITL checkpoints aren't enough control, the [Hybrid Stitch](image_stitching.md#hybrid-stitch) tab skips the automatic pipeline entirely and lets you align pairs by hand from the start.

---

## Workflow 2 — Set your desktop wallpaper

Two independent ways to change what's on screen: a direct one-shot assignment, or a graph-driven sequence that cycles automatically. Pick whichever fits — they don't need to be combined.

**Start from:** Main Window → **Select Category: System Tools** → **Wallpaper** tab.

```mermaid
flowchart LR
    Start(["Wallpaper tab"]) -->|path a| A1["1a. Select a monitor\n+ assign an image"]
    A1 --> A2["2a. Set Wallpaper"]
    Start -->|path b| B1["1b. Add Node(s)\nin Graph Canvas"]
    B1 --> B2["2b. Start In-App Slideshow"]

    style Start fill:#1d4ed8,stroke:#93c5fd,color:#eff6ff
```

=== "Path A — System Display(s) (direct assignment)"

    1. On the **System Display(s)** subtab, click the monitor tile you want to change, then click a thumbnail in the gallery below to assign it — an arrow in the screenshot shows this assignment relationship.

        ![Step 1a: click a monitor tile, then a gallery thumbnail to assign it](images/workflows/05a_wallpaper_pick_monitor.png)

    2. Scroll down and click **Set Wallpaper** to apply it to the real desktop immediately.

        ![Step 2a: click Set Wallpaper at the bottom of the tab](images/workflows/06a_wallpaper_set.png)

=== "Path B — Monitor Display (graph sequencer)"

    1. On the **Monitor Display** subtab, click **+ Add Node** for each wallpaper you want in the rotation (drag images from the gallery onto the canvas works too), then use **→ Connect** and **★ Set Start** to wire up the order.

        ![Step 1b: click + Add Node on the Graph Canvas](images/workflows/05b_wallpaper_graph_add_node.png)

    2. Click **▶ Start In-App Slideshow** to begin cycling through the graph while the app is open (**⏱ Start Slideshow Daemon** instead if you want it to keep running after you close the app).

        ![Step 2b: click Start In-App Slideshow](images/workflows/06b_wallpaper_graph_start_slideshow.png)

!!! note "Why two paths exist"
    System Display(s) is a flat "pick one image per monitor" model — quick, but it doesn't change over time. Monitor Display trades that simplicity for a sequencer: each display gets its own graph, letting you build loops, branches, and timed transitions instead of a static assignment.

---

## Workflow 3 — Catalogue a folder into your library

Register a folder of images into the searchable index *and* create catalogue entries for the show(s) it contains, using the same source folder for both.

**Start from:** Main Window → **Select Category: Library Database** → **Scan and Tag** tab.

```mermaid
flowchart LR
    A["1. Select scanned images"] --> B["2. Add/Update N Selected Images"]
    B --> C["3. Metadata Editor:\nApply to All Image Tabs"]
    C --> D["Listings → Content Listings"]
    D --> E{"4. Import Dir wizard"}
    E -->|4a| F["Browse to folder"]
    F -->|4b| G(["Import Selected"])
```

1. With **Scan Directory** already pointed at your folder, click thumbnails in the scan gallery to select the images you want indexed (a green border marks the selection).

    ![Step 1: click a thumbnail in the Scan and Tag gallery to select it](images/workflows/07_scan_select_thumbnail.png)

2. Click **Add/Update N Selected Images** — this opens the **Edit Metadata** auxiliary window instead of writing immediately.

    ![Step 2: click Add/Update N Selected Images at the bottom of Scan and Tag](images/workflows/08_scan_add_update.png)

3. In the **Edit Metadata** window's **Batch / Overview** tab, set **Group**/**Subgroup**/**Tags** once, then click **↓ Apply to All Image Tabs** to fan those values out to every selected image, and finish with **✔ Confirm & Save**.

    ![Step 3: set Group/Subgroup/Tags then click Apply to All Image Tabs](images/workflows/09_metadata_editor_apply_all.png)

4. Switch to **Listings → Content Listings** and click **📂 Import Dir** to also create a catalogue entry for the show(s) in that same folder:

    a. In the **Import Listings from Video Directory** window, click **Browse..** and point it at the source folder.

    ![Step 4a: click Browse.. in the Import Listings from Video Directory dialog](images/workflows/10_import_dir_browse.png)

    b. Review the detected series, adjust the shared **Type**/**Status**/**Genres** metadata if needed, and click **Import Selected**.

    ![Step 4b: click Import Selected to bulk-create show entries](images/workflows/11_import_dir_confirm.png)

!!! tip "Order matters here"
    Step 3's Group/Subgroup/Tags describe the *images* (for Image Search filtering); step 4's Import Dir wizard creates the *show entries* (for the Listings catalogue). They read the same folder but populate different parts of the library — running both is what makes a folder fully searchable both by image metadata and by show.

---

## Workflow 4 — Find and remove duplicate images

Scan a directory for duplicate/near-duplicate images and clear them out, with two different levels of destructiveness depending on what you find.

**Start from:** Main Window → **Select Category: System Tools** → **Similarity** tab.

```mermaid
flowchart LR
    A["1. Set Source path\n+ Scan for Similar Images"] --> B["2. Review grouped results"]
    B --> C{3. Triage}
    C -->|3a| D(["Delete Selected Files"])
    C -->|3b| E(["Delete Directory and Contents"])

    style C fill:#b45309,stroke:#fbbf24,color:#fffbeb
```

1. Set **Source path** to the directory you want to check (leave **Scan Method** at the recommended **Similarity Engine (tiered clusters)**), then click **⚡ Scan for Similar Images**.

    ![Step 1: set Source path and click Scan for Similar Images](images/workflows/12_similarity_source_and_scan.png)

2. Once the scan finishes, the gallery below fills with the matched groups — scroll through and inspect which copies you want to keep.

3. Triage what you found:

    === "3a — Remove specific files"
        Select the unwanted copies in the results gallery, then click **Delete Selected Files (N)**.

        ![Step 3a: click Delete Selected Files after selecting the unwanted copies](images/workflows/13a_similarity_delete_selected.png)

    === "3b — Wipe an entire duplicate folder"
        If a whole subfolder turned out to be nothing but duplicates of files elsewhere, select it and click **Delete Directory and Contents** instead — faster than selecting every file individually.

        ![Step 3b: click Delete Directory and Contents to remove a whole duplicate folder](images/workflows/13b_similarity_delete_directory.png)

!!! danger "Keep confirmation on"
    Both delete actions are irreversible. **Require confirmation before delete (recommended)** is checked by default on this tab — leave it on unless you're certain.

---

## Workflow 5 — Train and generate with a custom LoRA

Fine-tune a LoRA on your own character/style, then immediately use it to generate new images — the same **Output Name** and trigger word tie the two tabs together.

**Start from:** Main Window → **Select Category: Deep Learning** → **Training** tab.

```mermaid
flowchart LR
    A["1. Set Output Name\n+ Trigger Word"] --> B["2. Start Training"]
    B --> C["Generation tab"]
    C --> D["3. Set LoRA Path\n(same Output Name)"]
    D --> E["4. Generate"]
```

1. With **Model Architecture: LoRA (Diffusion and GANs)** selected and **Dataset Folder** already pointed at your training images, set **Output Name** (the filename your trained LoRA will be saved as) and **Trigger Word (Prompt)** (the token you'll use later to activate it).

    ![Step 1: set Output Name and Trigger Word fields](images/workflows/14_training_fields.png)

2. Click **Start Training** and wait for the run to finish — progress prints to the log beneath the form.

    ![Step 2: click Start Training](images/workflows/15_training_start.png)

3. Switch to the **Generation** tab (same **Model Architecture: LoRA**, same **Select Model** base you trained against). Set **LoRA Path** to the **Output Name** from step 1, and make sure **Prompt** includes the same trigger word.

    ![Step 3: set LoRA Path to the Output Name trained in step 1](images/workflows/16_generation_lora_path.png)

4. Click **Generate**.

    ![Step 4: click Generate](images/workflows/17_generation_generate.png)

!!! tip "Trigger word must match exactly"
    The **Trigger Word (Prompt)** from Training and the token you put in Generation's **Prompt** must be the same string — that's the only thing that actually activates the LoRA's learned concept. A mismatch (typo, different casing/spacing) silently generates from the base model as if the LoRA weren't loaded.
