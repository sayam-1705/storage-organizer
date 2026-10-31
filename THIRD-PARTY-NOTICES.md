# Third-party software notices

The native desktop packages bundle third-party runtime components in addition to
Storage Organizer. This inventory identifies the principal direct runtime
components of the current desktop build. The exact binaries and transitive
components can vary by operating system and must be audited from each release
bundle before public distribution.

## Qt for Python: PySide6 and Shiboken6

The desktop user interface uses PySide6 and Shiboken6 (version 6.12.0 in the
pinned desktop build). Qt for Python is dual-licensed under open-source terms
(including LGPLv3 and GPL variants) or commercial terms. Qt modules do not all
share the same license; inspect the license information for each binary/module
actually shipped in the bundle.

- Qt for Python licensing: https://doc.qt.io/qtforpython-6.12/commercial/index.html
- Qt module licensing: https://doc.qt.io/qt-6/licensing.html
- Qt LGPL obligations: https://www.qt.io/development/open-source-lgpl-obligations
- Qt source and project: https://code.qt.io/cgit/pyside/pyside-setup.git/

The PyInstaller build uses the `onedir` layout so its runtime libraries remain
separate files rather than being embedded in a single-file executable. This is
not, by itself, a complete LGPL compliance determination. Before distributing
native binaries, maintainers must inventory the exact Qt libraries/plugins in
each platform bundle, include the applicable license texts and notices, make
the corresponding library source and any local modifications available as
required, and confirm the user's applicable rights to replace/relink the Qt
libraries. Do not publish native installers until this review is complete.

## Pillow

Pillow 13.0.0 is pinned in the native desktop build. Its PyPI metadata declares
`MIT-CMU`; inspect the exact wheel and any bundled codec notices during the
release audit. Upstream project and release metadata:
https://pypi.org/project/pillow/13.0.0/ and https://python-pillow.org/

## pypdf

pypdf 6.21.4 is pinned in the native desktop build and declares `BSD-3-Clause`.
The required copyright and disclaimer notice must accompany binary
redistribution. Upstream project and license:
https://pypi.org/project/pypdf/6.21.4/ and https://github.com/py-pdf/pdf/

## PyInstaller

PyInstaller 6.22.3 is a build-time freezer. Its GPL 2.0-or-later terms include
a bootloader exception for applications produced by PyInstaller; see the current
license documentation:
https://pyinstaller.org/en/stable/license.html

## Release audit requirement

This file is an inventory and pointer to upstream terms, not a substitute for
legal advice or a complete transitive dependency SBOM. For every release, retain
the resolved dependency versions, inspect the exact bundled binary components,
include all applicable copyright/license notices, and verify the distribution
and relinking/source obligations before publishing native installers.
