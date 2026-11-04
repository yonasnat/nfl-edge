"""End-to-end checks of the web API. Skipped when the data hasn't been built."""
from pathlib import Path

import pytest

if not Path("data/features.parquet").exists():
    pytest.skip("data not built (run build_all.py)", allow_module_level=True)

from fastapi.testclient import TestClient

import api
import assistant
import snapshots

client = TestClient(api.app)  # not used as a context manager, so the background thread doesn't start


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshots, "DATABASE_URL", None)
    monkeypatch.setattr(snapshots, "SQLITE_PATH", str(tmp_path / "snap.db"))
    snapshots.setup()


def test_health():
    assert client.get("/").json() == {"message": "NFL Edge API is running"}


def test_assistant_status_and_disabled_ask(monkeypatch):
    monkeypatch.setattr(assistant, "API_KEY", None)
    assert client.get("/assistant").json()["enabled"] is False
    response = client.post("/games/anything/ask", json={"question": "hi"})
    assert response.status_code == 503


def test_changes_endpoint_validates_since():
    assert client.get("/games/G1/changes?since=not-a-date").status_code == 400
    assert client.get("/games/G1/changes?since=2026-11-01T12:00:00Z").json()["changes"] == []
