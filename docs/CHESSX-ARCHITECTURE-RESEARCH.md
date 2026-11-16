# ChessX architecture and integration research

Investigated the supplied local ChessX source before downloading reader dependencies. The original reference tree was read only and was not overwritten. Six selected files match current upstream revision `c7d815796e977c1ededef515d6db00bff326bd8d` after newline normalization; hashes and filenames are in `evidence/chessx-source-comparison.json`. This is a six-file comparison, not proof that the entire extracted tree matches that commit.

## Source map

| Area | Local source modules studied | Finding / CBA reuse |
|---|---|---|
| Build | `CMakeLists.txt`, `chessx.pro`, `src`, `dep`, `lib`, `tests`, `data` | C++17 CMake path requests Qt5 Core/Xml/DBus/Network/OpenGL/Svg/PrintSupport/Gui/Widgets and optional multimedia/TTS; qmake is a separate route. CBA is Python/PySide6 Qt6: these are not directly importable Python modules. |
| Board | `src/gui/boardview.*`, `boardviewex.*`; `src/database/board.*`, `gamex.*` | Custom C++ board/game models and Qt widgets. Preserve existing python-chess legality and SVG Qt widget instead of introducing another rules implementation. |
| Database abstraction | `database.h`, `memorydatabase.*`, `streamdatabase.*`, `index.*`, `filter.*` | Abstract open/load/search/count APIs, filters and separate indexes. Adapted the capability-reporting and logical-database boundary as Python reader contracts. No ChessX C++ ABI linked. |
| PGN | `pgndatabase.*`, `lib/chessx-pgn` | Streaming token/game parsing, offsets/index association. Existing mature python-chess PGN route retained, with a reader-registry adapter. |
| Scid | `src/database/scid/sciddatabase.*`, `dep/scid`, `codec_scid4` | Coordinated Scid database codec, game/tag/variation adaptation, progress bridge and cancellation. Not a lone `.sg4` reader. No CBA native Scid build or representative real-file test; UNSUPPORTED. |
| CTG | `ctgdatabase.cpp`, `ctg.h`, `ctgbookwriter.*` | Page/hash/position decoding and move/statistics handling; code credits Daydreamer and Stephan Vermeire's Brutus CTG work. Tightly coupled to BoardX/Move/Qt types. Not ported; CTG/CTB/CTO grouped but UNSUPPORTED. |
| Polyglot | `polyglotdatabase.*`, `polyglotwriter.*` | Fixed entries, position hash lookup and move map. Existing python-chess memory-mapped implementation retained, avoiding a redundant port. |
| Arena | `arenabook.cpp`, `abk.h` | 28-byte packed little-endian nodes, root record 900, child/sibling traversal and promotion mapping. Adapted into a bounded read-only Python mmap adapter with pointer/cycle/depth checks. Unlike ChessX's readAll path, CBA does not copy the whole book into RAM. Generated-file tests only: PARTIAL SUPPORT. Attribution and GPL notice retained. |
| Engines | `enginex.*`, `uciengine.*`, `wbengine.*`, `enginelist.*`, `engineparameter.h`, GUI engine-option models | UCI negotiation/options/profiles and separate XBoard protocol. CBA retains python-chess UCI implementation and adds a persistent registry/manager. XBoard/WinBoard studied, not integrated or advertised. |
| Opening tree | `openingtree.*`, `openingtreethread.*`, GUI `openingtreewidget.*` | Special book move maps; game search processed in batches of 100 with progress/filter updates. CBA uses persistent SQLite continuation rows, canonical positions, per-source comparison and background segment indexing. No copied C++ tree code. |
| Search | `search.*`, `tagsearch.*`, `positionsearch.*`, `elosearch.*`, `datesearch.*`, `filter.*` | Composable predicates; PositionSearch delegates to `database->findPosition` and returns ply+1. CBA's transposition-aware canonical keys remain unchanged; native CBH header search uses cbvault rather than a Python full-name scan. |
| Background/persistence | `openingtreethread.*`, Scid progress bridge, `settings.*`, `chessxsettings.*` | QThread/progress/cancellation, QSettings and database-specific index state. CBA uses queued Qt signals, worker threads, SQLite checkpoints, JSON profiles and optional alternate cache location. |

## Integration choices

A native C++ shared library would require an explicit C ABI and ownership/error contracts around ChessX's Qt/custom chess types, plus matching build/runtime dependencies. Python bindings would add the same adaptation and another packaging layer. Replacing the UI with a built ChessX executable would not extend the existing application as requested. A full ChessX GUI build therefore was not selected: it would not itself provide a standalone CBH reader or a stable Python API. No successful ChessX build is claimed.

A standalone Rust helper linked to cbvault provides the required read-only CBH boundary with much less coupling: JSON-lines requests, stable native record IDs, annotated PGN per requested game, bounded ranges, source counts, and native player-prefix header search. It runs locally via pipes, with no listener, account, token or network service. CBA independently validates decoded moves/variations through python-chess and indexes only eligible legal mainlines. Original database files remain read only. This is an actual Windows-built and exercised integration, not a proposal.

Selected documented algorithm adaptation is useful for ABK's small node structure. Larger CTG/Scid adapters remain separate work and cannot inherit compatibility from ChessX merely being able to read them.

## Other native readers evaluated

- [cbvault](https://github.com/itshak/cbvault), pinned `ce5a582d98c3d0ac62dc10b965b4fb32d102da97`, MIT, Rust 2024, 0.1.7: selected. Source exposes generation-aware Database/GameBuf, native headers, range conversion, annotation-preserving PGN, search and archive decoding. Actual classic CBH data was read here. Upstream 2CBH/CBV/CBZ claims are not promoted to verified CBA support without local format tests.
- [oschess-cb-bridge](https://github.com/asavis/oschess-cb-bridge): studied `cbformat::view::Base`, cbtool export, header/move-tree architecture, position-index bridge and current AGPL licensing. It has direct native CBH/2CBH and PGN support, plus a network-facing downstream bridge. CBA does not need its server. Its current reader was not compiled or shipped here; cbvault's separately documented MIT-era provenance is preserved rather than silently copying current AGPL source.
- [libcbh](https://github.com/rolandlo/libcbh): studied C++20 CMake shared-library target, CbhCodec/open/numGames/parseNext and annotated move structures. It would need a C shim or subprocess plus Windows export/dependency work. No Windows build is claimed; it was not needed after real cbvault decoding succeeded. GPL notices remain important if used later.

Source licenses are in `licenses/`; no purchased database or extracted PGN is distributed. Reference source discovery does not establish that every format or engine protocol was integrated.
