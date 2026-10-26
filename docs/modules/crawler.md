# Web Crawler (`crawler`)

| Field | Value |
|---|---|
| **Capability ID** | `crawler` |
| **Service Package** | `middleware/src/services/crawler/` |
| **Frontend View** | `frontend/src/tabs/web/ImageCrawlerTab.tsx` |
| **Contract Schema** | `contracts/schemas/capability/crawler.json` |
| **Contract SHA-256** | `b1efd5bfdec7392cdc787396712e715234f41cb19c5e3b706b5d4bf9b02e5827` |

## Overview

The Web Crawler capability provides automated image board scraping (Danbooru, Gelbooru, Sankaku, Safebooru) and configurable general web scraping with action sequences (B-01 / #906). Crawlers write downloaded media directly into caller-specified destination directories. The service does not access `library.db` or `cloud_jobs.db` (Gate B closed).

## Public Surface

- **Python Service (`middleware/src/services/crawler/`):**
  - Commands: `CrawlCommand`, `ListSupportedCommand`.
  - Results: `CrawlResult`, `ListSupportedResult`.
  - Protocol: `CrawlerServiceProtocol`.
  - Service: `CrawlerService`.
- **Sidecar Handlers (`middleware/src/sidecar/handlers/crawler.py`):**
  - `handle_crawl`, `handle_list_supported`.
- **Frontend Client (`frontend/src/hostclient/client.ts`):**
  - `crawlerCrawl`, `crawlerListSupported`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/crawler.json`
- **Methods:**
  - `crawler.crawl`: execute a crawler operation into a caller destination folder.
  - `crawler.list_supported`: query supported crawler types, board targets, and action templates.
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** crawler mode selector, settings inputs, action builder buttons, output directory field, and Run Crawler button are in natural tab order.
- **Screen-reader notes & known gaps:** crawl status and completion alerts use role-status containers and modal feedback. Headless browser automation and automated CAPTCHA resolution stay in PySide6 while shell migration proceeds.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_crawler_service.py middleware/test/sidecar/test_crawler_dispatch.py -q
npm run test-frontend -- src/tabs/web/ImageCrawlerTab.test.tsx
```
