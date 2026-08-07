"""Bounded client for the standalone local review engine."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ENGINE_PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 5.0


class EngineClient:
    def __init__(self, command=None, timeout_seconds=DEFAULT_TIMEOUT_SECONDS):
        self.command = tuple(command) if command is not None else self._discover_command()
        if not self.command:
            raise RuntimeError("local review engine command must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("engine timeout must be positive")
        self.timeout_seconds = timeout_seconds

    def review_front_head(self, request_id, landmarks):
        return self._execute(request_id, "review_front_head", {"landmarks": landmarks})

    def review_orientation_head(self, request_id, view, landmarks):
        return self._execute(
            request_id,
            "review_orientation_head",
            {"view": view, "landmarks": landmarks},
        )

    def review_cranial_jaw_pair(self, request_id, variant_id, front_landmarks, turned_landmarks):
        return self._execute(
            request_id,
            "review_cranial_jaw_pair",
            {
                "variant_id": variant_id,
                "front_landmarks": front_landmarks,
                "turned_landmarks": turned_landmarks,
            },
        )

    def review_eye_pair(self, request_id, view, stage, landmarks):
        return self._execute(
            request_id,
            "review_eye_pair",
            {"view": view, "stage": stage, "landmarks": landmarks},
        )

    def review_feature_study(self, request_id, feature, view, landmarks):
        return self._execute(
            request_id,
            "review_feature_study",
            {"feature": feature, "view": view, "landmarks": landmarks},
        )

    def review_feature_set(self, request_id, front, turned):
        return self._execute(request_id, "review_feature_set", {"front": front, "turned": turned})

    def create_exercise_project(
        self, request_id, directory, title, attempt_id, exercise_id="anime-head-front-construction"
    ):
        return self._execute(
            request_id,
            "create_exercise_project",
            {
                "directory": directory,
                "title": title,
                "document_asset": "artwork/attempt-001.kra",
                "attempt_id": attempt_id,
                "exercise_id": exercise_id,
            },
        )

    def review_asymmetry_comparison(self, request_id, control, candidate, stage, intent):
        return self._execute(
            request_id,
            "review_asymmetry_comparison",
            {"control": control, "candidate": candidate, "stage": stage, "intent": intent},
        )

    def review_identity_comparison(self, request_id, baseline, candidate, stage, identity_card):
        return self._execute(
            request_id,
            "review_identity_comparison",
            {
                "baseline": baseline,
                "candidate": candidate,
                "stage": stage,
                "identity_card": identity_card,
            },
        )

    def review_value_masks(
        self,
        request_id,
        front_form_mask,
        front_cast_mask,
        turned_form_mask,
        turned_cast_mask,
        width,
        height,
        light_direction,
        boundary_hardness,
        third_value_mask=None,
    ):
        return self._execute(
            request_id,
            "review_value_masks",
            {
                "front_form_mask": front_form_mask,
                "front_cast_mask": front_cast_mask,
                "turned_form_mask": turned_form_mask,
                "turned_cast_mask": turned_cast_mask,
                "width": width,
                "height": height,
                "light_direction": light_direction,
                "boundary_hardness": boundary_hardness,
                "third_value_mask": third_value_mask,
            },
        )

    def record_attempt_review(self, request_id, directory, attempt_id, review):
        return self._execute(
            request_id,
            "record_attempt_review",
            {"directory": directory, "attempt_id": attempt_id, "review": review},
        )

    def decide_attempt_review(
        self, request_id, directory, attempt_id, review_id, decision, rationale=None
    ):
        return self._execute(
            request_id,
            "decide_attempt_review",
            {
                "directory": directory,
                "attempt_id": attempt_id,
                "review_id": review_id,
                "decision": decision,
                "rationale": rationale,
            },
        )

    def project_progress_snapshot(self, request_id, directory):
        return self._execute(request_id, "project_progress_snapshot", {"directory": directory})

    def attach_style_bible(self, request_id, directory, asset_path):
        return self._execute(
            request_id,
            "attach_style_bible",
            {"directory": directory, "asset_path": asset_path},
        )

    def detach_style_bible(self, request_id, directory, asset_path):
        return self._execute(
            request_id,
            "detach_style_bible",
            {"directory": directory, "asset_path": asset_path},
        )

    def upsert_project_style_bible(self, request_id, directory, style_bible):
        return self._execute(
            request_id,
            "upsert_project_style_bible",
            {"directory": directory, "style_bible": style_bible},
        )

    def import_reference_asset(self, request_id, directory, source_path):
        return self._execute(
            request_id,
            "import_reference_asset",
            {"directory": directory, "source_path": source_path},
        )

    def project_style_bible_payload(self, request_id, directory, asset_path):
        return self._execute(
            request_id,
            "project_style_bible_payload",
            {"directory": directory, "asset_path": asset_path},
        )

    def attach_correspondence_set(self, request_id, directory, asset_path):
        return self._execute(
            request_id,
            "attach_correspondence_set",
            {"directory": directory, "asset_path": asset_path},
        )

    def detach_correspondence_set(self, request_id, directory, asset_path):
        return self._execute(
            request_id,
            "detach_correspondence_set",
            {"directory": directory, "asset_path": asset_path},
        )

    def upsert_project_correspondence_set(self, request_id, directory, correspondence_set):
        return self._execute(
            request_id,
            "upsert_project_correspondence_set",
            {"directory": directory, "correspondence_set": correspondence_set},
        )

    def project_correspondence_set_payload(self, request_id, directory, asset_path):
        return self._execute(
            request_id,
            "project_correspondence_set_payload",
            {"directory": directory, "asset_path": asset_path},
        )

    def propagate_project_correspondence(
        self, request_id, directory, asset_path, source_id, target_region_ids
    ):
        return self._execute(
            request_id,
            "propagate_project_correspondence",
            {
                "directory": directory,
                "asset_path": asset_path,
                "source_id": source_id,
                "target_region_ids": target_region_ids,
            },
        )

    def revise_capstone_decision_rationale(
        self, request_id, directory, attempt_id, review_id, rationale
    ):
        return self._execute(
            request_id,
            "revise_capstone_decision_rationale",
            {
                "directory": directory,
                "attempt_id": attempt_id,
                "review_id": review_id,
                "rationale": rationale,
            },
        )

    def import_compatible_capstone_review(
        self,
        request_id,
        directory,
        target_attempt_id,
        source_attempt_id,
        source_review_id,
        decision,
        rationale,
    ):
        return self._execute(
            request_id,
            "import_compatible_capstone_review",
            {
                "directory": directory,
                "target_attempt_id": target_attempt_id,
                "source_attempt_id": source_attempt_id,
                "source_review_id": source_review_id,
                "decision": decision,
                "rationale": rationale,
            },
        )

    def configure_capstone_policy(self, request_id, directory, retain_rationale_history):
        return self._execute(
            request_id,
            "configure_capstone_policy",
            {
                "directory": directory,
                "retain_rationale_history": retain_rationale_history,
            },
        )

    def configure_progress_retention(self, request_id, directory, enabled, clear_existing=False):
        return self._execute(
            request_id,
            "configure_progress_retention",
            {
                "directory": directory,
                "enabled": enabled,
                "clear_existing": clear_existing,
            },
        )

    def configure_study_consent(self, request_id, directory, opted_in, clear_existing=False):
        return self._execute(
            request_id,
            "configure_study_consent",
            {
                "directory": directory,
                "opted_in": opted_in,
                "clear_existing": clear_existing,
            },
        )

    def record_study_session(
        self,
        request_id,
        directory,
        baseline_attempt_id,
        remedial_exercise_id=None,
        redraw_attempt_id=None,
        explanation_rating=None,
        completed=False,
    ):
        return self._execute(
            request_id,
            "record_study_session",
            {
                "directory": directory,
                "baseline_attempt_id": baseline_attempt_id,
                "remedial_exercise_id": remedial_exercise_id,
                "redraw_attempt_id": redraw_attempt_id,
                "explanation_rating": explanation_rating,
                "completed": completed,
            },
        )

    def record_advice_feedback(
        self, request_id, directory, attempt_id, review_id, rating, note=None
    ):
        return self._execute(
            request_id,
            "record_advice_feedback",
            {
                "directory": directory,
                "attempt_id": attempt_id,
                "review_id": review_id,
                "rating": rating,
                "note": note,
            },
        )

    def configure_feedback_policy(
        self, request_id, directory, retain_revision_history, note_character_limit
    ):
        return self._execute(
            request_id,
            "configure_feedback_policy",
            {
                "directory": directory,
                "retain_revision_history": retain_revision_history,
                "note_character_limit": note_character_limit,
            },
        )

    def upsert_identity_card(self, request_id, directory, name, anchors):
        return self._execute(
            request_id,
            "upsert_identity_card",
            {"directory": directory, "name": name, "anchors": anchors},
        )

    def configure_identity_card_policy(self, request_id, directory, retain_revision_history):
        return self._execute(
            request_id,
            "configure_identity_card_policy",
            {
                "directory": directory,
                "retain_revision_history": retain_revision_history,
            },
        )

    def set_attempt_completion(self, request_id, directory, attempt_id, completed):
        return self._execute(
            request_id,
            "set_attempt_completion",
            {
                "directory": directory,
                "attempt_id": attempt_id,
                "completed": completed,
            },
        )

    def _execute(self, request_id, operation, payload):
        request = {
            "protocol_version": ENGINE_PROTOCOL_VERSION,
            "request_id": request_id,
            "operation": operation,
            "payload": payload,
        }
        encoded = json.dumps(request, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_MESSAGE_BYTES:
            raise ValueError("engine request exceeds 1 MiB")
        try:
            completed = subprocess.run(
                self.command,
                input=encoded,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("local review engine timed out") from error
        except OSError as error:
            raise RuntimeError("local review engine could not be started") from error
        if len(completed.stdout) > MAX_MESSAGE_BYTES:
            raise RuntimeError("local review engine response exceeds 1 MiB")
        try:
            response = json.loads(completed.stdout)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise RuntimeError("local review engine returned invalid JSON") from error
        if not isinstance(response, dict):
            raise RuntimeError("local review engine response root is not an object")
        if response.get("protocol_version") != ENGINE_PROTOCOL_VERSION:
            raise RuntimeError("local review engine protocol mismatch")
        if response.get("request_id") != request_id:
            raise RuntimeError("local review engine response does not match the request")
        if not response.get("ok"):
            detail = response.get("error", {}).get("message", "review failed")
            raise RuntimeError(f"local review engine rejected the request: {detail}")
        if completed.returncode != 0 or not isinstance(response.get("result"), dict):
            raise RuntimeError("local review engine returned an incomplete result")
        return response["result"]

    @staticmethod
    def _discover_command():
        configured = os.environ.get("CEL_SHADED_GENERATOR_ENGINE")
        if configured:
            return (configured,)
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        config_path = config_home / "cel-shaded-generator" / "krita.json"
        if config_path.is_file():
            try:
                payload = json.loads(config_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                raise RuntimeError("local review engine configuration is invalid") from error
            if not isinstance(payload, dict):
                raise RuntimeError("local review engine configuration is unsupported")
            executable = payload.get("engine_executable")
            if payload.get("schema_version") != 1 or not isinstance(executable, str):
                raise RuntimeError("local review engine configuration is unsupported")
            if not Path(executable).is_file() or not os.access(executable, os.X_OK):
                raise RuntimeError("configured local review engine is not executable")
            return (executable,)
        executable = shutil.which("cel-shaded-generator-engine")
        if executable:
            return (executable,)
        raise RuntimeError(
            "local review engine was not found; configure CEL_SHADED_GENERATOR_ENGINE"
        )
