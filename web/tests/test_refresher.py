"""Tests for web/app/refresher.py (scheduled market-data refresh).

Covers run_refresh success / non-zero / exception paths and the scheduler
start/shutdown lifecycle. subprocess is mocked so no real refresh runs.
"""

import pytest

from web.app import refresher


# ---------------------------------------------------------------------------
# run_refresh
# ---------------------------------------------------------------------------


def test_run_refresh_success_logs_rc(monkeypatch, caplog):
    class FakeResult:
        returncode = 0

    monkeypatch.setattr(refresher.subprocess, "run", lambda *a, **k: FakeResult())
    with caplog.at_level("INFO"):
        refresher.run_refresh()
    assert "refresh completed rc=0" in caplog.text


def test_run_refresh_nonzero_logs_error(monkeypatch, caplog):
    class FakeResult:
        returncode = 3

    monkeypatch.setattr(refresher.subprocess, "run", lambda *a, **k: FakeResult())
    with caplog.at_level("ERROR"):
        refresher.run_refresh()
    assert "refresh exited non-zero" in caplog.text


def test_run_refresh_exception_logs_failed(monkeypatch, caplog):
    def boom(*a, **k):
        raise OSError("boom")

    monkeypatch.setattr(refresher.subprocess, "run", boom)
    with caplog.at_level("ERROR"):
        refresher.run_refresh()  # must not raise
    assert "refresh failed" in caplog.text
    assert "boom" in caplog.text


def test_run_refresh_uses_expected_script_and_timeout(monkeypatch):
    captured = {}

    def fake_run(cmd, env=None, timeout=None):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        captured["has_env"] = env is not None
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(refresher.subprocess, "run", fake_run)
    monkeypatch.setattr(refresher, "_REFRESH_SCRIPT", "/app/refresh-market-data.sh")
    refresher.run_refresh()
    assert captured["cmd"] == ["/app/refresh-market-data.sh"]
    assert captured["timeout"] == 2700
    assert captured["has_env"]


# ---------------------------------------------------------------------------
# start_scheduler / shutdown_scheduler
# ---------------------------------------------------------------------------


def test_start_scheduler_registers_weekday_job(monkeypatch):
    # Ensure clean global state regardless of prior tests.
    monkeypatch.setattr(refresher, "_scheduler", None)
    created = {}
    monkeypatch.setattr(refresher.BackgroundScheduler, "add_job",
                        lambda self, fn, trigger, **kw: created.update({"fn": fn, "id": kw["id"]}))
    monkeypatch.setattr(refresher.BackgroundScheduler, "start", lambda self: None)
    s = refresher.start_scheduler()
    assert refresher._scheduler is s
    assert created["fn"] == refresher.run_refresh
    assert created["id"] == "market_refresh"
    # cleanup: reset global (scheduler was mocked, never actually started)
    monkeypatch.setattr(refresher, "_scheduler", None)


def test_shutdown_scheduler_noop_when_none(monkeypatch):
    monkeypatch.setattr(refresher, "_scheduler", None)
    refresher.shutdown_scheduler()  # must not raise


def test_scheduler_lifecycle_start_and_shutdown(tmp_path, monkeypatch):
    # Real BackgroundScheduler: start creates a background thread, shutdown stops it.
    monkeypatch.setattr(refresher, "_scheduler", None)
    s = refresher.start_scheduler()
    assert s.running is True
    # job is registered with our id
    ids = [j.id for j in s.get_jobs()]
    assert "market_refresh" in ids
    refresher.shutdown_scheduler()
    assert refresher._scheduler is None
