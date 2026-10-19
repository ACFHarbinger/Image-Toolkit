# HIE PySide6 Tab — Chat

Date: 2026-08-12

Implementation slice for Track 04:

- Added the installable `hie_gui` package under `gui/src`.
- Added reusable `HieViewport` with pan/zoom behavior and `HieTab` with
  capability-driven assistance preview/accept controls.
- Added standalone `hie-gui` / `python3 -m hie_gui.main` launch path.
- The tab consumes the shared `ProposalPipeline` and
  `ProposalAcceptanceService`; hosts can attach `DocumentHistory` through
  `set_history()`.

Validation: GUI Python sources compile successfully with `python3 -m
compileall`. PySide6 runtime smoke testing is pending because PySide6 is not
installed in this environment. Middleware suite remains 29 passing tests.
