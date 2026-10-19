"""Aspect buckets follow training.resolution (V2 pipeline ignored it, forcing ~1 MP)."""
from PIL import Image

from middleware.src.constants.models import SDXL_BUCKETS
from middleware.src.models.data.lora_dataset import BucketSample, buckets_for_resolution, closest_bucket


def test_1024_keeps_canonical_buckets():
    assert buckets_for_resolution(1024) == SDXL_BUCKETS


def test_512_buckets_are_sd15_sized_and_64_aligned():
    buckets = buckets_for_resolution(512)
    assert buckets[0] == (512, 512)
    assert all(w % 64 == 0 and h % 64 == 0 for w, h in buckets)
    assert all(abs(w * h - 512 * 512) / (512 * 512) < 0.15 for w, h in buckets)


def test_closest_bucket_prefers_the_sets_square_area():
    assert closest_bucket(1024, 1024, buckets_for_resolution(256)) == (256, 256)
    assert closest_bucket(1920, 1080, buckets_for_resolution(512))[0] > 512


def test_sample_uses_given_buckets(tmp_path):
    path = tmp_path / "img.png"
    Image.new("RGB", (1024, 1024)).save(path)
    assert BucketSample.from_path(path, buckets=buckets_for_resolution(512)).bucket == (512, 512)
    assert BucketSample.from_path(path).bucket == (1024, 1024)
