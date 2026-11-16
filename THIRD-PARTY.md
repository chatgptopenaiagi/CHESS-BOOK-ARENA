# Third-party components

This application is GPL-3.0-or-later because it uses python-chess (GPL-3.0-or-later). Chess SVG pieces are rendered by python-chess; its distributed piece artwork attribution identifies Colin M. L. Burnett, licensed under GPL v2 or later. Retain the upstream package notices distributed in `_internal` and available with source at https://github.com/niklasf/python-chess.

PySide6 / Qt are dynamically loaded, under LGPL v3 / GPL v3 / commercial licensing as supplied upstream. This distribution uses the open-source licensing route. Qt source, license terms and replacement/relinking information: https://www.qt.io/licensing/open-source-lgpl-obligations and https://code.qt.io/cgit/pyside/pyside-setup.git/. The portable `_internal/PySide6` libraries can be replaced with ABI-compatible builds; no application integrity lock prevents replacement. PyInstaller bootloader is GPL with its distribution exception. Python uses the PSF license. Upstream license files are included in the installer/portable distribution under `licenses`.

Stockfish is not redistributed; local optional engine use does not establish bundling rights for any arbitrary engine. Synthetic examples were authored for this application.

## 0.2.0 native additions

CBA's JSON-lines helper links cbvault 0.1.7, pinned at `ce5a582d98c3d0ac62dc10b965b4fb32d102da97`, under MIT. Its notices, including MIT-era cbformat provenance, are supplied in `licenses/cbvault-MIT.txt` and `licenses/cbvault-THIRD-PARTY-NOTICES.md`. CBA does not incorporate current AGPL oschess bridge source or libcbh. Their repositories were research references only.

The Python Arena ABK adapter adapts node structure/traversal/promotion logic from ChessX `arenabook.cpp` and `abk.h`, copyright Jens Nissen 2017, GPL v2 or later. ChessX attribution and license are retained in code and `licenses/ChessX-GPL2.txt`; CBA distributes the adaptation under its GPL v3-or-later terms. Other ChessX components were studied but not copied or linked.

Stockfish and Leela remain separately installed engines, outside the application installer. The optional downloader retains each official package's notices/runtime files. A locally verified Lc0 CPU installation does not establish compatibility for GPU releases or arbitrary networks.
