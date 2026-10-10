"""PromptEdit — the shared prompt editor for DL Train/Generate forms (#733).

Replaces the bare QLineEdit prompt/negative/trigger fields with one
component: tag autocomplete backed by the app's own vocabulary, trigger /
prefix chips, and a per-encoder SDXL token meter (75-token boundary —
warn, never silently truncate).

Drop-in for the QLineEdit fields it replaces: text()/setText() keep
existing collect()/set_config() call sites working; BaseGenerativeTab
collects PromptEdit duck-typed via to_prompt_text()/set_prompt_text().
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.src.components.prompt_vocabulary import NullVocabulary, TagSuggestion, VocabularyProvider
from gui.src.components.tag_chip_widget import TagChipGroup
from gui.src.theming.theme_api import color

logger = logging.getLogger(__name__)

_EDITOR_HEIGHT = 58
_DEBOUNCE_MS = 200
_MIN_TOKEN_PREFIX = 2
_POPUP_MAX_ROWS = 6


class _JobSignals(QObject):
    """Deliver QRunnable results back to the GUI thread."""

    suggestions = Signal(int, str, object)  # job_id, token, list | Exception
    counts = Signal(int, str, object)  # job_id, text, (enc1, enc2) | Exception


class _SuggestJob(QRunnable):
    def __init__(self, job_id: int, token: str, vocabulary: VocabularyProvider):
        super().__init__()
        self._job_id = job_id
        self._token = token
        self._vocabulary = vocabulary
        self.signals = _JobSignals()

    def run(self) -> None:
        try:
            result = self._vocabulary.suggest(self._token)
        except Exception as exc:  # provider failure must never kill the pool
            result = exc
        self.signals.suggestions.emit(self._job_id, self._token, result)


class _CountJob(QRunnable):
    def __init__(self, job_id: int, text: str, counter: "SdxlTokenCounter", model_id: str):
        super().__init__()
        self._job_id = job_id
        self._text = text
        self._counter = counter
        self._model_id = model_id
        self.signals = _JobSignals()

    def run(self) -> None:
        try:
            result = self._counter.counts(self._model_id, self._text)
        except Exception as exc:
            result = exc
        self.signals.counts.emit(self._job_id, self._text, result)


class SdxlTokenCounter:
    """Per-encoder CLIP token counts for the SDXL prompt pair.

    Loads CLIPTokenizer for the ``tokenizer`` / ``tokenizer_2`` subfolders
    of the selected base model, caching successes *and* failures per model
    id so an offline machine never re-attempts network loads. Unavailable
    models report (None, None) — the meter shows "—", never a fake zero.
    """

    TOKEN_LIMIT = 75  # per-chunk tokens; encoders pad to 77 with bos/eos

    def __init__(self) -> None:
        self._cache: dict[str, tuple[object, object] | None] = {}

    def counts(self, model_id: str, text: str) -> tuple[int | None, int | None]:
        if not model_id:
            return (None, None)
        pair = self._tokenizers(model_id)
        if pair is None:
            return (None, None)
        enc1, enc2 = pair
        first = len(enc1(text).input_ids) - 2  # drop bos/eos
        second = len(enc2(text).input_ids) - 2
        return (first, second)

    def _tokenizers(self, model_id: str) -> tuple[object, object] | None:
        if model_id not in self._cache:
            try:
                from transformers import CLIPTokenizer

                one = CLIPTokenizer.from_pretrained(model_id, subfolder="tokenizer")
                two = CLIPTokenizer.from_pretrained(model_id, subfolder="tokenizer_2")
                self._cache[model_id] = (one, two)
            except Exception as exc:
                logger.info("SDXL tokenizers unavailable for %s: %s", model_id, exc)
                self._cache[model_id] = None
        return self._cache[model_id]


class PromptEdit(QWidget):
    """Prompt/negative/trigger editor with autocomplete, chips, token meter.

    Signals
    -------
    promptChanged(str)
        Full prompt text changed. Use this for new wiring — the inner
        QPlainTextEdit's 0-arg textChanged is a different signature from
        QLineEdit's and must not be re-connected blindly (see #764).
    """

    promptChanged = Signal(str)

    def __init__(
        self,
        text: str = "",
        *,
        placeholder: str = "",
        vocabulary: VocabularyProvider | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(placeholder)
        self.editor.setFixedHeight(_EDITOR_HEIGHT)
        self.editor.installEventFilter(self)
        if text:
            self.editor.setPlainText(text)
            self._move_cursor_end()

        self._chips = TagChipGroup()
        self._chips.setVisible(False)
        self._chips.tag_clicked.connect(self.insert_tag)

        self._meter = QLabel("—")
        self._meter.setObjectName("prompt_token_meter")
        self._meter.setStyleSheet(f"color: {color('muted_text')};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.editor)
        layout.addWidget(self._chips)
        layout.addWidget(self._meter)

        self._vocabulary: VocabularyProvider = vocabulary or NullVocabulary()
        self._counter: SdxlTokenCounter | None = None
        self._model_id = ""
        self._job_seq = 0
        self._count_seq = 0

        self._popup = _CompletionPopup(self)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._request_suggestions)

        self._meter_timer = QTimer(self)
        self._meter_timer.setSingleShot(True)
        self._meter_timer.setInterval(_DEBOUNCE_MS)
        self._meter_timer.timeout.connect(lambda: self._update_meter(self.editor.toPlainText()))

        self.editor.textChanged.connect(self._on_text_changed)

    # ------------------------------------------------------------------
    # Drop-in QLineEdit compatibility + base-class duck typing
    # ------------------------------------------------------------------

    def text(self) -> str:
        return self.editor.toPlainText()

    def setText(self, value: str) -> None:  # noqa: N802 -- mirrors QLineEdit
        self.editor.setPlainText(value)
        self._move_cursor_end()

    def to_prompt_text(self) -> str:
        return self.editor.toPlainText()

    def set_prompt_text(self, value: str) -> None:
        self.editor.setPlainText(value)
        self._move_cursor_end()

    def _move_cursor_end(self) -> None:
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_vocabulary(self, vocabulary: VocabularyProvider) -> None:
        self._vocabulary = vocabulary

    def trigger_tokens(self) -> list[str]:
        """Trigger words mined from past run records — empty until Gate D's
        run store lands (#733 vocabulary contract)."""
        try:
            return self._vocabulary.trigger_tokens()
        except Exception as exc:
            logger.info("trigger tokens unavailable: %s", exc)
            return []

    def set_chips(self, labels: list[str]) -> None:
        """Trigger/prefix chip row; empty list hides it."""
        self._chips.set_tags(labels)
        self._chips.setVisible(bool(labels))

    def set_meter_model_id(
        self, model_id: str, counter: SdxlTokenCounter | None = None
    ) -> None:
        """Track per-encoder token counts for an SDXL-family base model."""
        if counter is not None:
            self._counter = counter
        elif self._counter is None:
            self._counter = SdxlTokenCounter()
        self._model_id = model_id or ""
        self._update_meter(self.editor.toPlainText())

    # ------------------------------------------------------------------
    # Insertion API (chips + Gate E's append-to-negative patches)
    # ------------------------------------------------------------------

    def current_token(self) -> str:
        """The partial tag being typed at the cursor (after the last comma)."""
        cursor = self.editor.textCursor()
        before = self.editor.toPlainText()[: cursor.position()]
        start = max(before.rfind(","), before.rfind("\n")) + 1
        return before[start:].strip()

    def insert_tag(self, tag: str) -> None:
        """Insert a tag at the cursor, keeping comma separation on both sides."""
        text = self.editor.toPlainText()
        pos = self.editor.textCursor().position()
        before, after = text[:pos], text[pos:]
        sep_before = "" if not before.strip() or before.rstrip().endswith(",") else ", "
        tail = "" if not after.strip() or after.lstrip().startswith(",") else ", "
        inserted = sep_before + tag + tail
        self.editor.setPlainText(before + inserted + after)
        cursor = self.editor.textCursor()
        cursor.setPosition(len(before + inserted))
        self.editor.setTextCursor(cursor)

    def append_tag(self, tag: str) -> None:
        """Append at the end if not already present — Gate E's patch target."""
        existing = {t.strip().lower() for t in self.editor.toPlainText().split(",")}
        if tag.strip().lower() in existing:
            return
        text = self.editor.toPlainText().rstrip()
        sep = ", " if text else ""
        self.editor.setPlainText(text + sep + tag)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_text_changed(self) -> None:
        self.promptChanged.emit(self.editor.toPlainText())
        self._meter_timer.start()
        if len(self.current_token()) >= _MIN_TOKEN_PREFIX:
            self._debounce.start()
        else:
            self._debounce.stop()
            self._popup.hide()

    def _request_suggestions(self) -> None:
        token = self.current_token()
        if len(token) < _MIN_TOKEN_PREFIX:
            return
        self._job_seq += 1
        job = _SuggestJob(self._job_seq, token, self._vocabulary)
        job.signals.suggestions.connect(self._on_suggestions)
        QThreadPool.globalInstance().start(job)

    def _on_suggestions(self, job_id: int, token: str, result: object) -> None:
        if job_id != self._job_seq or token != self.current_token():
            return  # stale — the user kept typing
        if isinstance(result, Exception) or not result:
            self._popup.hide()
            return
        self._popup.fill(result)  # type: ignore[arg-type]
        origin = self.editor.mapToGlobal(self.editor.rect().bottomLeft())
        self._popup.move(origin)
        if not self._popup.isVisible():
            self._popup.show()

    def _accept_suggestion(self, tag: str) -> None:
        cursor = self.editor.textCursor()
        text = self.editor.toPlainText()
        before = text[: cursor.position()]
        start = max(before.rfind(","), before.rfind("\n")) + 1
        end = cursor.position()
        if text[end : end + 1] == ",":  # consume the separator we replace
            end += 1
        prefix = " " if start > 0 else ""
        cursor.setPosition(start)
        cursor.setPosition(end, cursor.MoveMode.KeepAnchor)
        cursor.insertText(f"{prefix}{tag},")
        self._popup.hide()

    def _update_meter(self, text: str) -> None:
        if self._counter is None or not self._model_id:
            self._meter.setText("—")
            self._meter.setStyleSheet(f"color: {color('muted_text')};")
            return
        self._count_seq += 1
        job = _CountJob(self._count_seq, text, self._counter, self._model_id)
        job.signals.counts.connect(self._on_counts)
        QThreadPool.globalInstance().start(job)

    def _on_counts(self, job_id: int, text: str, result: object) -> None:
        if job_id != self._count_seq or text != self.editor.toPlainText():
            return
        if isinstance(result, Exception):
            self._meter.setText("—")
            self._meter.setStyleSheet(f"color: {color('muted_text')};")
            return
        enc1, enc2 = result  # type: ignore[misc]
        if enc1 is None or enc2 is None:
            self._meter.setText("—")
            self._meter.setStyleSheet(f"color: {color('muted_text')};")
            return
        warn = enc1 > SdxlTokenCounter.TOKEN_LIMIT or enc2 > SdxlTokenCounter.TOKEN_LIMIT
        tint = color("danger") if warn else color("muted_text")
        self._meter.setText(f"CLIP-L {enc1}/75 · OpenCLIP-G {enc2}/75")
        self._meter.setStyleSheet(f"color: {tint};")

    def eventFilter(self, watched: QObject, event) -> bool:  # noqa: N802 -- Qt override
        if watched is self.editor and event.type() == QEvent.Type.KeyPress:
            if not self._popup.isVisible():
                return False
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._popup.step(1)
                return True
            if key == Qt.Key.Key_Up:
                self._popup.step(-1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Tab):
                tag = self._popup.current_tag()
                if tag:
                    self._accept_suggestion(tag)
                return True
            if key == Qt.Key.Key_Escape:
                self._popup.hide()
                return True
        return False


class _CompletionPopup(QListWidget):
    """Borderless suggestion list floating under the editor."""

    def __init__(self, host: "PromptEdit"):
        super().__init__(host)
        self._host = host
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.itemClicked.connect(self._on_click)

    def fill(self, suggestions: list[TagSuggestion]) -> None:
        self.clear()
        shown = suggestions[:_POPUP_MAX_ROWS]
        for suggestion in shown:
            suffix = f"  ·  {suggestion.category}" if suggestion.category else ""
            if suggestion.uses:
                suffix += f" ×{suggestion.uses}"
            QListWidgetItem(suggestion.tag + suffix, self)
        self.setCurrentRow(0)
        row_height = self.sizeHintForRow(0) if shown else 20
        height = min(row_height * max(1, len(shown)) + 4, 240)
        self.resize(QSize(self._host.editor.width(), height))

    def step(self, delta: int) -> None:
        row = self.currentRow() + delta
        if 0 <= row < self.count():
            self.setCurrentRow(row)

    def current_tag(self) -> str:
        item = self.currentItem()
        return self._strip_meta(item.text()) if item else ""

    @staticmethod
    def _strip_meta(text: str) -> str:
        return text.split("  ·  ")[0].strip()

    def _on_click(self, item: QListWidgetItem) -> None:
        self._host._accept_suggestion(self._strip_meta(item.text()))


__all__ = ["PromptEdit", "SdxlTokenCounter"]
