# Project maintenance

This document describes the ongoing maintenance practices for Storage Organizer. Repository settings mentioned here are configured in GitHub and are not activated merely by adding workflow or policy files.

## Supported releases

- Prefer the latest published stable release for normal use.
- Security fixes are targeted at the latest published stable release; `main` may contain fixes intended for the next release.
- Older releases are not guaranteed to receive backports.
- Python support starts at Python 3.11. The CI matrix is the authoritative automated compatibility check for the Python versions and operating systems currently listed in `.github/workflows/ci.yml`.
- Native desktop support is limited to the targets documented in `docs/packaging.md`. Do not imply support for untested CPU architectures or operating systems.

## Pull requests and branch protection

Use focused pull requests and require the CI and security checks to pass before merging. For a small single-maintainer project, review requirements should match the available reviewer pool; do not configure a mandatory approval count that makes the owner unable to merge their own fixes.

Recommended GitHub ruleset for `main`:

1. Require pull requests before merging for collaborative changes.
2. Require the CI Python matrix and desktop smoke checks to pass.
3. Require CodeQL and dependency review checks where GitHub exposes them as required statuses.
4. Block force pushes and branch deletion.
5. Allow maintainers an explicit, documented emergency path for restoring a broken release or addressing an urgent security issue.

The exact check names can change when matrix jobs or workflow names change. Select the successful checks displayed in GitHub after the new workflows have run; do not guess their names. A ruleset is not enabled by this file and must be configured under **Settings → Rules → Rulesets**.

## Automated dependency maintenance

`.github/dependabot.yml` requests weekly updates for Python packages declared in `pyproject.toml` and GitHub Actions used by workflows. Minor and patch updates are grouped to reduce PR noise; major updates remain separately reviewable.

For every dependency PR:

- Inspect the upstream changelog and compatibility notes.
- Review security advisories and license changes.
- Run the full CI matrix and relevant packaging checks.
- Review Qt/PySide6 and transitive runtime changes carefully because they affect redistributable desktop packages.
- Update `packaging/constraints-desktop.txt` deliberately when changing the pinned desktop build toolchain; do not let a routine dependency PR silently change the release bundle.

Enable Dependabot security updates and alerts in **Settings → Code security and analysis**. Dependabot version updates are configured by the YAML file; security alert and security-update availability also depend on repository settings and GitHub features.

## Code scanning and dependency review

- `.github/workflows/codeql.yml` runs CodeQL for Python on pushes to `main`, pull requests, a weekly schedule, and manual dispatch.
- `.github/workflows/dependency-review.yml` checks pull-request dependency changes and fails on vulnerabilities rated moderate or higher.
- Findings must be triaged. A successful workflow is not proof that the project has no vulnerabilities.
- Enable repository code scanning and review the **Security** tab after the first CodeQL run.

## Security reporting and repository settings

The repository should enable **Private vulnerability reporting** under **Settings → Code security and analysis**. `SECURITY.md` provides fallback contact instructions but public issue reporting is not an acceptable channel for vulnerabilities.

Also consider enabling:

- Dependabot alerts and security updates.
- Secret scanning and push protection where available.
- A branch ruleset for `main`.
- Actions permissions restricted to read by default; grant write only to the specific job that needs it.

These settings are manual administrative actions. Confirm them in GitHub rather than assuming the policy files enabled them.

## Release checklist

Before creating a tag:

1. Confirm the working tree and `main` are clean and all CI/security checks pass.
2. Update `pyproject.toml` and add a complete version section to `CHANGELOG.md`.
3. Review dependency and license changes, especially the exact Qt/PySide6 modules and plugins in each desktop bundle.
4. Build native packages on the supported native runners.
5. Install and manually test the artifacts on representative target systems with disposable test data.
6. Verify the generated SHA-256 checksums.
7. Publish only after the Qt/PySide6 license, notices, source-material, and applicable replace/relink obligations have been reviewed and satisfied.
8. Do not set `NATIVE_RELEASE_LICENSE_APPROVED=true` until that review is complete.

The release workflow is tag-triggered. Its build jobs can succeed while the publish job remains skipped by the licensing gate. A successful tagged workflow does not by itself mean that a public GitHub Release exists.

## Maintenance cadence

- Review Dependabot PRs weekly.
- Review CodeQL findings when alerts arrive and after scheduled scans.
- Review the GitHub Actions and packaging toolchain at least once per release.
- Re-test native installers after changes to PySide6, PyInstaller, packaging scripts, target OS runners, or supported OS baselines.
- Keep README installation instructions, `docs/packaging.md`, `THIRD-PARTY-NOTICES.md`, and `CHANGELOG.md` synchronized with actual release behavior.
