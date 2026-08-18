"""Pytest fixtures: off-line, self-contained test environment.

- Forces the file market-data backend.
- Points every market-data JSON path at a temp dir filled with minimal
  snapshots that satisfy the structure assertions used by the tests, so the
  suite runs without any real `data/*.json` (CI-friendly).
- Isolates the users sqlite per test run.
"""

import json
import os
import sys
from pathlib import Path

# Must be set before importing web.app.config.
os.environ.setdefault("MARKET_DATA_BACKEND", "file")
os.environ.setdefault("TRADEROFF_TEST", "1")

# Isolate the users sqlite per test run.
_web_root = Path(__file__).resolve().parents[1]
os.environ.setdefault("USERS_DB", str(_web_root / "data" / "users.test.sqlite"))

# Ensure the project root is importable (web.app package).
_ROOT = _web_root.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402

from web.app import config, market_data  # noqa: E402

_DATES = [f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}" for i in range(250)]


def _spark(points=5):
    return [{"date": _DATES[i], "close": 100.0 + i} for i in range(points)]

ENV_GROUPS = [
    ["A股", "沪深300", "000300.SH"], ["A股", "中证500", "000905.SH"],
    ["A股", "中证1000", "000852.SH"], ["A股", "中证2000", "932000.CSI"],
    ["A股", "中证红利", "000922.CSI"], ["A股", "创业板指", "399006.SZ"],
    ["A股", "科创50", "000688.SH"],
    ["港股", "恒生指数", "HSI"], ["港股", "恒生科技", "HKTECH"],
    ["美股", "纳斯达克指数", "IXIC"], ["美股", "标普500", "SPX"],
]
STYLE_CODES = ["399370.SZ", "399371.SZ", "399372.SZ", "399373.SZ", "399374.SZ", "399375.SZ", "399376.SZ", "399377.SZ"]
UNIVERSE = [["沪深300", "000300.SH"], ["中证500", "000905.SH"], ["中证1000", "000852.SH"],
            ["中证2000", "932000.CSI"], ["中证红利", "000922.CSI"], ["创业板指", "399006.SZ"], ["科创50", "000688.SH"]]


def _make_env_payload():
    return {"asOf": "2026-08-17", "indices": [
        {"group": g, "name": n, "code": c, "date": _DATES[-1], "close": 100.0,
         "week": 1.0, "month": 2.0, "ytd": 3.0, "year": 4.0, "sparkline": _spark(),
         "history": [{"date": _DATES[i], "close": 100.0 + i} for i in range(250)]}
        for g, n, c in ENV_GROUPS
    ]}


def _make_style_payload():
    return {"asOf": "2026-08-17", "indices": [
        {"group": ("全市场" if i == 0 else "大盘" if i < 3 else "中盘" if i < 5 else "小盘"),
         "name": f"风格{i}", "code": STYLE_CODES[i], "date": _DATES[-1], "close": 100.0,
         "week": 1.0, "month": 2.0, "ytd": 3.0, "year": 4.0, "sparkline": _spark(),
         "history": [{"date": _DATES[ii], "close": 100.0 + ii} for ii in range(250)]}
        for i in range(8)
    ]}


def _make_industry_payload():
    return {"asOf": "2026-08-17", "indices": [
        {"code": f"801{i:03d}.SI", "name": f"行业{i}", "date": _DATES[-1], "close": 100.0,
         "week": 1.0, "month": 2.0, "ytd": 3.0, "year": 4.0, "amount": 1.0,
         "sparkline": _spark(),
         "history": [{"date": _DATES[ii], "close": 100.0 + ii} for ii in range(250)]}
        for i in range(31)
    ]}


def _make_volume_payload():
    buckets = [{"name": n, "code": c, "amount": 100.0, "amountPercentile": 50.0,
                "share": 20.0, "sharePercentile": 40.0} for n, c in
               [["沪深300", "000300.SH"], ["中证500", "000905.SH"], ["中证1000", "000852.SH"],
                ["中证2000", "932000.CSI"], ["3800以外", "OTHER"]]]
    history = [{
        "date": _DATES[i], "total": 500.0,
        "amounts": {"000300.SH": 100.0, "000905.SH": 100.0, "000852.SH": 100.0, "932000.CSI": 100.0, "OTHER": 100.0},
        "shares": {"000300.SH": 20.0, "000905.SH": 20.0, "000852.SH": 20.0, "932000.CSI": 20.0, "OTHER": 20.0},
    } for i in range(250)]
    return {"asOf": "2026-08-17", "buckets": buckets, "history": history}


def _make_volatility_payload():
    groups = [{"name": n, "code": c, "history": [{"date": _DATES[i], "value": 1.0 + (i % 10)} for i in range(250)]}
              for n, c in UNIVERSE]
    return {"asOf": "2026-08-17", "indexVolatility": groups, "crossSectionVolatility": groups}


def _make_turnover_payload():
    return {"asOf": "2026-08-17", "indices": [
        {"name": n, "code": c, "current": 1.0, "weekAverage": 2.0, "monthAverage": 3.0,
         "percentile": 50.0, "sparkline": [{"date": _DATES[i], "value": 1.0} for i in range(5)],
         "history": [{"date": _DATES[i], "value": 1.0 + (i % 5)} for i in range(250)]}
        for n, c in UNIVERSE
    ]}


def _make_breadth_payload():
    return {"asOf": "2026-08-17", "groups": [
        {"name": n, "code": c, "count": 22, "rise": 10, "flat": 4, "fall": 8,
         "distribution": [{"label": f"r{i}", "count": 1} for i in range(22)]}
        for n, c in UNIVERSE
    ]}


def _make_factor_payload():
    keys = ["size", "nonlinearSize", "beta", "momentum", "residualVolatility", "liquidity",
            "bookToPrice", "earningsYield", "growth", "dividendYield", "leverage",
            "earningsVariability", "earningsQuality", "profitability", "investmentQuality", "longTermReversal"]
    return {
        "schemaVersion": 1, "asOf": "2026-08-12",
        "factors": [{"key": k, "coverage": 0.5} for k in keys],
        "indices": [{"name": f"ix{i}", "count": 1800 if i == 3 else 1800 + i,
                     "exposures": {k: 0.0 for k in keys}, "coverages": {k: 1.0 for k in keys}} for i in range(4)],
        "distributions": [{"key": k, "bins": [{"label": f"g{j}", "count": 1} for j in range(6)]} for k in keys],
        "industries": [{"name": "银行"}],
        "stockTableFactors": ["size"],
        "model": {"disclaimer": "非 MSCI Barra 官方模型"},
        "quality": {"warnings": [], "universeCount": 1800, "priceHistoryDays": 1250},
        "stocks": [{"code": "000001.SZ", "name": "平安", "industry": "银行", "exposures": {"size": 0.1}, "marketCap": 1e9}],
        "heatmap": [],
    }


def _make_fear_greed_payload():
    return [{
        "date": _DATES[i], "QVIX": 50.0, "股价强度": 50.0, "期货升贴水": 50.0,
        "成交量": 50.0, "避险需求": 50.0, "our_index": 50.0, "our_zone": "中性",
        "shanghai_index": 3000.0, "raw_qvix": 15.0, "raw_strength": 0.5,
        "raw_futures": -5.0, "raw_volume": 0.1, "raw_safety": 0.01,
    } for i in range(250)]


_FIXTURES = {
    "market-environment": _make_env_payload,
    "market-style": _make_style_payload,
    "industry-price": _make_industry_payload,
    "market-volume": _make_volume_payload,
    "market-volatility": _make_volatility_payload,
    "market-turnover": _make_turnover_payload,
    "market-breadth": _make_breadth_payload,
    "factor-exposure": _make_factor_payload,
    "fear-greed": _make_fear_greed_payload,
}


@pytest.fixture(autouse=True, scope="session")
def _market_data_fixtures():
    """Write minimal in-memory snapshots to a temp dir used as the data backend."""
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="tr-test-data-"))
    config.DATA_PATH = str(tmp / "fear_greed_runtime.json")
    mapping = {
        "market-environment": "market_environment_runtime.json",
        "market-style": "market_style_runtime.json",
        "industry-price": "industry_price_runtime.json",
        "market-volume": "market_volume_runtime.json",
        "market-volatility": "market_volatility_runtime.json",
        "market-turnover": "market_turnover_runtime.json",
        "market-breadth": "market_breadth_runtime.json",
        "factor-exposure": "factor_exposure_runtime.json",
    }
    (tmp / "tushare_raw").mkdir(parents=True, exist_ok=True)
    for dataset, fname in mapping.items():
        payload = _FIXTURES[dataset]()
        (tmp / fname).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        config.DATASET_FILES[dataset] = str(tmp / fname)
    config.FACTOR_EXPOSURE_PATH = str(tmp / mapping["factor-exposure"])
    # fear-greed (dashboard) file
    (tmp / "fear_greed_runtime.json").write_text(
        json.dumps(_FIXTURES["fear-greed"](), ensure_ascii=False), encoding="utf-8"
    )
    # reset market_data caches so they re-read from the temp files
    market_data._rows_cache = None
    market_data._factor_exposure_cache = None
    market_data._factor_exposure_path_mtime = 0.0
    yield tmp
