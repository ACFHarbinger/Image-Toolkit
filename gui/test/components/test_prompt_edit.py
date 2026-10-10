"""#733: PromptEdit — shared prompt editor (autocomplete, chips, SDXL meter)
and its vocabulary providers."""

import json

import pytest
from gui.src.classes.base.base_generative_tab import BaseGenerativeTab
from gui.src.components.prompt_edit import PromptEdit, SdxlTokenCounter
from gui.src.components.prompt_vocabulary import (
    CompositeVocabulary,
    DbVocabulary,
    RunRecordStore,
    StaticVocabulary,
    TagSuggestion,
    Wd14FallbackVocabulary,
)
from PySide6.QtWidgets import QFormLayout

pytestmark = pytest.mark.gui


def _wait_until(condition, timeout_ms: int = 3000) -> None:
    """pytest-qt is not a project dependency — poll the event loop instead."""
    from PySide6.QtCore import QCoreApplication, QElapsedTimer, QThread

    timer = QElapsedTimer()
    timer.start()
    while not condition():
        if timer.elapsed() > timeout_ms:
            raise AssertionError("condition not met within timeout")
        QCoreApplication.processEvents()
        QThread.msleep(20)


# ---------------------------------------------------------------------------
# Vocabulary providers
# ---------------------------------------------------------------------------


def test_static_vocabulary_prefix_match():
    vocab = StaticVocabulary(("1girl", "1boy", "cat ears"))
    assert [s.tag for s in vocab.suggest("1g")] == ["1girl"]
    assert [s.tag for s in vocab.suggest("cat")] == ["cat ears"]
    assert vocab.suggest("zzz") == []


def test_composite_vocabulary_dedupes_and_orders():
    first = StaticVocabulary(("cat ears", "cat tail"))
    second = StaticVocabulary(("cat ears", "catalog"))
    composite = CompositeVocabulary([first, second])
    assert [s.tag for s in composite.suggest("cat", limit=10)] == [
        "cat ears",
        "cat tail",
        "catalog",
    ]


def test_db_vocabulary_ranks_by_usage():
    rows = [
        ("1girl", "general", 500),
        ("1boy", "general", 3),
        ("1other", "general", 40),
    ]
    vocab = DbVocabulary(rows_factory=lambda: rows)
    assert [s.tag for s in vocab.suggest("1", limit=10)] == ["1girl", "1other", "1boy"]
    assert vocab.suggest("zzz") == []


def test_db_vocabulary_failure_is_empty():
    vocab = DbVocabulary(rows_factory=RuntimeError("db down"))
    assert vocab.suggest("1g") == []


def test_wd14_fallback_uses_csv_rows(monkeypatch):
    vocab = Wd14FallbackVocabulary()
    monkeypatch.setattr(
        vocab,
        "_load",
        lambda: [TagSuggestion("1girl", "0"), TagSuggestion("absurdres", "3")],
    )
    assert [s.tag for s in vocab.suggest("abs")] == ["absurdres"]


def test_run_record_store_reads_trigger_tokens(tmp_path):
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    run_a.mkdir()
    run_b.mkdir()
    (run_a / "record.json").write_text(
        json.dumps({"trigger_word": "my_char", "lora_path": "out/my_char.safetensors"}),
        encoding="utf-8",
    )
    (run_b / "record.json").write_text(
        json.dumps({"trigger_word": "my_char"}),  # duplicate is dropped
        encoding="utf-8",
    )
    (tmp_path / "run-c").mkdir()
    (tmp_path / "run-c" / "record.json").write_text("{broken", encoding="utf-8")

    store = RunRecordStore((str(tmp_path),))
    assert store.trigger_tokens() == ["my_char"]


def test_run_record_store_negative_for_lora(tmp_path):
    run = tmp_path / "run-a"
    run.mkdir()
    (run / "record.json").write_text(
        json.dumps(
            {
                "trigger_word": "my_char",
                "lora_path": "outputs/my_char.safetensors",
                "negative_prompt": "lowres, bad hands",
            }
        ),
        encoding="utf-8",
    )
    store = RunRecordStore((str(tmp_path),))
    assert store.negative_for_lora("my_char.safetensors") == "lowres, bad hands"
    assert store.negative_for_lora("outputs/my_char.safetensors") == "lowres, bad hands"
    assert store.negative_for_lora("unrelated.safetensors") is None
    assert RunRecordStore().negative_for_lora("anything") is None


# ---------------------------------------------------------------------------
# PromptEdit — editor behavior
# ---------------------------------------------------------------------------


@pytest.fixture
def edit(q_app):
    return PromptEdit(vocabulary=StaticVocabulary(("cat_ears", "cat_tail")))


def test_text_aliases_roundtrip(edit):
    edit.setText("1girl, solo")
    assert edit.text() == "1girl, solo"
    assert edit.to_prompt_text() == "1girl, solo"
    edit.set_prompt_text("1boy")
    assert edit.text() == "1boy"


def test_prompt_changed_signal(edit):
    seen: list[str] = []
    edit.promptChanged.connect(seen.append)
    edit.setText("1girl")
    assert seen == ["1girl"]


def test_current_token_after_comma(edit):
    edit.setText("masterpiece, best quality, 1g")
    cursor = edit.editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    edit.editor.setTextCursor(cursor)
    assert edit.current_token() == "1g"


def test_insert_tag_keeps_comma_separation(edit):
    edit.setText("1girl")
    edit.insert_tag("cat_ears")
    assert edit.text() == "1girl, cat_ears"

    edit.setText("")
    edit.insert_tag("cat_ears")
    assert edit.text() == "cat_ears"

    edit.setText("1girl,")
    edit.insert_tag("cat_ears")
    assert edit.text() == "1girl,cat_ears"


def test_append_tag_dedupes(edit):
    edit.setText("lowres, bad anatomy")
    edit.append_tag("bad anatomy")
    assert edit.text() == "lowres, bad anatomy"
    edit.append_tag("text")
    assert edit.text() == "lowres, bad anatomy, text"


def test_chips_row_shows_and_inserts(edit):
    edit.set_chips(["masterpiece, best quality", "my_char"])
    assert edit._chips.isVisibleTo(edit)
    edit._chips.tag_clicked.emit("my_char")
    assert "my_char" in edit.text()
    edit.set_chips([])
    assert not edit._chips.isVisibleTo(edit)


# ---------------------------------------------------------------------------
# PromptEdit — autocomplete (bypassing the thread pool)
# ---------------------------------------------------------------------------


def test_suggestions_fill_popup_and_accept_replaces_token(edit):
    edit.setText("1g")
    edit._on_suggestions(0, "1g", [TagSuggestion("cat_ears", "general", 7)])
    assert edit._popup.isVisible()
    assert edit._popup.count() == 1
    assert "cat_ears" in edit._popup.item(0).text()
    assert "×7" in edit._popup.item(0).text()

    edit._accept_suggestion("cat_ears")
    assert edit.text() == "cat_ears,"
    assert not edit._popup.isVisible()


def test_accept_mid_prompt_preserves_surrounding_text(edit):
    edit.setText("1girl, 1g, solo")
    cursor = edit.editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    # place cursor right after "1g"
    cursor.setPosition(len("1girl, 1g"))
    edit.editor.setTextCursor(cursor)
    edit._accept_suggestion("cat_ears")
    assert edit.text() == "1girl, cat_ears, solo"


def test_stale_suggestions_are_dropped(edit):
    edit.setText("1g")
    edit._job_seq = 5  # a newer job already superseded this one
    edit._on_suggestions(4, "1g", [TagSuggestion("cat_ears")])
    assert not edit._popup.isVisible()


def test_suggestion_end_to_end_through_pool(edit):
    edit.setText("ca")
    edit._request_suggestions()
    _wait_until(lambda: edit._popup.isVisible())
    assert edit._popup.count() == 2  # cat_ears + cat_tail


# ---------------------------------------------------------------------------
# PromptEdit — token meter (fake counter; never touches the network)
# ---------------------------------------------------------------------------


class _FakeCounter:
    def counts(self, model_id, text):
        if not model_id:
            return (None, None)
        words = [w for w in text.split(",") if w.strip()]
        return (len(words), 90 if "long" in text else len(words))


def test_meter_shows_counts_and_warns_past_limit(edit):
    edit.set_meter_model_id("some/model", counter=_FakeCounter())
    edit.setText("1girl, solo")
    edit._update_meter(edit.text())
    _wait_until(lambda: "CLIP-L 2/75" in edit._meter.text())
    edit.setText("long prompt here")
    edit._update_meter(edit.text())
    _wait_until(lambda: "OpenCLIP-G 90/75" in edit._meter.text())


def test_meter_unavailable_shows_dash(edit):
    edit.set_meter_model_id("", counter=_FakeCounter())
    edit._update_meter("1girl")
    assert edit._meter.text() == "—"


def test_sdxl_token_counter_caches_failures():
    counter = SdxlTokenCounter()
    assert counter.counts("", "x") == (None, None)
    # Nonexistent model id: failure is cached, no exception escapes.
    result = counter.counts("definitely/not-a-real-model-733", "x")
    assert result == (None, None)
    assert counter._cache["definitely/not-a-real-model-733"] is None


# ---------------------------------------------------------------------------
# BaseGenerativeTab collect/set_config compat
# ---------------------------------------------------------------------------


def test_base_collect_and_restore_roundtrip_prompt_edit(q_app):
    tab = BaseGenerativeTab()
    layout = QFormLayout()
    tab.setLayout(layout)
    prompt = PromptEdit()
    tab.add_param_widget(layout, "Prompt:", prompt, "prompt")

    prompt.setText("1girl, cat ears")
    params = tab.collect()
    assert params["prompt"] == "1girl, cat ears"

    prompt.setText("")
    tab.set_config({"prompt": "1boy, solo"})
    assert prompt.text() == "1boy, solo"


def test_lora_generate_tab_swapped_fields_collect(q_app):
    from gui.src.tabs.models.gen.lora_generate_tab import LoRAGenerateTab

    tab = LoRAGenerateTab()
    data = tab.collect()
    assert "1girl, solo, cat ears, library" in data["prompt"]
    assert "lowres" in data["neg_prompt"]
    tab.set_config({"prompt": "1boy", "neg_prompt": "worst quality"})
    assert tab.prompt_edit.text() == "1boy"
    assert tab.neg_prompt_edit.text() == "worst quality"
