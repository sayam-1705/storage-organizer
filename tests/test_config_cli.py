from __future__ import annotations

import json
from pathlib import Path
import pytest
from storage_organizer.cli import main
from storage_organizer.config import load_config


def test_loads_default_config(tmp_path):
    config = load_config(tmp_path / "does-not-exist.toml")
    assert config["transfer"]["verify_hash"] is True
    assert config["organization"]["date_policy"] == "metadata_then_modified"


def test_rejects_invalid_config(tmp_path):
    config_path = tmp_path / "bad.toml"
    config_path.write_text('[organization]\ndate_policy = "invented"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(config_path)


def test_cli_preview_json_and_organize(tmp_path, make_file, capsys):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "notes.txt", b"hello")
    assert main(["preview", "--source", str(source), "--destination", str(destination), "--json"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert len(preview) == 1
    assert preview[0]["action"] == "copy"
    assert not destination.exists()
    assert main(["organize", "--source", str(source), "--destination", str(destination), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["copied"] == 1
    assert result["failed"] == 0


def test_cli_rejects_overlapping_paths(tmp_path, make_file, capsys):
    source = tmp_path / "source"
    make_file(source / "a.txt")
    assert main(["preview", "--source", str(source), "--destination", str(source / "out")]) == 2
    assert "must not overlap" in capsys.readouterr().err
