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


def test_rejects_path_traversal_in_unknown_date_folder(tmp_path):
    config_path = tmp_path / "unsafe.toml"
    config_path.write_text('[organization]\nunknown_date_folder = "../outside"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="safe folder name"):
        load_config(config_path)


def test_rejects_invalid_rename_template(tmp_path):
    config_path = tmp_path / "unsafe-template.toml"
    config_path.write_text('[duplicates]\nrename_template = "../{stem} ({number}){suffix}"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid filename characters"):
        load_config(config_path)


def test_rejects_unknown_configuration_keys(tmp_path):
    config_path = tmp_path / "typo.toml"
    config_path.write_text('[transfer]\nverfiy_hash = false\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown key"):
        load_config(config_path)
