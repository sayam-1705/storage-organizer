## Summary

Describe what changed and why.

## Change type

- [ ] Bug fix
- [ ] Feature
- [ ] Documentation
- [ ] Tests
- [ ] Build / packaging / CI
- [ ] Maintenance

## Validation

- [ ] Added or updated tests where appropriate.
- [ ] Ran `python -m pytest --cov=storage_organizer --cov-report=term-missing`.
- [ ] Ran `python scripts/run_demo_smoke.py` when relevant.
- [ ] Ran the benchmark smoke test when relevant.
- [ ] Ran `python -m compileall -q src` and `python -m pip check`.
- [ ] Updated documentation and `CHANGELOG.md` where appropriate.

## Data-safety review

- [ ] Source files are never deleted or modified.
- [ ] No silent overwrites were introduced.
- [ ] SHA-256 verification and safe publication behavior remain intact.
- [ ] Tests use synthetic data; no personal files, media, credentials, or local logs are included.

## Compatibility and risk

Describe affected operating systems, filesystems, Python versions, configuration, and packaging behavior. Call out any migration or release implications.

## Screenshots / logs (optional)

Include only sanitized output. Do not attach private user data.
