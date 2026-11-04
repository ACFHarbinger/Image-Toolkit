# Implicit state machines — Qt app + middleware (2026-11-03)

Scope: `gui/src` and `middleware/src`, excluding `legacy/`, `sidecar/`, the
frozen Tauri `frontend/`, the C++ core and mobile. Found by grepping lifecycle
booleans, status strings, mode/phase fields, `worker is None` busy checks and
existing enums, then reading each candidate. Single `_cancelled` worker flags
are omitted — one flag is not a machine.

## Already explicit (reference)

- `middleware/src/cloud/state.py` `JobState` — `ALLOWED` table,
  `check_transition()`, `IllegalTransition`. The pattern to copy.
- `extractor_tab/_player_lifecycle.py:40` `PlayerLifecycleState` and
  `windows/main/_session_recovery_state.py:27` `SessionRecoveryState` —
  converted from implicit flags (ui-arch-43); single logging setter.
- `constants/comfy.py` `ServerState`/`RunStatus`, `hie/jobs/base.py`
  `JobStatus` — enums with no transition guard
  (`models/core/comfy_manager.py:104` `_set_state` accepts anything).

## Implicit, ranked by payoff from making explicit

1. **Extractor queue run** — `gui/src/tabs/core/extractor_tab/_queue_panel.py:372`,
   `:445`. Idle / processing / awaiting-confirm encoded as
   `active_queue_worker is not None` + `_inprocess_awaiting_confirm`; the
   docstring names the three states, callers recompute them. Per-item
   `pending → processing → done/error` is a parallel `list[str]` (`:43`)
   beside `inprocess_items`.
2. **App shutdown** — `gui/src/windows/main/_lifecycle.py`. `closeEvent`
   (`:182`), tray Quit `_quit_application` (`:263`), and the
   `_close_pending` deferral (`:283`). **Likely bug:** tray Quit never calls
   `_defer_close_for_extractions`, and its docstring says `closeEvent` is
   bypassed, so quitting from the tray mid-extraction probably kills it.
3. **ComfyUI workspace controller** — `gui/src/modules/comfy_workspace_controller.py`.
   `busy` (`_worker`) × `_pending_stop` × `_closed` × `ServerState`; a stop
   while busy is queued and replayed in `_done` (`:128`). `ViewState` is dead:
   set to `NOT_CREATED` at `:56`, never changed. Generate tab's Queue button
   adds validation sub-states from `_validation_pending`,
   `_validation_unavailable`, `object_info is None`, `_issues_by_mode`
   (`gui/src/tabs/models/gen/comfy_generate_tab.py:362`, `_comfy_validation.py:70`).
4. **Wallpaper daemon / slideshow** — `wallpaper_tab/system_display_subtab/_daemon.py`.
   Config `"running"` flag × pid-file liveness × in-app `slideshow_timer`:
   stopped / starting (flag, no pid yet) / running / stale (flag, dead pid).
   Stale is reconciled only at startup (`:158`), by design.
   `_wallpaper_worker_ui_locked` is a separate lock on top.
5. **Wallpaper directory scan** — `wallpaper_common_base/_scan_pipeline.py:102`.
   `_scan_pipeline_busy`, `_pending_scan_request`, generation counter,
   `_directory_scan_state`, timer tick, watchdog. Its own `noqa` calls it a
   "bounded iterator state machine".
6. **Image crawler** — `middleware/src/web/crawlers/image_crawler.py`,
   `image_crawler_parts/_login.py:234`. Crawling / awaiting verification /
   awaiting login / blocked-login / blocked-challenge / cancelled / done
   across `_is_running`, `_access_blocked`, `_login_blocked`, `_resume_event`
   and locals `login_pending`, `notified`. `_login_blocked ⇒ _access_blocked`
   holds only by convention. Final message picked from flag combos (`:269`).
7. **Login window** — `gui/src/windows/authentication/login_window.py:229`.
   Idle / transition-pending / authenticated / failed→idle;
   `is_authenticated = True` set independently in three paths (`:339`,
   `:507`, `:626`), reversed by `auth_transition_failed`.
8. **Busy + pending coalescer, three copies** —
   `media_convert_subtab/_codec_directory_browse.py:92` and
   `_format_directory_browse.py:115` (copy-pasted);
   `gui/src/helpers/models/training_event_tail.py` (busy / dirty / stopped /
   generation). **Minor bug:** `_on_error` (`:127`) lacks `_on_read`'s
   generation check and never replays `_dirty`; after `stop()`+`start()` an
   old worker's error is reported for the new run and the new run's first
   read waits for the next file change.
9. **Extractor `_media_load_pending`** — `_video_session_config.py:268`,
   `_view_controls.py:330`. Shadows `PlayerLifecycleState.RESTORED`;
   `toggle_playback` reads the flag, not the enum. They drift:
   `extractor_tab/manager.py:284` resets the enum, not the flag.

## Fine as is

Small, locked, or genuinely concurrent: `middleware/src/bridge/cancel.py`
`CancelToken`; GIF upscale `gpu_schedule.py` condition-variable flags;
`core/gpu_lease_arbiter.py` owner/kind/estimate triple (reset together);
`supervisor/gui_gate.py` `_owns_lock`.

## Recommendation

Convert 1–3 to the `cloud/state.py` shape (enum + `ALLOWED` + one logging
setter). Write a regression test for the bugs in 2 and 8 first.
