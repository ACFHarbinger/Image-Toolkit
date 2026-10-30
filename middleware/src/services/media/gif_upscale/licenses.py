"""License records for the GIF upscale catalogue (#1127).

Records do not gate ``available()``. Harbinger's 2026-10-30 decision bundles every
backend for private use. APISR's academic-only disclaimer and the AGPL/GPL encoders
make a public release need a fresh license check.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LicenseRecord:
    algorithm_id: str
    spdx: str
    source: str
    redistribution: str
    note: str


def shipping_allowed(_record: LicenseRecord) -> bool:
    """Private-tool decision: the license is recorded and never blocks a backend."""
    return True


LICENSES: dict[str, LicenseRecord] = {
    record.algorithm_id: record
    for record in (
        LicenseRecord(
            "realesrgan",
            "BSD-3-Clause",
            "https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE",
            "ok",
            "Code and published weights. In-repo RRDBNet is the plain-torch port in ESRGANWrapper.",
        ),
        LicenseRecord(
            "real-cugan",
            "MIT",
            "https://github.com/bilibili/ailab/blob/main/Real-CUGAN/LICENSE",
            "ok",
            "LICENSE file read 2026-10-30: MIT, copyright 2022 bilibili.",
        ),
        LicenseRecord(
            "waifu2x",
            "MIT",
            "https://github.com/nagadomi/waifu2x/blob/master/LICENSE",
            "ok",
            "Upstream project license is MIT.",
        ),
        LicenseRecord(
            "apisr",
            "GPL-3.0-only",
            "https://github.com/Kiteretsu77/APISR/blob/main/README.md",
            "private-use",
            "README license section is GPL-3.0. The same README says academic use only.",
        ),
        LicenseRecord(
            "anime4k",
            "MIT",
            "https://github.com/bloc97/Anime4K",
            "ok",
            "GitHub repository license is MIT. This tree ports the published shader math.",
        ),
        LicenseRecord(
            "animesr",
            "Apache-2.0",
            "https://github.com/TencentARC/AnimeSR/blob/main/LICENSE",
            "ok",
            "LICENSE header read 2026-10-30: Apache-2.0, with listed third-party Apache components.",
        ),
        LicenseRecord(
            "seedvr2",
            "Apache-2.0",
            "https://github.com/ByteDance-Seed/SeedVR",
            "ok",
            "Repository README states Apache-2.0. Weights are large; the registry greys the backend out until they are cached.",
        ),
        LicenseRecord(
            "flashvsr",
            "Apache-2.0",
            "https://github.com/OpenImagingLab/FlashVSR",
            "ok",
            "GitHub repository license is Apache-2.0. Block-sparse attention is an optional build, not a license gate.",
        ),
        LicenseRecord(
            "dove",
            "Apache-2.0",
            "https://github.com/zhengchen1999/DOVE",
            "ok",
            "GitHub repository license is Apache-2.0.",
        ),
        LicenseRecord(
            "gifski",
            "AGPL-3.0-only",
            "https://github.com/ImageOptim/gifski",
            "private-use",
            "Optional external binary. Bundling it in a public build needs a new license check.",
        ),
        LicenseRecord(
            "libimagequant",
            "GPL-3.0-or-later",
            "https://github.com/ImageOptim/libimagequant/blob/main/COPYRIGHT",
            "private-use",
            "COPYRIGHT read 2026-10-30: Kornel Lesiński's changes are GPL-3.0-or-later. A separate commercial license exists outside that file.",
        ),
        LicenseRecord(
            "classical",
            "MIT",
            "middleware/src/services/media/gif_upscale/classical",
            "ok",
            "Local implementations of published resampling and pixel-art scalers. No weights.",
        ),
    )
}
