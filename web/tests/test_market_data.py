"""Boundary/error tests for web/app/market_data.py validators.

Patch market_data.market_snapshot to feed structurally-invalid payloads and
assert each validator raises ValidationError (DB "unavailable" raises
MarketDataError). Also covers file-mode helpers and edge cases.
"""

import json
from pathlib import Path

import pytest

from web.app import config, market_data


# Helpers to build a "minimum valid" faked snapshot then corrupt specific parts.
def _env_payload():
    indices = [
        {"group": g, "name": n, "code": c, "history": [{"date": "2026-08-01", "close": 1.0}] * 250}
        for i, (g, n, c) in enumerate(market_data.MARKET_ENVIRONMENT_INDICES)
    ]
    return {"asOf": "2026-08-17", "indices": indices}


def _universe_items():
    return [
        {"name": n, "code": c, "history": [{"date": "2026-08-01", "value": 1.0}] * 250}
        for n, c in market_data.A_SHARE_INDEX_UNIVERSE
    ]


@pytest.fixture(autouse=True)
def _file_mode(monkeypatch):
    # conftest already forces MARKET_DATA_BACKEND=file and TRADEROFF_TEST;
    # just ensure the factor file path is a temp one per-test by default.
    yield


# ---------------------------------------------------------------------------
# market_environment
# ---------------------------------------------------------------------------


def test_environment_rejects_wrong_length(monkeypatch):
    bad = _env_payload()
    bad["indices"] = bad["indices"][:-1]
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: bad)
    with pytest.raises(market_data.ValidationError):
        market_data.market_environment()


def test_environment_rejects_wrong_definition(monkeypatch):
    bad = _env_payload()
    bad["indices"][0]["code"] = "WRONG.SH"
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: bad)
    with pytest.raises(market_data.ValidationError):
        market_data.market_environment()


def test_environment_accepts_valid(monkeypatch):
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: _env_payload())
    assert market_data.market_environment()["indices"]


# ---------------------------------------------------------------------------
# market_style
# ---------------------------------------------------------------------------


def test_style_rejects_not_eight(monkeypatch):
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: {"indices": [{"code": "x"}] * 7})
    with pytest.raises(market_data.ValidationError):
        market_data.market_style()


def test_style_accepts_eight(monkeypatch):
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: {"indices": [{"code": str(i)} for i in range(8)]})
    assert len(market_data.market_style()["indices"]) == 8


# ---------------------------------------------------------------------------
# industry_price
# ---------------------------------------------------------------------------


def test_industry_rejects_wrong_count(monkeypatch):
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: {"indices": []})
    with pytest.raises(market_data.ValidationError):
        market_data.industry_price()


def test_industry_accepts_31(monkeypatch):
    indices = [{"code": f"801{i:03d}.SI", "history": [], "name": str(i)} for i in range(31)]
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: {"indices": indices})
    assert len(market_data.industry_price()["indices"]) == 31


# ---------------------------------------------------------------------------
# market_volume
# ---------------------------------------------------------------------------


def test_volume_rejects_bad_buckets_or_history(monkeypatch):
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: {"buckets": [{"name": "x", "code": "y"}], "history": [{}] * 249})
    with pytest.raises(market_data.ValidationError):
        market_data.market_volume()


def test_volume_rejects_bad_bucket_order(monkeypatch):
    buckets = [{"name": n, "code": c} for n, c in market_data.MARKET_VOLUME_BUCKETS]
    buckets[0]["code"] = "BAD"
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: {"buckets": buckets, "history": [{}] * 250})
    with pytest.raises(market_data.ValidationError):
        market_data.market_volume()


# ---------------------------------------------------------------------------
# market_volatility
# ---------------------------------------------------------------------------


def test_volatility_rejects_group_mismatch(monkeypatch):
    n = len(market_data.A_SHARE_INDEX_UNIVERSE)
    iv = [{"name": n0, "code": c0, "history": []} for n0, c0 in market_data.A_SHARE_INDEX_UNIVERSE]
    csv = [{"name": n0, "code": "WRONG", "history": []} for n0, c0 in market_data.A_SHARE_INDEX_UNIVERSE]
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: {"indexVolatility": iv, "crossSectionVolatility": csv})
    with pytest.raises(market_data.ValidationError):
        market_data.market_volatility()


# ---------------------------------------------------------------------------
# market_turnover
# ---------------------------------------------------------------------------


def test_turnover_rejects_definition(monkeypatch):
    indices = [{"name": n0, "code": c0, "history": [{"date": "2026-08-01", "value": 1.0}] * 10} for n0, c0 in market_data.A_SHARE_INDEX_UNIVERSE]
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: {"indices": indices})
    with pytest.raises(market_data.ValidationError):
        market_data.market_turnover()  # history len != 250


# ---------------------------------------------------------------------------
# market_breadth
# ---------------------------------------------------------------------------


def test_breadth_rejects_unreconciled_counts(monkeypatch):
    groups = []
    for n0, c0 in market_data.A_SHARE_INDEX_UNIVERSE:
        groups.append({
            "name": n0, "code": c0, "count": 10, "rise": 3, "flat": 1, "fall": 5,
            "distribution": [{"label": f"b{i}", "count": 1} for i in range(22)],
        })
    # rise+flat+fall = 9 != count 10 -> reject
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: {"groups": groups})
    with pytest.raises(market_data.ValidationError):
        market_data.market_breadth()


# ---------------------------------------------------------------------------
# factor_exposure
# ---------------------------------------------------------------------------


def _valid_factor_payload():
    def bin_(i):
        return {"label": f"g{i}", "count": 1}

    return {
        "schemaVersion": 1, "asOf": "2026-08-12",
        "factors": [{"key": k, "coverage": 0.5} for k in market_data.FACTOR_KEYS],
        "indices": [{"name": f"ix{i}", "exposures": {k: 0.0 for k in market_data.FACTOR_KEYS}, "coverages": {k: 1.0 for k in market_data.FACTOR_KEYS}} for i in range(4)],
        "distributions": [{"key": k, "bins": [bin_(i) for i in range(6)]} for k in market_data.FACTOR_KEYS],
        "industries": [{"name": "银行"}],
        "stockTableFactors": ["size"],
        "model": {"disclaimer": "非 MSCI Barra 官方模型"},
        "quality": {"warnings": [], "universeCount": 1800},
        "stocks": [{"code": "000001.SZ", "name": "平安", "exposures": {"size": 0.1}}],
        "heatmap": [],
    }


def _factor_via_market_snapshot(monkeypatch, payload):
    # Force factor_exposure to use market_snapshot (the postgres path) so we can
    # feed a crafted payload instead of reading a real file.
    monkeypatch.setattr(config, "MARKET_DATA_BACKEND", "postgres")
    monkeypatch.setattr(market_data, "market_snapshot", lambda ds: payload)
    return lambda: market_data.factor_exposure()


def test_factor_rejects_bad_schema_version(monkeypatch):
    bad = _valid_factor_payload(); bad["schemaVersion"] = 2
    _factor_via_market_snapshot(monkeypatch, bad)
    with pytest.raises(market_data.ValidationError):
        market_data.factor_exposure()


def test_factor_rejects_bad_asof(monkeypatch):
    bad = _valid_factor_payload(); bad["asOf"] = "not-a-date"
    _factor_via_market_snapshot(monkeypatch, bad)
    with pytest.raises(market_data.ValidationError):
        market_data.factor_exposure()


def test_factor_rejects_wrong_factor_count(monkeypatch):
    bad = _valid_factor_payload(); bad["factors"] = bad["factors"][:-1]
    _factor_via_market_snapshot(monkeypatch, bad)
    with pytest.raises(market_data.ValidationError):
        market_data.factor_exposure()


def test_factor_rejects_bad_coverage_range(monkeypatch):
    bad = _valid_factor_payload(); bad["factors"][0]["coverage"] = 2.0
    _factor_via_market_snapshot(monkeypatch, bad)
    with pytest.raises(market_data.ValidationError):
        market_data.factor_exposure()


def test_factor_rejects_bad_index_exposure(monkeypatch):
    bad = _valid_factor_payload(); bad["indices"][0]["exposures"]["size"] = "oops"
    _factor_via_market_snapshot(monkeypatch, bad)
    with pytest.raises(market_data.ValidationError):
        market_data.factor_exposure()


def test_factor_rejects_bad_distribution(monkeypatch):
    bad = _valid_factor_payload(); bad["distributions"][0]["bins"] = [{"label": "x", "count": 1}]
    _factor_via_market_snapshot(monkeypatch, bad)
    with pytest.raises(market_data.ValidationError):
        market_data.factor_exposure()


def test_factor_rejects_missing_disclaimer(monkeypatch):
    bad = _valid_factor_payload(); bad["model"] = {"disclaimer": "别的声明"}
    _factor_via_market_snapshot(monkeypatch, bad)
    with pytest.raises(market_data.ValidationError):
        market_data.factor_exposure()


def test_factor_accepts_valid_payload(monkeypatch):
    _factor_via_market_snapshot(monkeypatch, _valid_factor_payload())
    assert market_data.factor_exposure()["asOf"] == "2026-08-12"


def test_factor_file_missing_raises_market_error(monkeypatch):
    monkeypatch.setattr(config, "MARKET_DATA_BACKEND", "file")
    monkeypatch.setattr(config, "FACTOR_EXPOSURE_PATH", str(Path("__absent__/none.json")))
    with pytest.raises(market_data.MarketDataError):
        market_data.factor_exposure()


# ---------------------------------------------------------------------------
# load_rows (file mode) + normalization
# ---------------------------------------------------------------------------


def test_load_rows_normalizes_numeric_and_keeps_dates(monkeypatch, tmp_path):
    p = tmp_path / "fg.json"
    p.write_text(json.dumps([
        {"date": "2026-08-12", "our_index": 26.64, "our_zone": "恐惧", "shanghai_index": 3946.67, "QVIX": 12},
    ]), encoding="utf-8")
    monkeypatch.setattr(config, "DATA_PATH", str(p))
    monkeypatch.setattr(market_data, "_rows_cache", None)
    rows = market_data.load_rows()
    assert rows[0]["our_index"] == 26.64
    assert rows[0]["our_zone"] == "恐惧"
    assert rows[0]["QVIX"] == 12


def test_load_rows_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setattr(market_data, "_rows_cache", None)
    with pytest.raises(FileNotFoundError):
        market_data.load_rows()
