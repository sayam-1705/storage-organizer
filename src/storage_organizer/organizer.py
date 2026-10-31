from __future__ import annotations

from pathlib import Path

from .config import load_config
from .logging_setup import setup_logging
from .planner import build_plan
from .storage import validate_paths
from .transfer import execute_plan


def create_plan(sources: list[Path], destination: Path, config_path: Path | None = None):
    config = load_config(config_path)
    sources, destination = validate_paths(sources, destination)
    return build_plan(sources, destination, config), config, sources, destination


def organize(
    sources: list[Path],
    destination: Path,
    config_path: Path | None = None,
    progress=None,
    logger=None,
    cancel_event=None,
    file_progress=None,
    plan_ready=None,
):
    """Plan and execute an organization run.

    ``plan_ready`` is called once after planning, before transfer begins. The
    optional ``file_progress`` callback reports structured per-file transitions.
    Existing ``progress`` callers retain their original callback signature.
    """
    plan, config, sources, destination = create_plan(sources, destination, config_path)
    if plan_ready:
        plan_ready(plan)
    if logger is None:
        log_dir = None
        raw = config.get("logging", {}).get("directory")
        if raw:
            log_dir = Path(raw).expanduser()
        logger = setup_logging(log_dir)
    summary = execute_plan(
        plan,
        verify_hash=bool(config["transfer"].get("verify_hash", True)),
        logger=logger,
        progress=progress,
        cancel_event=cancel_event,
        file_progress=file_progress,
    )
    return summary, plan
