# Web Integration — Tab Tutorials

The **Web Integration** category holds every tab that talks to the network: bulk image crawling, raw HTTP requests, cloud backup synchronization, reverse image search, and identity reconnaissance. API credentials generally come from the encrypted vault (Settings → API keys) rather than being typed in plain text.

---

## Crawler

Bulk-downloads images from websites into a chosen **Download Dir**.

### Crawler Type

The type switches the whole settings page:

- **General Web Crawler** — a Selenium-driven browser scraper for arbitrary sites. You describe *how to walk the page* yourself with the Actions list (below). Extra settings: target **Browser** (`chrome`, `firefox`, `edge`, `brave`) and **headless mode** (run the browser invisibly; disable to watch it work or to get past interactive checks). A *General Login Configuration* section handles sites that need a signed-in session.
- **Image Board Crawler (Danbooru / Gelbooru / Sankaku Complex API)** — no browser at all; talks to the board's public API. Fields: **Board URL**, **Resource** (`posts`, `tags`, `comments`…), **Tags** (the board's own tag query syntax, e.g. `1girl scenic original`), **Limit (per page)**, **Max Pages**, **Extra Query Params** (raw query-string extras like `deleted=show&order=count`), and optional **Username** / **API Key** authentication for higher rate limits or restricted content.

### String to Replace + Replacements (General crawler)

The pagination mechanism. The crawler visits the **Target URL** once *per replacement*: it takes the substring given in **String to Replace** (e.g. `page=1`) and substitutes each comma-separated value from **Replacements** (e.g. `page=2, page=3`) in turn — so `https://example.com/gallery?page=1` with replacements `page=2, page=3` crawls pages 1→2→3 with the same Actions applied on every page. Any URL substring works: path segments (`/chapter-1/` → `/chapter-2/`), query values, IDs. Leave both empty to crawl only the Target URL.

### Actions (General crawler)

An ordered mini-program executed *for each image/element* found on the page (with **Skip First / Skip Last** trimming the element list). Build it by picking an action, optionally a parameter, and **Add**; the list runs top to bottom:

- **Find Parent Link (`<a>`)** — step from a matched element up to its enclosing link (thumbnails usually live inside the link to the full view).
- **Download Simple Thumbnail (Legacy)** — grab the thumbnail image directly.
- **Extract High-Res Preview URL** — pull the full-resolution URL a preview element points at.
- **Open Link in New Tab** / **Switch to Last Tab** / **Close Current Tab** — tab navigation, for galleries that open full views in new tabs.
- **Click Element by Text** — click a button/link identified by its visible text (parameter).
- **Wait for Page Load** / **Wait X Seconds** — synchronization; the parameter of *Wait X Seconds* is the delay.
- **Find Element by CSS Selector** — re-target the current element by a CSS selector (parameter).
- **Find `<img>` Number X on Page** — target the Nth image element (parameter = N).
- **Download Image from Element** — download whatever image the current element resolves to.
- **Download Current URL as Image** — when the tab's URL *is* the image.
- **Wait for Gallery (Context Reset)** — wait for the gallery view to be back and reset the element context (use after closing a full-view tab).
- **Scrape Text (Saves to JSON)** — harvest text (captions, tags) alongside the images into a JSON file.
- **Scan Page for Text and Skip if Found** — skip the current element when the page contains a given text (parameter) — a content filter.
- **Refresh Current Element** — re-fetch the element after DOM changes.

A typical high-res gallery recipe: *Find Parent Link → Open Link in New Tab → Switch to Last Tab → Wait for Page Load → Find `<img>` Number 1 on Page → Download Image from Element → Close Current Tab → Wait for Gallery (Context Reset)*.

### Deduplication and Selection Mode

What happens *after* the crawl finishes, before files are kept:

- **Download All (Default)** — keep everything that was downloaded.
- **Manual Selection** — a review dialog shows every downloaded image with checkboxes; only the checked ones survive, the rest are deleted (Cancel discards the entire crawl).
- **Automated Selection** — first a *duplicate-scan configuration* dialog (method/threshold), then a scan marks likely duplicates among the downloads, and a pruning dialog appears with duplicates pre-unchecked — accept to keep only the checked set. Best for boards where the same image recurs across pages.

---

## Requests

A raw HTTP client for API experiments and scripted downloads — two ordered lists that together form a small batch job.

- **Base URL** — the prefix every request builds on.
- **Request Type** — `GET` or `POST` for each request you add:
    - **GET** — the parameter field is appended to the Base URL as a suffix (path or query string).
    - **POST** — the parameter field is parsed as `key:val, k2:v2` pairs and sent as the POST body.
    - Add several requests; the **Request List runs in order**, top to bottom (right-click entries to manage them).
- **Response Actions** — executed **for each request's response**, also in order:
    - **Print Response URL / Status Code / Headers / Content (Text)** — write the corresponding part of the response into the log output (inspection/debugging).
    - **Save Response Content (Binary)** — write the raw response body to disk; the parameter is the file path. This is the action that turns the tab into a downloader.

Example: Base URL `https://api.example.com`, requests `GET /image/1.png`, `GET /image/2.png`, actions *Print Response Status Code* + *Save Response Content (Binary)* → two files saved with their statuses logged.

---

## Cloud Synchronization

Backs up a local directory tree to a cloud drive.

### Cloud Provider

- **Google Drive (Service Account)** — server-to-server auth; no browser login, works unattended. Shows the *Share Folder With* field because service-account uploads live in the service account's own storage — sharing the destination folder to your personal email is how you see the files in your own Drive UI.
- **Google Drive (Personal Account)** — OAuth login as you; files land directly in your Drive.
- **Dropbox** and **OneDrive** — token-based clients for those providers.

### Required files / keys

Which credentials are needed depends on the provider:

- *Service Account*: a **Service Account Key File** (`service_account_key.json` downloaded from Google Cloud Console; its contents are loaded via the vault).
- *Personal Account*: a **Client Secrets File** (`client_secrets.json`, the OAuth client you create in Google Cloud Console) plus a **Token File** — this one is **auto-generated**: on first sync a browser window asks you to authorize, and the resulting `token.json` is stored at the configured path and silently reused/refreshed afterwards. You never create the token yourself; delete it to force a re-login.
- *Dropbox*: an access **token** stored in the vault under `dropbox_token` (create an app in the Dropbox App Console to obtain one).
- *OneDrive*: its provider token/credentials, likewise vault-managed.

Below the credentials: **Local Source Directory** (what to upload), **Remote Destination Path** (target folder on the drive), sync-behavior options, and **View Remote** (Google) to inspect the remote folder map.

---

## Reverse Search

Finds where an image (or images — the tab works on a gallery selection) appears, or what looks like it.

### Engine

- **Google Lens** — drives a real browser through Google Lens and scrapes the results. Engine-specific options: **Browser** (`brave`/`chrome`/`firefox`/`edge`), **Mode** (below), **Keep Browser Open** (leave the browser up after the search — useful for continuing manually), and a resolution filter for results.
- **TinEye API** — the commercial TinEye matching API; needs credentials via the `TINEYE_API_KEY` / `TINEYE_API_SECRET` environment variables or `backend/config/api_keys.yaml`. No browser involved.
- **Local AI Search** — fully offline CBIR: the query image is embedded with CLIP ViT-B/32 and matched against your own local index at `~/.image-toolkit/cbir_index/`. Its option is **Results (top-k)** — how many nearest neighbours to return. Nothing leaves your machine.

### Mode (Google Lens)

Selects which Lens result page gets scraped:

- **All** — the default mixed results page.
- **Visual matches** — similar-looking images (style/content matches, not necessarily the same picture).
- **Exact matches** — pages containing this exact image — the mode for finding an image's origin or checking where it has been reposted.

---

## Entity Reconnaissance

Local-first OSINT identity resolution: "who/what is in this image?", answered against **your own** reference dataset, with an auditable evidence trail. The scope selector governs privacy: **Local only (offline)** never touches the network (Strict Privacy Mode); **Web only** uses reverse-image discovery; **Local + Web** tries the local index first and falls back to the web.

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

Pick the option matching your dataset *before* building — the index is embedding-specific.

### Source vs. Identity vs. Provenance (the three panes)

- **Source** (left) — the query. *Load Image…*, then either **click a subject in the image** — a SAM2 segmenter cuts out exactly the clicked person/character, so group shots resolve one subject at a time — or press **Resolve Identity** to use the whole frame.
- **Identity** (center) — the verdict: the resolved name, a **confidence** bar, the **method** that produced the match (local index / web engine), and the **origin**. *Export JSON / Export CSV* save the full report.
- **Provenance** (right) — the evidence: a tree of every source that contributed to the identification with its score (double-click to open). This is what makes a resolution auditable instead of a black-box answer.

Below the panes, the **Batch Dataset Builder** turns resolution into dataset curation: add a pile of unsorted images, each gets a *suggested identity* + score row, and **Approve All → Move to Identity Folders** files them into `<target>/<FirstName_LastName>/` directories — growing the identity dataset with verified samples.
