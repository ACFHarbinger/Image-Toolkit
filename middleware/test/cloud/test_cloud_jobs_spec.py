"""JobSpec validation/round-trip and the shard planners (#826)."""

from __future__ import annotations

import pytest
from middleware.src.cloud.sharding import blob_for_file, plan_comfy_batch, plan_extraction, plan_index, plan_lora
from middleware.src.cloud.spec import (
    ExecutionMode,
    InputBlob,
    JobSpec,
    Limits,
    Placement,
    ShardSpec,
    SpecError,
    WorkloadKind,
    default_mode,
)

PL = Placement("gcp", "europe-west1", ExecutionMode.MANAGED_BATCH)


def test_round_trip_preserves_everything():
    blobs = [InputBlob("a" * 64, 5, "a.mp4"), InputBlob("b" * 64, 6, "b.mp4")]
    shards, inputs = plan_extraction(blobs, 1, {"fps": 24})
    spec = JobSpec(WorkloadKind.EXTRACT, PL, shards, inputs=inputs, limits=Limits(max_spend_usd=2.0),
                   image="reg/worker@sha256:" + "0" * 64, title="t")
    assert JobSpec.from_json(spec.to_json()) == spec


@pytest.mark.parametrize("kwargs, msg", [
    ({"shards": ()}, "at least one shard"),
    ({"shards": (ShardSpec(1),)}, "indices"),
    ({"shards": (ShardSpec(0, inputs=("missing",)),)}, "unknown inputs"),
    ({"image": "reg/worker:latest"}, "digest-pinned"),
    ({"limits": Limits(max_runtime_s=0)}, "max_runtime_s"),
    ({"kind": WorkloadKind.LORA_TRAIN, "shards": (ShardSpec(0), ShardSpec(1))}, "single-shard"),
])
def test_validation_rejects(kwargs, msg):
    base = {"kind": WorkloadKind.EXTRACT, "placement": PL, "shards": (ShardSpec(0),)}
    with pytest.raises(SpecError, match=msg):
        JobSpec(**{**base, **kwargs}).validate()


def test_idempotency_key_is_stable_per_attempt():
    spec = JobSpec(WorkloadKind.EXTRACT, PL, (ShardSpec(0),), job_id="cj-1")
    assert spec.idempotency_key(1) == spec.idempotency_key(1) != spec.idempotency_key(2)


def test_planners(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello")
    blob = blob_for_file(str(f))
    shards, inputs = plan_extraction([blob, blob], 4, {})
    assert len(inputs) == 1 and shards[0].inputs == (blob.sha256,)  # duplicate files upload once

    comfy = plan_comfy_batch(["p0", "p1", "p2"], 2, base_seed=100)
    assert [len(s.params["items"]) for s in comfy] == [2, 1]
    assert comfy[1].params["items"][0]["seed"] == 102

    idx = plan_index([5, 1, 3, 3, 9], 2)
    assert [(s.params["id_min"], s.params["id_max"]) for s in idx] == [(1, 3), (5, 9)]

    lora, _ = plan_lora({"rank": 16}, [blob])
    assert len(lora) == 1


def test_default_modes_follow_the_recorded_answer():
    assert default_mode(WorkloadKind.EXTRACT) is ExecutionMode.MANAGED_BATCH
    assert default_mode(WorkloadKind.COMFY_BATCH) is ExecutionMode.INSTANCE


def test_shard_count_is_bounded():
    from middleware.src.cloud.spec import MAX_SHARDS

    spec = JobSpec(WorkloadKind.INDEX, PL, tuple(ShardSpec(i) for i in range(MAX_SHARDS + 1)))
    with pytest.raises(SpecError, match="limit"):
        spec.validate()

