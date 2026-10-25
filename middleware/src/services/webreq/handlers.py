"""Command handlers for the WebRequests service (B-02 / #907).

Executes single requests and sequential pipelines through native C++ bindings
(WebRequestsLogic) and standard library networking. Gate B compliant: no DB access.
"""

from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from middleware.src.services.base import CommandValidationError, Handler
from middleware.src.services.webreq.commands import (
    ActionItem,
    ExecuteCommand,
    ExecuteResult,
    RequestItem,
    SequenceCommand,
    SequenceItemResult,
    SequenceResult,
)


def _sanitize_url(url: str) -> str:
    """Validate and ensure scheme for HTTP URLs."""
    trimmed = url.strip()
    if not trimmed:
        raise CommandValidationError("URL must not be empty", field="url")
    if not (trimmed.startswith("http://") or trimmed.startswith("https://")):
        trimmed = f"https://{trimmed}"
    parsed = urllib.parse.urlparse(trimmed)
    if not parsed.netloc:
        raise CommandValidationError(f"Invalid network location in URL: {url!r}", field="url")
    return trimmed


class ExecuteHandler(Handler[ExecuteCommand, ExecuteResult]):
    """Handler executing an isolated HTTP request."""

    def handle(self, command: ExecuteCommand) -> ExecuteResult:
        clean_url = _sanitize_url(command.url)
        method = command.method.upper()
        headers = dict(command.headers or {})
        timeout = max(1, min(command.timeout_seconds, 300))

        data: bytes | None = None
        if command.body and method in {"POST", "PUT", "PATCH"}:
            data = command.body.encode("utf-8")
            if "Content-Type" not in headers and "content-type" not in headers:
                headers["Content-Type"] = "application/json" if command.body.strip().startswith(("{", "[")) else "application/x-www-form-urlencoded"

        if "User-Agent" not in headers and "user-agent" not in headers:
            headers["User-Agent"] = "ImageToolkit/1.0.0 (WebRequests)"

        req = urllib.request.Request(clean_url, data=data, headers=headers, method=method)
        start_time = time.perf_counter()

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                status_code = response.getcode() or 200
                status_text = response.msg or "OK"
                resp_headers = {k: v for k, v in response.headers.items()}
                content_type = response.headers.get("Content-Type", "application/octet-stream")
                raw_bytes = response.read(65536)  # limit preview read to 64KB
                try:
                    body_text = raw_bytes.decode("utf-8", errors="replace")
                except Exception:
                    body_text = f"<binary data: {len(raw_bytes)} bytes>"

                return ExecuteResult(
                    url=clean_url,
                    status_code=status_code,
                    status_text=status_text,
                    headers=resp_headers,
                    content_type=content_type,
                    body=body_text,
                    duration_ms=round(duration_ms, 2),
                    error=None,
                )
        except urllib.error.HTTPError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            resp_headers = {k: v for k, v in exc.headers.items()} if exc.headers else {}
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
            try:
                err_body = exc.read(65536).decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            return ExecuteResult(
                url=clean_url,
                status_code=exc.code,
                status_text=exc.reason or "HTTP Error",
                headers=resp_headers,
                content_type=content_type,
                body=err_body,
                duration_ms=round(duration_ms, 2),
                error=f"HTTP {exc.code}: {exc.reason}",
            )
        except urllib.error.URLError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecuteResult(
                url=clean_url,
                status_code=0,
                status_text="Connection Error",
                headers={},
                content_type="",
                body="",
                duration_ms=round(duration_ms, 2),
                error=str(exc.reason),
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecuteResult(
                url=clean_url,
                status_code=0,
                status_text="Execution Error",
                headers={},
                content_type="",
                body="",
                duration_ms=round(duration_ms, 2),
                error=str(exc),
            )


class SequenceHandler(Handler[SequenceCommand, SequenceResult]):
    """Handler executing sequential requests with response actions."""

    def __init__(self, logic_cls: Any | None = None) -> None:
        self._logic_cls = logic_cls

    def handle(self, command: SequenceCommand) -> SequenceResult:
        base_url = _sanitize_url(command.base_url)
        requests = command.requests or [RequestItem(type="GET", param="")]
        actions = command.actions or []
        timeout = max(1, min(command.timeout_seconds, 300))

        # Build config dict expected by WebRequestsLogic / C++ bindings
        config = {
            "base_url": base_url,
            "requests": [{"type": r.type, "param": r.param} for r in requests],
            "actions": [{"type": a.type, "param": a.param} for a in actions],
            "timeout": timeout,
        }

        logs: list[str] = []
        item_results: list[SequenceItemResult] = []

        if self._logic_cls == "fallback":
            return self._fallback_sequence_execution(base_url, requests, actions, timeout)

        # Attempt execution through WebRequestsLogic if available
        logic = None
        if self._logic_cls is not None:
            logic = self._logic_cls(config)
        else:
            try:
                from middleware.src.web.clients.web_requests import WebRequestsLogic
                logic = WebRequestsLogic(config)
            except Exception as e:
                logs.append(f"[INIT] WebRequestsLogic fallback active: {e}")

        if logic is not None:
            logic.on_status.subscribe(lambda msg: logs.append(msg))
            logic.on_error.subscribe(lambda msg: logs.append(f"[ERROR] {msg}"))
            final_status: list[str] = []
            logic.on_finished.subscribe(lambda msg: final_status.append(msg))

            try:
                logic.run()
            except Exception as exc:
                logs.append(f"[CRITICAL] Sequence execution failed: {exc}")
                final_status.append(str(exc))

            # Parse logs to construct SequenceItemResult entries
            status_pattern = re.compile(r"Request complete\. Status: (\d+)")
            error_pattern = re.compile(r"Request failed: (.*)")
            save_pattern = re.compile(r"Response content saved to (.*)")

            for i, req in enumerate(requests):
                # Construct resolved URL
                sub_path = req.param.strip()
                if req.type == "GET" and sub_path:
                    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", sub_path.lstrip("/"))
                else:
                    url = base_url

                # Find status in logs
                item_code = 200
                item_err = None
                item_save = None
                for line in logs:
                    if f"Request {i + 1}/" in line:
                        pass
                    sm = status_pattern.search(line)
                    if sm:
                        item_code = int(sm.group(1))
                    em = error_pattern.search(line)
                    if em:
                        item_err = em.group(1)
                        if item_code == 200:
                            item_code = 0
                    sp = save_pattern.search(line)
                    if sp:
                        item_save = sp.group(1).strip()

                item_results.append(
                    SequenceItemResult(
                        index=i,
                        url=url,
                        method=req.type,
                        status_code=item_code,
                        saved_path=item_save,
                        error=item_err,
                    )
                )

            summary = final_status[0] if final_status else "Sequence execution completed."
            status: str = "completed"
            if any(item.error for item in item_results):
                status = "failed" if all(item.error for item in item_results) else "completed"

            return SequenceResult(
                status="completed" if status == "completed" else "failed",
                base_url=base_url,
                total_requests=len(requests),
                completed_requests=len(item_results),
                logs=logs,
                items=item_results,
                message=summary,
            )

        # Pure Python fallback when logic object cannot be loaded
        return self._fallback_sequence_execution(base_url, requests, actions, timeout)

    def _fallback_sequence_execution(
        self,
        base_url: str,
        requests: list[RequestItem],
        actions: list[ActionItem],
        timeout: int,
    ) -> SequenceResult:
        logs: list[str] = [f"Starting fallback request sequence for {base_url}"]
        item_results: list[SequenceItemResult] = []

        exec_handler = ExecuteHandler()

        for idx, req in enumerate(requests):
            sub_path = req.param.strip()
            if req.type == "GET" and sub_path:
                url = urllib.parse.urljoin(base_url.rstrip("/") + "/", sub_path.lstrip("/"))
                body = ""
            else:
                url = base_url
                body = req.param if req.type in {"POST", "PUT", "PATCH"} else ""

            logs.append(f"--- Request {idx + 1}/{len(requests)}: [{req.type}] ---")
            logs.append(f"Executing {req.type}: {url}")

            exec_res = exec_handler.handle(
                ExecuteCommand(
                    url=url,
                    method=req.type,
                    headers=req.headers,
                    body=body,
                    timeout_seconds=timeout,
                )
            )

            saved_path: str | None = None
            if exec_res.error:
                logs.append(f"[ERROR] Request failed: {exec_res.error}")
            else:
                logs.append(f"Request complete. Status: {exec_res.status_code}")

                # Process actions
                for action in actions:
                    atype = action.type
                    aparam = action.param.strip()
                    if atype == "Print Response URL":
                        logs.append(f"  > Action: Response URL: {exec_res.url}")
                    elif atype == "Print Response Status Code":
                        logs.append(f"  > Action: Status Code: {exec_res.status_code}")
                    elif atype == "Print Response Headers":
                        hdrs = "\n    ".join(f"{k}: {v}" for k, v in exec_res.headers.items())
                        logs.append(f"  > Action: Response Headers:\n    {hdrs}")
                    elif atype == "Print Response Content (Text)":
                        preview = exec_res.body[:500] if len(exec_res.body) > 500 else exec_res.body
                        logs.append(f"  > Action: Response Content:\n{preview}")
                    elif atype == "Save Response Content (Binary)":
                        if not aparam:
                            logs.append("  > Action: Save failed. No file path provided in parameter.")
                        else:
                            try:
                                target_path = aparam
                                if os.path.isdir(target_path):
                                    fname = os.path.basename(urllib.parse.urlparse(url).path) or f"response_{idx + 1}.dat"
                                    target_path = os.path.join(target_path, fname)
                                os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
                                with open(target_path, "wb") as f:
                                    f.write(exec_res.body.encode("utf-8", errors="replace"))
                                saved_path = target_path
                                logs.append(f"  > Action: Response content saved to {target_path}")
                            except Exception as save_err:
                                logs.append(f"  > Action: Save failed: {save_err}")

            item_results.append(
                SequenceItemResult(
                    index=idx,
                    url=url,
                    method=req.type,
                    status_code=exec_res.status_code,
                    saved_path=saved_path,
                    error=exec_res.error,
                )
            )

        logs.append("--- All requests finished. ---")
        return SequenceResult(
            status="completed" if not any(it.error for it in item_results) else "failed",
            base_url=base_url,
            total_requests=len(requests),
            completed_requests=len(item_results),
            logs=logs,
            items=item_results,
            message="All requests finished.",
        )
