# Safety model and operational checklist

- Start with `preview` and inspect the planned destination paths.
- Use a destination with enough free space and a stable power connection.
- Do not unplug a source or destination during a transfer.
- Originals are never deleted by the application.
- Existing destination files are never intentionally overwritten. Conflicts are skipped or renamed.
- Source and destination cannot be the same directory or ancestor/descendant paths.
- Symlinked files and directories are skipped by the scanner to avoid traversing outside the selected tree.
- Metadata readers are optional and run locally. Do not install third-party metadata packages unless needed.
- Keep configuration and logs private; they can include file paths and error details.
- Test with disposable sample data before using irreplaceable files.

## Recovery after interruption

The application writes each copy to a temporary file, verifies it, and then publishes it under its final name. If interrupted, a `.storage-organizer-*.partial` file may remain. Review such files before removing them. Re-run the organizer: identical files already at the destination will be skipped by hash. The source remains available for retry.

## Threats not fully eliminated

Hardware failure, sudden power loss, malicious filesystem behavior, and filesystem limitations can still cause errors. SHA-256 verification reduces the risk of undetected copy corruption but is not a substitute for a separate backup. This tool is an organizer, not a backup system.
