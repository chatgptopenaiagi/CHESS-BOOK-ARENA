# 0.2.0 format compatibility

| Family | CBA status | Verified boundary |
|---|---|---|
| PGN / PGN.GZ / PGN.ZIP | READ-ONLY SUPPORTED | Existing streaming import, annotated replay/export and ZIP member parsing |
| FEN / EPD | READ-ONLY SUPPORTED | Position validation and training; not game collections |
| Polyglot BIN | READ-ONLY SUPPORTED | Correct hash/entry lookup, legal candidates, weights, fixture tests |
| Classic CBH multi-file family | READ-ONLY SUPPORTED | Native cbvault helper, actual large multi-file database, stable IDs, annotated and nonstandard games, bounded indexing and sourced play. Null-analysis mainlines retained but excluded from historical statistics. No write support. |
| 2CBH family | PARTIAL SUPPORT | Adapter delegates to upstream generation-aware API; no representative real 2CBH file tested here. Never described as fully supported. |
| Arena ABK | PARTIAL SUPPORT | ChessX-derived node algorithm, generated legal book and malformed-cycle tests. No representative third-party ABK book tested. |
| CTG / CTB / CTO | UNSUPPORTED | Companion grouping and source research only. No constructor-only compatibility claim. |
| Scid SI4 / SG4 / SN4 / SCID4 | UNSUPPORTED | Components grouped under SI4; no integrated native codec or real-file test |
| CBV / CBZ | UNSUPPORTED | Upstream cbvault archive feature studied but not integrated/tested in CBA; no automatic extraction claim |

No current format is classified FULLY SUPPORTED or CONVERSION SUPPORTED. Source access is deliberately read only, and no external converter has been validated. Source extension recognition, successful native open, per-game decoding, and indexed coverage are separate states.

Classic required components: CBH headers, CBG moves, CBA annotations, CBP players, CBT tournaments, CBC annotators, CBS sources. CBJ and other optional files are retained in the source signature when present. The native decoder may require wide-offset companions for sufficiently large files; its typed errors are shown rather than guessing offsets. Source directories are never reorganized.
