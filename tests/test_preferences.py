import json
from pathlib import Path
from storage_organizer import preferences


def test_preferences_round_trip_without_database(tmp_path, monkeypatch):
    location = tmp_path / "user-data"
    monkeypatch.setattr(preferences, "user_data_dir", lambda: location)
    assert preferences.load_preferences() == {}
    preferences.save_preferences(source="/tmp/source")
    preferences.save_preferences(destination="/tmp/destination")
    assert preferences.load_preferences() == {"source": "/tmp/source", "destination": "/tmp/destination"}
    assert json.loads((location / "preferences.json").read_text()) == {"source": "/tmp/source", "destination": "/tmp/destination"}


def test_multiple_source_preferences_preserve_legacy_first_source(tmp_path, monkeypatch):
    location = tmp_path / "user-data"
    monkeypatch.setattr(preferences, "user_data_dir", lambda: location)

    preferences.save_preferences(sources=["/mnt/drive-a", "/mnt/drive-b", "/mnt/drive-a"])

    assert preferences.load_preferences() == {
        "source": "/mnt/drive-a",
        "sources": ["/mnt/drive-a", "/mnt/drive-b"],
    }


def test_recent_run_history_is_atomic_and_bounded(tmp_path, monkeypatch):
    location = tmp_path / "user-data"
    monkeypatch.setattr(preferences, "user_data_dir", lambda: location)

    for index in range(12):
        preferences.save_recent_run({"id": index, "status": "completed"})

    runs = preferences.load_recent_runs()
    assert len(runs) == 10
    assert [item["id"] for item in runs] == list(range(11, 1, -1))
    assert not (location / "recent-runs.json.tmp").exists()
