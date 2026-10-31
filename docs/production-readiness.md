# Production-readiness audit

This checklist records the safeguards covered by the code and automated tests. It is not a claim that every operating system/filesystem combination has been physically tested.

## Implemented safeguards

- Copy-only operation: source files are never deleted.
- Preview is read-only and does not create the destination.
- Source and destination paths are canonicalized and overlapping trees are rejected.
- Existing destination symlinks/junctions are rejected, and the transfer layer rechecks destination parents before writing.
- Source symlinks are skipped during scans and checked again immediately before a copy.
- Files are copied to a same-directory temporary file and verified against the planned SHA-256 digest before publication.
- Existing files are not intentionally overwritten; identical files are skipped and different-name collisions are renamed.
- Stale `.storage-organizer-*.partial` files are not treated as successful copies during duplicate scanning. They are left for user review rather than automatically deleted.
- File names are normalized when required for common Windows/removable-filesystem compatibility; reserved Windows device names are prefixed.
- Configuration sections, keys, date policy, folder names, rename templates, and verification flags are validated.
- GUI defaults to Qt's generic platform theme on Linux unless the user explicitly sets `QT_QPA_PLATFORMTHEME`, avoiding a known GNOME xsettings schema crash on some installations.
- GUI supports multiple source folders, scan progress, byte-level transfer progress with throughput/ETA, per-file search/status filters, validated settings, and a bounded local recent-operation history.
- Settings and logs are ordinary local files. No database, cloud service, or network request is required by the application.
- Tests generate synthetic files in temporary directories; no real media fixtures are stored in Git.
- Native desktop release workflows are configured for native OS/architecture runners: Windows x64 installer, macOS arm64 and Intel DMGs, and Linux x86_64 AppImage.
- The v1.0.2 tagged release workflow completed successfully: the Python distribution build and all four native desktop installer jobs passed. The published release contains the Windows x64 installer, macOS ARM64 and Intel DMGs, Linux x86_64 AppImage, Python wheel, source distribution, and `SHA256SUMS.txt`. The installed packages were also manually tested by the maintainer.
- Third-party license compliance: the exact Qt/PySide6/Qt plugin inventory, corresponding source availability, license texts, and relinking/replacement rights must be verified before native release publication. The release workflow is gated on the `NATIVE_RELEASE_LICENSE_APPROVED=true` repository Actions variable, which must remain unset until that review is complete.

## Required release checks

The v1.0.2 release build and installer QA are complete. The items below distinguish automated validation and maintainer-reported installer testing from platform and legal checks that still require separate evidence.

- [x] CI passes on Ubuntu, Windows, and macOS for every Python version in the workflow matrix.
- [x] GUI initialization smoke test passes on all CI operating systems.
- [x] Review the output of `python -m pytest --cov=storage_organizer --cov-report=term-missing`.
- [ ] Manually test a small disposable dataset on representative physical filesystems (for example NTFS, exFAT, APFS, and ext4). CI uses generated files and does not replace this check.
- [ ] Test a full destination, unplug/reconnect behavior, and interruption during a large-file copy on expendable storage.
- [x] Confirm generated wheel/sdist contents do not contain private files or media assets.
- [x] Build and smoke-test frozen desktop bundles on the native target runners.
- [x] Validate the Windows installer, both macOS disk images, and Linux AppImage in the v1.0.2 tagged release workflow.
- [x] Publish SHA-256 checksums for all seven release assets and verify the checksum file is attached to the release.
- [ ] Review third-party license obligations and publish any required notices/source/relinking materials for bundled Qt/PySide6 components. Do not treat successful installer testing as a substitute for this review.
- [ ] Complete representative physical-filesystem and interruption testing before claiming support for those scenarios.

## Repository maintenance validation

- [x] Main-branch CI passed on the 12-job Python/OS matrix and four native frozen-desktop smoke jobs.
- [x] CodeQL completed successfully on the main branch and uploaded its analysis results.
- [x] Dependency Graph was enabled in repository settings; the two open Dependabot action-update pull requests then passed Dependency Review, CI, and CodeQL.
- [x] Active GitHub rulesets protect `main` and `v*` release tags. The `main` ruleset currently requires the 12 Python matrix checks; adding desktop smoke, CodeQL, and Dependency Review as required checks remains a recommended administrative improvement.

## Known limits

- The CI matrix is automated coverage, not proof that a physical USB drive or every filesystem was tested. FAT32, exFAT, NTFS, APFS, and ext4 differ in supported metadata, naming, and atomic operations.
- The app does not guarantee crash durability against sudden power loss or failing hardware. Temporary files can remain after a crash; they are ignored for duplicate detection and are not automatically deleted.
- The transfer engine verifies content with SHA-256 by default. Hashing large destination trees can be I/O intensive.
- File-based logs are not a transactional journal. Recovery is based on inspecting the destination and safely rerunning the copy.
- Filename normalization can change names that are not portable to Windows or common removable filesystems. Review the preview before copying.
- Metadata availability varies. Files without supported embedded dates fall back to modification time; the application cannot guarantee the original capture/creation date.
- GUI progress speed and ETA are estimates based on bytes written to temporary destination files; changing source files or storage throughput can affect the estimate.
- Recent-operation history is a convenience summary, not a transactional recovery journal. It stores source/destination paths and aggregate counts locally.
- A separate backup is still recommended for irreplaceable data.
