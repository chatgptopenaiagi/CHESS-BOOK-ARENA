# Architecture

`app/catalog.py` owns read-only streaming adapters, SQLite source catalog, raw PGN retention, collision-free canonical position keys, player-aware continuation rows, recovery and game persistence. SQLite WAL and separate per-operation connections permit worker indexing while the UI reads committed data. Catalog position counts differ from raw move entries and distinct games.

`app/opponents.py` defines the common `ChessOpponent` and `Decision` interfaces, historical database/player/book implementations, configurable selection, engine integration and explicit hybrid provenance. Every returned move is checked against mature python-chess legality both at candidate lookup and before application. Engine assistance cannot introduce a candidate outside the selected source. Database score is from the moving side's perspective.

`app/gui.py` owns the responsive three-panel Qt desktop, SVG board, promotion choice, legal targets, discovery, library, filtering, game modes, history, replay, variations, clocks and settings. Workers emit queued Qt signals; only the main thread mutates widgets. Mutations of the current board are guarded while the opponent is busy. Close requests cancel import and wait for background work rather than terminating transactions.

`app/verification.py`, tests and `--self-test <receipt.json>` provide deterministic executable acceptance with a complete, sourced historical fixture game. The executable uses temporary storage for acceptance; normal launches persist user state in LocalAppData. The launcher has no dependence on the source working directory. Inno Setup installs the whole portable runtime per user. No elevated permission is needed.

Security boundaries: no credentials stored, no original database writes, no network service, no bundled engine. ZIP paths are not passed to archive extraction; book filenames are reduced to basenames in the derived-data directory. The member limit bounds decompression size, though large compressed imports can still take time. Engine executables are user-selected local programs, not sandboxed.
