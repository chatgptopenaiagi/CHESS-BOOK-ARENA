# Verification report — 0.1.0

Final automated suite: **34 passed, 0 failed**. Four dependency deprecation warnings concern future Python 3.16 asyncio changes. Earlier run: 26 passed / 1 failed due to a malformed generated EPD fixture; corrected fixture, rerun and additional tests are recorded in development logs (not published because they contain machine paths).

Coverage: multi-game PGN; gzip; Polyglot; ZIP; FEN; EPD; exact fixture counts; player search/filter; four move-selection strategies; changing opponents; out-of-coverage; engine-fallback labeling with both fake and actual UCI engines; completed historical game without engine; promotion; invalid PGN/book handling; idempotence; cancellation/recovery; file changes; transpositions; castling/en passant; fifty-/seventy-five-move and material draw checks; persistent game metadata/PGN; live Qt window; real Qt mouse clicks/drag and promotion dialog; ZIP-contained book; coverage-ended GUI notification; engine analysis without optional MultiPV.

The packaged runtime acceptance separately exercises folder discovery, worker PGN indexing, library selection, legal human moves, sourced historical replies, checkmate, save, PGN reload and complete desktop rendering. It writes its own `packaged: true` receipt. The game is `1. f3 e5 2. g4 Qh4# 0-1`; both Black moves are from the imported fixture database, and no UCI engine is needed. Synthetic fixture data is not presented as a real historical corpus.

See `evidence/test-summary.json`, `evidence/packaged-acceptance.json`, screenshot and installer receipt. Unit-suite count excludes the separate executable and installer workflows. Portable and installed executable hashes are compared. The installer is tested per user into a dedicated test directory, then its uninstaller is run. This proves this host/runtime combination, not a clean external Windows machine.

Missing large-corpus, clean-machine, expanded DPI and proprietary-converter testing prevents a full mission PASS. Full-game batch analysis, tournament-filtered opponents and increment clocks are not implemented. Initial delivery status: **PARTIAL**, with the central playable acceptance demonstrated.
