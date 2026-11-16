# Third-party components

This application is GPL-3.0-or-later because it uses python-chess (GPL-3.0-or-later). Chess SVG pieces are rendered by python-chess; its distributed piece artwork attribution identifies Colin M. L. Burnett, licensed under GPL v2 or later. Retain the upstream package notices distributed in `_internal` and available with source at https://github.com/niklasf/python-chess.

PySide6 / Qt are dynamically loaded, under LGPL v3 / GPL v3 / commercial licensing as supplied upstream. This distribution uses the open-source licensing route. Qt source, license terms and replacement/relinking information: https://www.qt.io/licensing/open-source-lgpl-obligations and https://code.qt.io/cgit/pyside/pyside-setup.git/. The portable `_internal/PySide6` libraries can be replaced with ABI-compatible builds; no application integrity lock prevents replacement. PyInstaller bootloader is GPL with its distribution exception. Python uses the PSF license. Upstream license files are included in the installer/portable distribution under `licenses`.

Stockfish is not redistributed; local optional engine use does not establish bundling rights for any arbitrary engine. Synthetic examples were authored for this application.
