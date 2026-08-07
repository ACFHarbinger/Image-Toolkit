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

    def record_attempt_review(self, request_id, directory, attempt_id, review):
        return self._execute(
            request_id,
            "record_attempt_review",
            {"directory": directory, "attempt_id": attempt_id, "review": review},
        )

    def decide_attempt_review(self, request_id, directory, attempt_id, review_id, decision):
        return self._execute(
            request_id,
            "decide_attempt_review",
            {
                "directory": directory,
                "attempt_id": attempt_id,
                "review_id": review_id,
                "decision": decision,
            },
        )

    def project_progress_snapshot(self, request_id, directory):
        return self._execute(request_id, "project_progress_snapshot", {"directory": directory})

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
