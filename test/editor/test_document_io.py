import pytest

from editor import LayerStack, load_document, save_document


def _stack_with_two_layers():
    stack = LayerStack(4, 3)
    a = stack.add_layer("layer-1", "Layer 1")
    a.pixels[0, 0] = [10, 20, 30, 255]
    a.meta.opacity = 0.5
    a.meta.blend_mode = "multiply"
    b = stack.add_layer("layer-2", "Layer 2")
    b.pixels[1, 1] = [40, 50, 60, 128]
    b.meta.visible = False
    stack.add_mask("layer-2")
    b.mask[0, 0] = 64
    return stack


def test_save_and_load_document_round_trips_layers(tmp_path):
    stack = _stack_with_two_layers()
    save_document(tmp_path, stack)
    loaded = load_document(tmp_path)

    assert loaded.width == 4
    assert loaded.height == 3
    assert [layer.meta.id for layer in loaded.layers()] == ["layer-1", "layer-2"]

    layer_1 = loaded.layer("layer-1")
    assert layer_1.meta.name == "Layer 1"
    assert layer_1.meta.opacity == 0.5
    assert layer_1.meta.blend_mode == "multiply"
    assert layer_1.pixels[0, 0].tolist() == [10, 20, 30, 255]
    assert layer_1.mask is None

    layer_2 = loaded.layer("layer-2")
    assert layer_2.meta.visible is False
    assert layer_2.pixels[1, 1].tolist() == [40, 50, 60, 128]
    assert layer_2.mask is not None
    assert layer_2.mask[0, 0] == 64
    assert layer_2.mask[1, 1] == 255


def test_save_document_creates_directory(tmp_path):
    destination = tmp_path / "nested" / "doc"
    save_document(destination, LayerStack(2, 2))
    assert destination.exists()
    assert (destination / "manifest.json").exists()


def test_save_document_clears_stale_layer_files(tmp_path):
    stack = LayerStack(2, 2)
    stack.add_layer("layer-a", "A")
    stack.add_layer("layer-b", "B")
    save_document(tmp_path, stack)
    assert (tmp_path / "layer-b.pixels.npy").exists()

    smaller = LayerStack(2, 2)
    smaller.add_layer("layer-a", "A")
    save_document(tmp_path, smaller)

    assert not (tmp_path / "layer-b.pixels.npy").exists()
    loaded = load_document(tmp_path)
    assert [layer.meta.id for layer in loaded.layers()] == ["layer-a"]


def test_load_document_rejects_missing_manifest(tmp_path):
    with pytest.raises(ValueError, match="no document manifest"):
        load_document(tmp_path)


def test_load_document_rejects_unsupported_schema_version(tmp_path):
    save_document(tmp_path, LayerStack(2, 2))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        manifest_path.read_text().replace('"schema_version": 1', '"schema_version": 99')
    )
    with pytest.raises(ValueError, match="unsupported document schema version"):
        load_document(tmp_path)


def test_save_document_first_save_creates_no_recovery_directory(tmp_path):
    save_document(tmp_path, LayerStack(2, 2))
    assert not (tmp_path / ".recovery").exists()


def test_save_document_second_save_snapshots_prior_state_into_recovery(tmp_path):
    stack = _stack_with_two_layers()
    save_document(tmp_path, stack)

    changed = LayerStack(4, 3)
    changed.add_layer("layer-only", "Only")
    save_document(tmp_path, changed)

    snapshot = tmp_path / ".recovery" / "1"
    assert snapshot.exists()
    snapshot_stack = load_document(snapshot)
    assert [layer.meta.id for layer in snapshot_stack.layers()] == ["layer-1", "layer-2"]

    current = load_document(tmp_path)
    assert [layer.meta.id for layer in current.layers()] == ["layer-only"]


def test_save_document_rotates_bounded_recovery_revisions(tmp_path):
    for index in range(4):
        stack = LayerStack(2, 2)
        stack.add_layer(f"layer-{index}", f"Layer {index}")
        save_document(tmp_path, stack, recovery_revisions=2)

    recovery = tmp_path / ".recovery"
    assert sorted(item.name for item in recovery.iterdir()) == ["1", "2"]
    # slot 1 holds the save immediately before the most recent (index 2),
    # slot 2 the one before that (index 1) -- index 0's snapshot was evicted.
    assert [layer.meta.id for layer in load_document(recovery / "1").layers()] == ["layer-2"]
    assert [layer.meta.id for layer in load_document(recovery / "2").layers()] == ["layer-1"]


def test_save_document_rejects_invalid_recovery_revisions(tmp_path):
    with pytest.raises(ValueError, match="recovery revisions"):
        save_document(tmp_path, LayerStack(2, 2), recovery_revisions=0)
    with pytest.raises(ValueError, match="recovery revisions"):
        save_document(tmp_path, LayerStack(2, 2), recovery_revisions=101)
