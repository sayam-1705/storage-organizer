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
