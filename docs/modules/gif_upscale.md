# GIF upscaling licenses and weights

Sampler GIF resize goes through `middleware/src/services/media/gif_upscale/`. The registry records a license for each backend and does not block on it. This tree is a private tool (Harbinger, 2026-10-30). A public release needs another license check before shipping APISR or the AGPL/GPL encoders.

Weights use the device setting `gif_upscale.weights_policy`:

| Value | Behavior |
|---|---|
| `on_demand` | Default. Download a weight when that backend runs, then keep it in the user cache. |
| `prefetch_all` | Download every registered weight up front. |
| `offline` | Use only files already in the cache. Never open a network connection. |

Every download is checked against the registry SHA-256. The cache is `~/.cache/image-toolkit/gif-upscale/` (override with `IMAGE_TOOLKIT_GIF_UPSCALE_CACHE`). Weight files are not committed.

| Backend | SPDX | Redistribution | Source checked 2026-10-30 |
|---|---|---|---|
| Real-ESRGAN | BSD-3-Clause | ok | xinntao/Real-ESRGAN `LICENSE` |
| Real-CUGAN | MIT | ok | bilibili/ailab `Real-CUGAN/LICENSE` |
| waifu2x | MIT | ok | nagadomi/waifu2x `LICENSE` |
| APISR | GPL-3.0-only | private-use | README: GPL-3.0 and academic use only |
| Anime4K | MIT | ok | bloc97/Anime4K repository license |
| AnimeSR | Apache-2.0 | ok | TencentARC/AnimeSR `LICENSE` header |
| SeedVR2 | Apache-2.0 | ok | ByteDance-Seed/SeedVR README |
| FlashVSR | Apache-2.0 | ok | OpenImagingLab/FlashVSR repository license |
| DOVE | Apache-2.0 | ok | zhengchen1999/DOVE repository license |
| gifski | AGPL-3.0-only | private-use | ImageOptim/gifski |
| libimagequant | GPL-3.0-or-later | private-use | ImageOptim/libimagequant `COPYRIGHT` |
| Classical scalers | MIT | ok | code in this repository |

APNG, animated WebP, MP4, still-image input, video input, and batch folders are roadmap-only. See `docs/moon/roadmaps/new_features.md` §4.22.
