"""Replicates the original web/tests/server.test.js suite against the FastAPI app.

Runs in file mode using the runtime JSON snapshots in data/ (already present).
"""

import pytest
from fastapi.testclient import TestClient

from web.app.dashboard import zone
from web.app.main import app
from web.app import auth, market_data

client = TestClient(app)


# ---------------------------------------------------------------------------
# zone boundaries (server.test.js #1)
# ---------------------------------------------------------------------------


def test_zone_boundaries_follow_notebook_definitions():
    assert zone(24.9) == "极度恐惧"
    assert zone(25) == "恐惧"
    assert zone(40) == "中性"
    assert zone(60) == "贪婪"
    assert zone(75) == "极度贪婪"


# ---------------------------------------------------------------------------
# WeChat authorize URL (server.test.js #2)
# ---------------------------------------------------------------------------


def test_wechat_authorize_url_uses_website_qr_login_and_callback_state(monkeypatch):
    from urllib.parse import urlparse, parse_qs
    monkeypatch.setattr(auth, "WECHAT_APP_ID", "", raising=False)
    url = auth.build_wechat_authorize_url("test-state")
    parsed = urlparse(url)
    assert parsed.netloc == "open.weixin.qq.com"
    assert parsed.path == "/connect/qrconnect"
    qs = parse_qs(parsed.query)
    assert qs["scope"] == ["snsapi_login"]
    assert qs["state"] == ["test-state"]


# ---------------------------------------------------------------------------
# market environment (server.test.js #3)
# ---------------------------------------------------------------------------


def test_market_environment_exact_seven_a_share_indices():
    result = market_data.market_environment()
    expected = [
        ["A股", "沪深300", "000300.SH"], ["A股", "中证500", "000905.SH"],
        ["A股", "中证1000", "000852.SH"], ["A股", "中证2000", "932000.CSI"],
        ["A股", "中证红利", "000922.CSI"], ["A股", "创业板指", "399006.SZ"],
        ["A股", "科创50", "000688.SH"],
        ["港股", "恒生指数", "HSI"], ["港股", "恒生科技", "HKTECH"],
        ["美股", "纳斯达克指数", "IXIC"], ["美股", "标普500", "SPX"],
    ]
    assert [[i["group"], i["name"], i["code"]] for i in result["indices"]] == expected
    assert all(isinstance(i[k], (int, float)) for i in result["indices"] for k in ("week", "month", "ytd", "year", "close"))
    assert all(len(i["sparkline"]) == 5 and all(isinstance(p["close"], (int, float)) for p in i["sparkline"]) for i in result["indices"])
    assert all(len(i["history"]) == 250 and all(_is_date(p["date"]) and isinstance(p["close"], (int, float)) for p in i["history"]) for i in result["indices"])


# ---------------------------------------------------------------------------
# market style (server.test.js #4)
# ---------------------------------------------------------------------------


def test_market_style_eight_complete_indices():
    result = market_data.market_style()
    expected_codes = ["399370.SZ", "399371.SZ", "399372.SZ", "399373.SZ", "399374.SZ", "399375.SZ", "399376.SZ", "399377.SZ"]
    assert [i["code"] for i in result["indices"]] == expected_codes
    assert all(i["group"] in ("全市场", "大盘", "中盘", "小盘") for i in result["indices"])
    assert all(isinstance(i[k], (int, float)) for i in result["indices"] for k in ("week", "month", "ytd", "year", "close"))
    assert all(len(i["sparkline"]) == 5 and len(i["history"]) == 250 for i in result["indices"])


# ---------------------------------------------------------------------------
# industry price (server.test.js #5)
# ---------------------------------------------------------------------------


def test_industry_price_retains_shenwan_level1():
    result = market_data.industry_price()
    assert len(result["indices"]) == 31
    assert all(re_match(r"^801\d{3}\.SI$", i["code"]) for i in result["indices"])
    assert all(isinstance(i[k], (int, float)) for i in result["indices"] for k in ("week", "month", "ytd", "year", "close", "amount"))
    assert all(len(i["sparkline"]) == 5 and len(i["history"]) == 250 for i in result["indices"])


# ---------------------------------------------------------------------------
# market volume (server.test.js #6)
# ---------------------------------------------------------------------------


def test_market_volume_five_buckets_and_250_days():
    result = market_data.market_volume()
    expected = [["沪深300", "000300.SH"], ["中证500", "000905.SH"], ["中证1000", "000852.SH"], ["中证2000", "932000.CSI"], ["3800以外", "OTHER"]]
    assert [[b["name"], b["code"]] for b in result["buckets"]] == expected
    assert len(result["history"]) == 250
    for b in result["buckets"]:
        for k in ("amount", "amountPercentile", "share", "sharePercentile"):
            assert isinstance(b[k], (int, float))
        assert 0 <= b["share"] <= 100 and 0 < b["amountPercentile"] <= 100 and 0 < b["sharePercentile"] <= 100
    for row in result["history"]:
        amounts = list(row["amounts"].values())
        shares = list(row["shares"].values())
        assert _is_date(row["date"])
        assert isinstance(row["total"], (int, float))
        assert len(amounts) == 5 and len(shares) == 5
        assert all(isinstance(v, (int, float)) for v in amounts)
        assert all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in shares)
        assert abs(sum(amounts) - row["total"]) < 0.02
        assert abs(sum(shares) - 100) < 0.02


# ---------------------------------------------------------------------------
# market volatility (server.test.js #7)
# ---------------------------------------------------------------------------


def test_market_volatility_exact_seven_index_and_component_histories():
    result = market_data.market_volatility()
    expected = [["沪深300", "000300.SH"], ["中证500", "000905.SH"], ["中证1000", "000852.SH"], ["中证2000", "932000.CSI"], ["中证红利", "000922.CSI"], ["创业板指", "399006.SZ"], ["科创50", "000688.SH"]]
    assert [[i["name"], i["code"]] for i in result["indexVolatility"]] == expected
    assert [[i["name"], i["code"]] for i in result["crossSectionVolatility"]] == expected
    for group in (result["indexVolatility"], result["crossSectionVolatility"]):
        assert all(len(i["history"]) == 250 for i in group)
        assert all(_is_date(p["date"]) and isinstance(p["value"], (int, float)) and p["value"] >= 0 for i in group for p in i["history"])


# ---------------------------------------------------------------------------
# market turnover (server.test.js #8)
# ---------------------------------------------------------------------------


def test_market_turnover_seven_complete_histories():
    result = market_data.market_turnover()
    expected = [["沪深300", "000300.SH"], ["中证500", "000905.SH"], ["中证1000", "000852.SH"], ["中证2000", "932000.CSI"], ["中证红利", "000922.CSI"], ["创业板指", "399006.SZ"], ["科创50", "000688.SH"]]
    assert [[i["name"], i["code"]] for i in result["indices"]] == expected
    for i in result["indices"]:
        for k in ("current", "weekAverage", "monthAverage", "percentile"):
            assert isinstance(i[k], (int, float))
        assert i["current"] >= 0 and 0 < i["percentile"] <= 100
        assert len(i["sparkline"]) == 5 and len(i["history"]) == 250
        assert all(_is_date(p["date"]) and isinstance(p["value"], (int, float)) and p["value"] >= 0 for p in i["history"])


# ---------------------------------------------------------------------------
# market breadth (server.test.js #9)
# ---------------------------------------------------------------------------


def test_market_breadth_seven_reconciled_distributions():
    result = market_data.market_breadth()
    expected = [["沪深300", "000300.SH"], ["中证500", "000905.SH"], ["中证1000", "000852.SH"], ["中证2000", "932000.CSI"], ["中证红利", "000922.CSI"], ["创业板指", "399006.SZ"], ["科创50", "000688.SH"]]
    assert [[g["name"], g["code"]] for g in result["groups"]] == expected
    for g in result["groups"]:
        assert isinstance(g["count"], int) and g["count"] > 0
        assert g["rise"] + g["flat"] + g["fall"] == g["count"]
        assert len(g["distribution"]) == 22
        assert all(isinstance(b["label"], str) and isinstance(b["count"], int) and b["count"] >= 0 for b in g["distribution"])
        assert sum(b["count"] for b in g["distribution"]) == g["count"]


# ---------------------------------------------------------------------------
# factor exposure (server.test.js #10)
# ---------------------------------------------------------------------------


def test_factor_exposure_cnlt_reference_set():
    result = market_data.factor_exposure()
    expected = ["size", "nonlinearSize", "beta", "momentum", "residualVolatility", "liquidity", "bookToPrice", "earningsYield", "growth", "dividendYield", "leverage", "earningsVariability", "earningsQuality", "profitability", "investmentQuality", "longTermReversal"]
    assert [f["key"] for f in result["factors"]] == expected
    assert len(result["indices"]) == 4
    assert len(result["distributions"]) == 16
    assert "非 MSCI Barra 官方模型" in result["model"]["disclaimer"]
    assert 1500 <= result["quality"]["universeCount"] <= 1900
    assert all(i["count"] >= 250 for i in result["indices"][:3])
    assert result["indices"][-1]["count"] == result["quality"]["universeCount"]
    assert result["quality"]["priceHistoryDays"] >= 1250
    for f in result["factors"]:
        assert isinstance(f["coverage"], (int, float)) and 0 <= f["coverage"] <= 1
    zero_factors = [f["key"] for f in result["factors"] if f["coverage"] == 0]
    for fk in zero_factors:
        assert all(i["exposures"][fk] is None for i in result["indices"])
    assert len(result["stocks"]) <= 500


# ---------------------------------------------------------------------------
# dashboard anonymous behavior via the HTTP endpoint (server.test.js #11)
# ---------------------------------------------------------------------------


def test_dashboard_hides_raw_values_for_anonymous_visitors():
    resp = client.get("/api/dashboard?range=1y")
    assert resp.status_code == 200
    result = resp.json()
    assert len(result["indicators"]) == 5
    assert all(i["value"] == 0 and i["average"] == 0 for i in result["indicators"])
    assert len(result["series"]) == 250
    assert 0 <= result["index"]["score"] <= 100
    assert all(isinstance(p["shanghai"], (int, float)) for p in result["series"])
    for key in ("qvix", "strength", "futures", "volume", "safety"):
        assert all(isinstance(p[key], (int, float)) for p in result["series"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


import re

_date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_date(value) -> bool:
    return isinstance(value, str) and bool(_date_re.fullmatch(value))


def re_match(pattern, value) -> bool:
    return isinstance(value, str) and re.compile(pattern).fullmatch(value) is not None
