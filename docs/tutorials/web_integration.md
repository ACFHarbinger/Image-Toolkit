# :material-web: Web Integration — Tab Tutorials

The **Web Integration** category holds every tab that talks to the network: bulk image crawling, raw HTTP requests, cloud backup synchronization, reverse image search, and identity reconnaissance. API credentials generally come from the encrypted vault (Settings → API keys) rather than being typed in plain text.

```mermaid
flowchart LR
    Web((The Web)) -->|Crawler| Files1([Downloaded images])
    Web -->|Requests| Data([API responses / files])
    Files1 <-->|Cloud Synchronization| Cloud[(Google Drive · Dropbox · OneDrive)]
    Files1 -->|Reverse Search| Origin([Where an image came from])
    Files1 -->|Entity Reconnaissance| Identity([Who/what is in an image])

    style Web fill:#1e3a8a,stroke:#60a5fa,color:#eff6ff
    style Cloud fill:#0f766e,stroke:#2dd4bf,color:#ecfeff
```

!!! warning "Privacy note"
    Reverse Search and Entity Reconnaissance can send image data to third-party services (Google Lens, TinEye) unless you restrict them to their fully offline modes (**Local AI Search**, **Local only (offline)**). Check the mode before searching anything sensitive.

---

## Crawler

Bulk-downloads images from websites into a chosen **Download Dir**.

![Crawler tab, General Web Crawler type: Login Configuration, Web Scraper Settings, Actions, Output Configuration](images/web_integration/crawler_general_top.png)
![Crawler tab scrolled further: Actions list populated, Output Configuration with optional Screenshot Dir, Selection Mode](images/web_integration/crawler_general_scrolled.png)

### Crawler Type

![Crawler Type dropdown: General Web Crawler, Image Board Crawler (Danbooru/Gelbooru/Sankaku Complex API)](images/web_integration/crawler_type_dropdown.png)

The type switches the whole settings page:

=== "General Web Crawler"
    A Selenium-driven browser scraper for arbitrary sites. You describe *how to walk the page* yourself with the Actions list (below). Extra settings: target **Browser** (`chrome`, `firefox`, `edge`, `brave`) and **headless mode** (run the browser invisibly; disable to watch it work or to get past interactive checks). A *General Login Configuration* section handles sites that need a signed-in session.

    ![Browser dropdown: chrome, firefox, edge, brave](images/web_integration/crawler_browser_dropdown.png)

=== "Image Board Crawler (API)"
    No browser at all; talks to the board's public API directly. Three boards are supported, each with its own **API Configuration** and **Authentication (Optional)** section:

    | Board | Default Board URL | Resource | Auth fields |
    |---|---|---|---|
    | **Danbooru** | `danbooru.donmai.us` | `posts` | Username + API Key |
    | **Gelbooru** | `gelbooru.com` | `post` | User ID + API Key |
    | **Sankaku Complex** | `capi-v2.sankakucomplex.com` | `posts` | Username/Email + Password |

    ![Image Board Crawler (Danbooru API) full form](images/web_integration/crawler_danbooru_api.png)
    ![Image Board Crawler (Gelbooru API) full form](images/web_integration/crawler_gelbooru_api.png)
    ![Image Board Crawler (Sankaku Complex API) full form](images/web_integration/crawler_sankaku_api.png)

    Common fields across all three: **Tags** (the board's own tag query syntax, e.g. `1girl scenic original`), **Limit (per page)**, **Max Pages**, and **Extra Query Params** (raw query-string extras like `deleted=show&order=count`). Authentication is optional and only raises rate limits / unlocks restricted content — anonymous querying works out of the box.

### String to Replace + Replacements (General crawler)

The pagination mechanism. The crawler visits the **Target URL** once *per replacement*: it takes the substring given in **String to Replace** (e.g. `page=1`) and substitutes each comma-separated value from **Replacements** (e.g. `page=2, page=3`) in turn — so `https://example.com/gallery?page=1` with replacements `page=2, page=3` crawls pages 1→2→3 with the same Actions applied on every page. Any URL substring works: path segments (`/chapter-1/` → `/chapter-2/`), query values, IDs. Leave both empty to crawl only the Target URL.

### Actions (General crawler)

An ordered mini-program executed *for each image/element* found on the page (with **Skip First / Skip Last** trimming the element list). Build it by picking an action, optionally a parameter, and **Add**; the list runs top to bottom.

![Actions dropdown open, listing all 15 available step types](images/web_integration/crawler_actions_dropdown.png)

| Action | What it does |
|---|---|
| **Find Parent Link (`<a>`)** | Step from a matched element up to its enclosing link (thumbnails usually live inside the link to the full view). |
| **Download Simple Thumbnail (Legacy)** | Grab the thumbnail image directly. |
| **Extract High-Res Preview URL** | Pull the full-resolution URL a preview element points at. |
| **Open Link in New Tab** / **Switch to Last Tab** / **Close Current Tab** | Tab navigation, for galleries that open full views in new tabs. |
| **Click Element by Text** | Click a button/link identified by its visible text (parameter). |
| **Wait for Page Load** / **Wait X Seconds** | Synchronization; the parameter of *Wait X Seconds* is the delay. |
| **Find Element by CSS Selector** | Re-target the current element by a CSS selector (parameter). |
| **Find `<img>` Number X on Page** | Target the Nth image element (parameter = N). |
| **Download Image from Element** | Download whatever image the current element resolves to. |
| **Download Current URL as Image** | When the tab's URL *is* the image. |
| **Wait for Gallery (Context Reset)** | Wait for the gallery view to be back and reset the element context (use after closing a full-view tab). |
| **Scrape Text (Saves to JSON)** | Harvest text (captions, tags) alongside the images into a JSON file. |
| **Scan Page for Text and Skip if Found** | Skip the current element when the page contains a given text (parameter) — a content filter. |
| **Refresh Current Element** | Re-fetch the element after DOM changes. |

!!! example "A typical high-res gallery recipe"
    **Find Parent Link → Open Link in New Tab → Switch to Last Tab → Wait for Page Load → Find `<img>` Number 1 on Page → Download Image from Element → Close Current Tab → Wait for Gallery (Context Reset)**

### Deduplication and Selection Mode

What happens *after* the crawl finishes, before files are kept:

![Selection Mode dropdown: Download All (Default), Manual Selection, Automated Selection](images/web_integration/crawler_selection_mode_dropdown.png)

- **Download All (Default)** — keep everything that was downloaded.
- **Manual Selection** — a review dialog shows every downloaded image with checkboxes; only the checked ones survive, the rest are deleted (Cancel discards the entire crawl).
- **Automated Selection** — first a *duplicate-scan configuration* dialog (method/threshold), then a scan marks likely duplicates among the downloads, and a pruning dialog appears with duplicates pre-unchecked — accept to keep only the checked set. Best for boards where the same image recurs across pages.

---

## Requests

A raw HTTP client for API experiments and scripted downloads — two ordered lists that together form a small batch job.

![Requests tab: Base URL, Request List, Response Actions, Run Requests](images/web_integration/requests_main.png)

- **Base URL** — the prefix every request builds on.
- **Request Type** — `GET` or `POST` for each request you add:

    ![Request Type dropdown: GET / POST](images/web_integration/requests_type_dropdown.png)

    - **GET** — the parameter field is appended to the Base URL as a suffix (path or query string).
    - **POST** — the parameter field is parsed as `key:val, k2:v2` pairs and sent as the POST body.
    - Add several requests; the **Request List runs in order**, top to bottom (right-click entries to manage them).
- **Response Actions** — executed **for each request's response**, also in order:

    ![Response Actions dropdown: Print Response URL / Status Code / Headers / Content, Save Response Content (Binary)](images/web_integration/requests_response_actions_dropdown.png)

    - **Print Response URL / Status Code / Headers / Content (Text)** — write the corresponding part of the response into the log output (inspection/debugging).
    - **Save Response Content (Binary)** — write the raw response body to disk; the parameter is the file path. This is the action that turns the tab into a downloader.

!!! example
    Base URL `https://api.example.com`, requests `GET /image/1.png`, `GET /image/2.png`, actions *Print Response Status Code* + *Save Response Content (Binary)* → two files saved with their statuses logged.

---

## Cloud Synchronization

Backs up a local directory tree to a cloud drive.

### Cloud Provider

![Cloud Provider dropdown: Google Drive (Service Account), Google Drive (Personal Account), Dropbox, OneDrive](images/web_integration/cloud_sync_provider_dropdown.png)

=== "Google Drive (Service Account)"
    Server-to-server auth; no browser login, works unattended. Shows the *Share Folder With* field because service-account uploads live in the service account's own storage — sharing the destination folder to your personal email is how you see the files in your own Drive UI.

    ![Google Drive (Service Account): key file, source/dest paths, Share Folder With, Sync Behavior, Share Folder Now](images/web_integration/cloud_sync_google_service_account.png)

=== "Google Drive (Personal Account)"
    OAuth login as you; files land directly in your Drive.

    ![Google Drive (Personal Account): Client Secrets File, auto-generated Token File, source/dest paths](images/web_integration/cloud_sync_google_personal_account.png)

=== "Dropbox"
    Token-based client — a leaner form with just source/dest paths and sync behavior once the vault-stored token is in place.

    ![Dropbox: source/dest paths, Sync Behavior](images/web_integration/cloud_sync_dropbox.png)

=== "OneDrive"
    Same lean form as Dropbox, using OneDrive's vault-managed provider credentials.

    ![OneDrive: source/dest paths, Sync Behavior](images/web_integration/cloud_sync_onedrive.png)

### Required files / keys

Which credentials are needed depends on the provider:

- *Service Account*: a **Service Account Key File** (`service_account_key.json` downloaded from Google Cloud Console; its contents are loaded via the vault).
- *Personal Account*: a **Client Secrets File** (`client_secrets.json`, the OAuth client you create in Google Cloud Console) plus a **Token File** — this one is **auto-generated**: on first sync a browser window asks you to authorize, and the resulting `token.json` is stored at the configured path and silently reused/refreshed afterwards. You never create the token yourself; delete it to force a re-login.
- *Dropbox*: an access **token** stored in the vault under `dropbox_token` (create an app in the Dropbox App Console to obtain one).
- *OneDrive*: its provider token/credentials, likewise vault-managed.

### Sync Behavior

Below the credentials: **Local Source Directory** (what to upload), **Remote Destination Path** (target folder on the drive), and two independent orphan-handling policies:

| Files found... | Merge (default) | Mirror | Ignore |
|---|---|---|---|
| **Only Locally** | Upload to Remote | :material-alert: Delete from Local | Do Nothing |
| **Only on Remote** | Download to Local | :material-alert: Delete from Remote | Do Nothing |

!!! danger "Mirror options are destructive"
    **Delete from Local (Mirror Remote)** and **Delete from Remote (Mirror Local)** are shown in red for a reason — they permanently remove files to force one side to match the other. Use **Perform Dry Run (Simulate only)** first to preview exactly what a sync would do before running it for real, especially with a Mirror policy selected.

**View Remote Files Map** inspects the remote folder structure (Google providers only, via **Share Folder Now**/related APIs); **Run Synchronization Now** executes the configured behavior.

---

## Reverse Search

Finds where an image (or images — the tab works on a gallery selection) appears, or what looks like it.

![Reverse Search tab: Image Source, Engine, Browser, Mode, Keep Browser Open, results gallery](images/web_integration/reverse_search_main.png)

### Engine

![Engine dropdown: Google Lens, TinEye API, Local AI Search](images/web_integration/reverse_search_engine_dropdown.png)

=== "Google Lens"
    Drives a real browser through Google Lens and scrapes the results. Engine-specific options: **Browser** (`brave`/`chrome`/`firefox`/`edge`), **Mode** (below), **Keep Browser Open** (leave the browser up after the search — useful for continuing manually), and a resolution filter for results.

=== "TinEye API"
    The commercial TinEye matching API; needs credentials via the `TINEYE_API_KEY` / `TINEYE_API_SECRET` environment variables or `backend/config/api_keys.yaml`. No browser involved.

    ![TinEye API config: credentials-via-env note, Search Selected Image](images/web_integration/reverse_search_tineye_config.png)

=== "Local AI Search"
    Fully offline CBIR: the query image is embedded with CLIP ViT-B/32 and matched against your own local index at `~/.image-toolkit/cbir_index/`. Its option is **Results (top-k)** — how many nearest neighbours to return. Nothing leaves your machine.

    ![Local AI Search config: Results (top-k), local index path, CLIP ViT-B/32 model](images/web_integration/reverse_search_local_ai_config.png)

    !!! tip "The only fully private option"
        If you're reverse-searching anything sensitive, **Local AI Search** is the mode that guarantees no data leaves your machine — Google Lens and TinEye both send the image to a third-party service.

### Mode (Google Lens)

Selects which Lens result page gets scraped:

![Mode dropdown: All, Visual matches, Exact matches](images/web_integration/reverse_search_mode_dropdown.png)

- **All** — the default mixed results page.
- **Visual matches** — similar-looking images (style/content matches, not necessarily the same picture).
- **Exact matches** — pages containing this exact image — the mode for finding an image's origin or checking where it has been reposted.

---

## Entity Reconnaissance

Local-first OSINT identity resolution: "who/what is in this image?", answered against **your own** reference dataset, with an auditable evidence trail. The scope selector governs privacy: **Local only (offline)** never touches the network (Strict Privacy Mode); **Web only** uses reverse-image discovery; **Local + Web** tries the local index first and falls back to the web.

![Entity Reconnaissance tab: Identity Dataset and Discovery header, three-pane Source/Identity/Provenance layout, Batch Dataset Builder](images/web_integration/entity_recon_main.png)

### Build Identity Index

Feeds the resolver. Point **Dataset root** at a directory organized as one folder per identity:

```
/Dataset/FirstName_LastName/photo1.jpg
/Dataset/FirstName_LastName/photo2.jpg
/Dataset/Other_Person/pic.png
```

**Build Identity Index** embeds every image and builds a fast HNSW nearest-neighbour index; the *folder name* is the identity label a match reports. Rebuild after adding identities or images.

### Embedding Options

The embedding model decides *what kind of subject* the index can recognize:

- **Faces (ArcFace)** — a face-recognition embedding; the right choice when your identities are real people photographed face-on. Ignores clothing/background.
- **Characters / objects (CLIP)** — a general visual-semantic embedding; the right choice for illustrated/anime characters, mascots, or objects, where "identity" means overall appearance rather than facial geometry.

!!! warning "Pick the embedding before building"
    The index is embedding-specific — match the option to your dataset *before* building, or the index will need to be rebuilt from scratch.

### Source vs. Identity vs. Provenance (the three panes)

- **Source** (left) — the query. *Load Image…*, then either **click a subject in the image** — a SAM2 segmenter cuts out exactly the clicked person/character, so group shots resolve one subject at a time — or press **Resolve Identity** to use the whole frame.
- **Identity** (center) — the verdict: the resolved name, a **confidence** bar, the **method** that produced the match (local index / web engine), and the **origin**. *Export JSON / Export CSV* save the full report.
- **Provenance** (right) — the evidence: a tree of every source that contributed to the identification with its score (double-click to open). This is what makes a resolution auditable instead of a black-box answer.

Below the panes, the **Batch Dataset Builder** turns resolution into dataset curation: add a pile of unsorted images, each gets a *suggested identity* + score row, and **Approve All → Move to Identity Folders** files them into `<target>/<FirstName_LastName>/` directories — growing the identity dataset with verified samples.
