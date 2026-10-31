from __future__ import annotations

import json
from pathlib import Path
import pytest
from storage_organizer.cli import main
from storage_organizer.config import load_config, save_config


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
    assert len(result["files"]) == 1
    assert result["files"][0]["status"] == "copied"
    assert result["files"][0]["source"] == str(source / "notes.txt")


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


def test_cli_json_reports_copied_duplicate_and_destination_skip(tmp_path, make_file, capsys):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    make_file(source / "one.txt", b"source duplicate")
    make_file(source / "two.txt", b"source duplicate")
    make_file(source / "three.txt", b"already in destination")
    make_file(destination / "archive" / "existing.txt", b"already in destination")

    code = main([
        "organize",
        "--source", str(source),
        "--destination", str(destination),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    statuses = {Path(item["source"]).name: item for item in payload["files"]}

    assert code == 0
    assert payload["scanned"] == 3
    assert payload["copied"] == 1
    assert payload["duplicates"] == 1
    assert payload["skipped_identical"] == 1
    assert statuses["one.txt"]["status"] == "copied"
    assert statuses["two.txt"]["status"] == "duplicate"
    assert statuses["two.txt"]["duplicate_of"] == str(source / "one.txt")
    assert statuses["three.txt"]["status"] == "skipped"
    assert statuses["three.txt"]["duplicate_of"].endswith("existing.txt")


def test_save_config_round_trips_gui_organization_settings(tmp_path):
    config_path = tmp_path / "config.toml"
    config = load_config(tmp_path / "missing.toml")
    config["organization"]["include_hidden"] = True
    config["organization"]["date_policy"] = "modified"
    config["organization"]["unknown_date_folder"] = "Unsorted Items"

    assert save_config(config, config_path) == config_path
    loaded = load_config(config_path)
    assert loaded["organization"]["include_hidden"] is True
    assert loaded["organization"]["date_policy"] == "modified"
    assert loaded["organization"]["unknown_date_folder"] == "Unsorted Items"


def test_save_config_rejects_invalid_settings_without_replacing_existing_file(tmp_path):
    config_path = tmp_path / "config.toml"
    config = load_config(tmp_path / "missing.toml")
    save_config(config, config_path)
    original = config_path.read_text(encoding="utf-8")
    config["organization"]["unknown_date_folder"] = "../unsafe"

    with pytest.raises(ValueError, match="safe folder name"):
        save_config(config, config_path)

    assert config_path.read_text(encoding="utf-8") == original
    assert not (tmp_path / "config.toml.tmp").exists()
