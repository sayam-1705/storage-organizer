# Contributing to Storage Organizer

Thank you for considering a contribution. Storage Organizer is an offline-first, copy-only file organizer. Contributions should preserve its data-safety guarantees and keep the core usable without a network connection or database.

## Before opening an issue

- Search existing issues and pull requests for duplicates.
- For support questions, include the application version, operating system, Python version (when relevant), and a minimal description of the issue.
- Never attach private documents, personal media, drive dumps, credentials, access tokens, or unredacted logs. Use synthetic files and redact local usernames and paths.
- Do not report security vulnerabilities in public issues. Follow [SECURITY.md](SECURITY.md).

## Development setup

Requirements: Python 3.11 or newer. The GUI and media extras are optional; the test extra is required to run the test suite.

```bash
git clone https://github.com/sayam-1705/storage-organizer.git
cd storage-organizer
python -m venv .venv
```

Activate the environment:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the project and development extras:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test,gui,media]"
```

## Run checks

Run the full test suite with coverage:

```bash
python -m pytest --cov=storage_organizer --cov-report=term-missing
```

Run the synthetic end-to-end check and benchmark smoke test:

```bash
python scripts/run_demo_smoke.py
python scripts/benchmark_large_dataset.py --files 500 --file-size 256 --directories 10 --copy
```

Check the CLI and source compilation:

```bash
storage-organizer --help
python -m compileall -q src
python -m pip check
```

For desktop packaging work, use the pinned toolchain in `packaging/constraints-desktop.txt` and follow [docs/packaging.md](docs/packaging.md). Native desktop bundles must be built on their target operating system and architecture.

## Engineering expectations

- Preserve copy-only behavior. Never delete or mutate source files.
- Preserve preview as a read-only operation.
- Do not introduce silent overwrites. Keep safe, no-overwrite publication and SHA-256 verification behavior intact.
- Keep file traversal deterministic and avoid following source symlinks.
- Use bounded-memory techniques for large files and datasets.
- Keep the core offline and independent of the GUI. Avoid adding network services, databases, or mandatory third-party runtime dependencies without a clear design discussion.
- Keep user data out of tests and commits. Generate fixtures in temporary directories and use synthetic content.
- Add regression tests for bug fixes and tests for new behavior. Include platform-specific coverage where path, filesystem, or GUI behavior differs.
- Update documentation and `CHANGELOG.md` when user-visible behavior, configuration, commands, packaging, or compatibility changes.
- Treat `THIRD-PARTY-NOTICES.md` and the Qt/PySide6 redistribution review as release-critical.

## Pull request process

1. Create a focused branch from `main`.
2. Make the smallest coherent change that solves the problem.
3. Add or update tests and documentation.
4. Run the relevant local checks before pushing.
5. Open a pull request using the repository template. Explain the problem, the approach, compatibility impact, and how the change was tested.
6. Address review feedback and keep the branch current with `main`.

Use clear commit messages. Conventional prefixes such as `feat:`, `fix:`, `docs:`, `test:`, `build:`, and `chore:` are encouraged but not mandatory.

## Release changes

Do not create or push a release tag as part of an ordinary feature pull request. Releases are tag-triggered and must satisfy the exact version, changelog, test, artifact, manual QA, and licensing requirements documented in [docs/packaging.md](docs/packaging.md) and [docs/maintenance.md](docs/maintenance.md). Do not enable `NATIVE_RELEASE_LICENSE_APPROVED` until the Qt/PySide6 review is complete.
