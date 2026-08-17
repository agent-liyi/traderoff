"""Market data access + payload validation, ported from the Node server.js.

Backends:
- postgres: durable source (market_runtime_snapshots JSONB + market_fear_greed_daily)
- file:    runtime JSON files (testing / local)

Validation keeps the exact checks from the Node version so the pytest suite
mirrors the original node:test suite.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config

# ---------------------------------------------------------------------------
# Expected index/definition tables (identical to Node constants)
# ---------------------------------------------------------------------------

A_SHARE_INDEX_UNIVERSE = [
    ["沪深300", "000300.SH"],
    ["中证500", "000905.SH"],
    ["中证1000", "000852.SH"],
    ["中证2000", "932000.CSI"],
    ["中证红利", "000922.CSI"],
    ["创业板指", "399006.SZ"],
    ["科创50", "000688.SH"],
]

MARKET_ENVIRONMENT_INDICES = [
    *([["A股", name, code] for name, code in A_SHARE_INDEX_UNIVERSE]),
    ["港股", "恒生指数", "HSI"],
    ["港股", "恒生科技", "HKTECH"],
    ["美股", "纳斯达克指数", "IXIC"],
    ["美股", "标普500", "SPX"],
]

MARKET_VOLUME_BUCKETS = [
    ["沪深300", "000300.SH"],
    ["中证500", "000905.SH"],
    ["中证1000", "000852.SH"],
    ["中证2000", "932000.CSI"],
    ["3800以外", "OTHER"],
]

FACTOR_KEYS = [
    "size", "nonlinearSize", "beta", "momentum", "residualVolatility",
    "liquidity", "bookToPrice", "earningsYield", "growth", "dividendYield",
    "leverage", "earningsVariability", "earningsQuality", "profitability",
    "investmentQuality", "longTermReversal",
]

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MarketDataError(Exception):
    """A 503-able runtime/unavailable error. `message` is surfaced to clients."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(Exception):
    """A 500-able "data structurally invalid" error (message not exposed)."""


# ---------------------------------------------------------------------------
# Backend pool / snapshot read
# ---------------------------------------------------------------------------

def _connect():
    if not config.MARKET_DATABASE_URL:
        raise MarketDataError("行情数据库未配置")
    import psycopg  # lazy import keeps file backend dependency-light

    return psycopg.connect(config.MARKET_DATABASE_URL, connect_timeout=15)


def _snapshot_from_db(dataset: str) -> dict:
    try:
        conn = _connect()
    except MarketDataError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MarketDataError("行情数据库暂时不可用") from exc
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM market_runtime_snapshots WHERE dataset = %s",
                (dataset,),
            )
            row = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        raise MarketDataError("行情数据库暂时不可用") from exc
    finally:
        conn.close()
    if row is None:
        raise MarketDataError(f"{dataset} 行情快照尚未入库")
    return row[0]


def _snapshot_from_file(dataset: str) -> dict:
    path = Path(config.DATASET_FILES[dataset])
    return json.loads(path.read_text(encoding="utf-8"))


def market_snapshot(dataset: str) -> dict:
    """Read a snapshot payload from the active backend (mirrors marketSnapshot)."""
    if config.MARKET_DATA_BACKEND == "postgres":
        return _snapshot_from_db(dataset)
    return _snapshot_from_file(dataset)


# ---------------------------------------------------------------------------
# fear-greed daily rows
# ---------------------------------------------------------------------------

_rows_mtime = 0.0
_rows_cache = None


def _normalize_row(row: dict) -> dict:
    """Convert numeric DB/JSON values to Python numbers, keep str for date/zone."""
    out = {}
    for key, value in row.items():
        if key in ("date", "our_zone") or isinstance(value, str):
            out[key] = value
        else:
            out[key] = float(value or 0)
    return out


def load_rows() -> list[dict]:
    """Full fear-greed history, oldest->newest (mirrors loadRows with stat cache)."""
    global _rows_mtime, _rows_cache
    if config.MARKET_DATA_BACKEND == "postgres":
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT trade_date::text AS date, score_qvix AS "QVIX",
                      score_strength AS "股价强度", score_futures AS "期货升贴水",
                      score_volume AS "成交量", score_safety AS "避险需求",
                      our_index, our_zone, shanghai_index,
                      raw_qvix, raw_strength, raw_futures, raw_volume, raw_safety
                    FROM market_fear_greed_daily
                    ORDER BY trade_date
                    """
                )
                cols = [d.name for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        except Exception as exc:  # noqa: BLE001
            raise MarketDataError("行情数据库暂时不可用") from exc
        finally:
            conn.close()
        if not rows:
            raise MarketDataError("恐惧贪婪行情尚未入库")
        return [_normalize_row(r) for r in rows]

    path = Path(config.DATA_PATH)
    info = path.stat()
    if _rows_cache is None or info.st_mtime != _rows_mtime:
        _rows_cache = [
            _normalize_row(r)
            for r in json.loads(path.read_text(encoding="utf-8"))
        ]
        _rows_mtime = info.st_mtime
    return _rows_cache


# ---------------------------------------------------------------------------
# dataset validators (exact copies of Node checks)
# ---------------------------------------------------------------------------


def market_environment() -> dict:
    payload = market_snapshot("market-environment")
    indices = payload.get("indices")
    if not isinstance(indices, list) or len(indices) != len(MARKET_ENVIRONMENT_INDICES):
        raise ValidationError("市场环境数据不完整")
    for item, (group, name, code) in zip(indices, MARKET_ENVIRONMENT_INDICES):
        if (
            item.get("group") != group
            or item.get("name") != name
            or item.get("code") != code
            or len(item.get("history") or []) != 250
        ):
            raise ValidationError("市场环境指数定义不正确")
    return payload


def market_style() -> dict:
    payload = market_snapshot("market-style")
    indices = payload.get("indices")
    if not isinstance(indices, list) or len(indices) != 8:
        raise ValidationError("市场风格数据不完整")
    return payload


def industry_price() -> dict:
    payload = market_snapshot("industry-price")
    indices = payload.get("indices")
    if not isinstance(indices, list) or len(indices) != 31:
        raise ValidationError("行业价格指数数据不完整")
    return payload


def market_volume() -> dict:
    payload = market_snapshot("market-volume")
    buckets = payload.get("buckets")
    history = payload.get("history")
    if (
        not isinstance(buckets, list)
        or len(buckets) != len(MARKET_VOLUME_BUCKETS)
        or not isinstance(history, list)
        or len(history) != 250
    ):
        raise ValidationError("市场成交量数据不完整")
    for item, (name, code) in zip(buckets, MARKET_VOLUME_BUCKETS):
        if item.get("name") != name or item.get("code") != code:
            raise ValidationError("市场成交量桶定义不正确")
    return payload


def market_volatility() -> dict:
    payload = market_snapshot("market-volatility")
    iv = payload.get("indexVolatility")
    csv = payload.get("crossSectionVolatility")
    if (
        not isinstance(iv, list)
        or len(iv) != len(A_SHARE_INDEX_UNIVERSE)
        or not isinstance(csv, list)
        or len(csv) != len(A_SHARE_INDEX_UNIVERSE)
    ):
        raise ValidationError("市场波动率数据不完整")
    for group in (iv, csv):
        for item, (name, code) in zip(group, A_SHARE_INDEX_UNIVERSE):
            if (
                item.get("name") != name
                or item.get("code") != code
                or len(item.get("history") or []) != 250
            ):
                raise ValidationError("市场波动率指数定义不正确")
    return payload


def market_turnover() -> dict:
    payload = market_snapshot("market-turnover")
    indices = payload.get("indices")
    if not isinstance(indices, list) or len(indices) != len(A_SHARE_INDEX_UNIVERSE):
        raise ValidationError("市场换手率数据不完整")
    for item, (name, code) in zip(indices, A_SHARE_INDEX_UNIVERSE):
        if (
            item.get("name") != name
            or item.get("code") != code
            or len(item.get("history") or []) != 250
        ):
            raise ValidationError("市场换手率指数定义不正确")
    return payload


def market_breadth() -> dict:
    payload = market_snapshot("market-breadth")
    groups = payload.get("groups")
    if not isinstance(groups, list) or len(groups) != len(A_SHARE_INDEX_UNIVERSE):
        raise ValidationError("成分股涨跌分布数据不完整")
    for item, (name, code) in zip(groups, A_SHARE_INDEX_UNIVERSE):
        dist = item.get("distribution")
        if (
            item.get("name") != name
            or item.get("code") != code
            or not isinstance(dist, list)
            or len(dist) != 22
        ):
            raise ValidationError("成分股涨跌分布定义不正确")
        count = item.get("count", 0)
        if (
            item.get("rise", 0) + item.get("flat", 0) + item.get("fall", 0) != count
            or sum(int(bin.get("count", 0)) for bin in dist) != count
        ):
            raise ValidationError("成分股涨跌分布统计不完整")
    return payload


_factor_exposure_path_mtime = 0.0
_factor_exposure_cache = None


def factor_exposure() -> dict:
    global _factor_exposure_path_mtime, _factor_exposure_cache
    if config.MARKET_DATA_BACKEND != "postgres":
        path = Path(config.FACTOR_EXPOSURE_PATH)
        if not path.exists():
            raise MarketDataError("多因子快照尚未生成")
        info = path.stat()
        if _factor_exposure_cache is None or info.st_mtime != _factor_exposure_path_mtime:
            _factor_exposure_cache = json.loads(path.read_text(encoding="utf-8"))
            _factor_exposure_path_mtime = info.st_mtime

    payload = _factor_exposure_cache if config.MARKET_DATA_BACKEND != "postgres" else market_snapshot("factor-exposure")
    if payload.get("schemaVersion") != 1 or not _is_date(payload.get("asOf")):
        raise ValidationError("多因子数据版本或日期无效")

    factors = payload.get("factors")
    if not isinstance(factors, list) or len(factors) != 16:
        raise ValidationError("多因子定义不完整")
    for item, key in zip(factors, FACTOR_KEYS):
        coverage = item.get("coverage")
        if (
            item.get("key") != key
            or not isinstance(coverage, (int, float))
            or coverage < 0
            or coverage > 1
        ):
            raise ValidationError("多因子定义不完整")

    indices = payload.get("indices")
    if not isinstance(indices, list) or len(indices) != 4:
        raise ValidationError("多因子指数数据不完整")
    for item in indices:
        if not item.get("exposures") or not item.get("coverages"):
            raise ValidationError("多因子指数数据不完整")
        for key in FACTOR_KEYS:
            value = item["exposures"].get(key)
            if value is not None and not _is_finite_number(value):
                raise ValidationError("多因子指数数据不完整")

    distributions = payload.get("distributions")
    if not isinstance(distributions, list) or len(distributions) != 16:
        raise ValidationError("多因子分布数据不完整")
    for item, key in zip(distributions, FACTOR_KEYS):
        bins = item.get("bins")
        if (
            item.get("key") != key
            or not isinstance(bins, list)
            or len(bins) != 6
            or any(
                not isinstance(bin.get("label"), str)
                or not isinstance(bin.get("count"), int)
                or bin["count"] < 0
                for bin in bins
            )
        ):
            raise ValidationError("多因子分布数据不完整")

    if (
        not isinstance(payload.get("industries"), list)
        or not payload["industries"]
        or not isinstance(payload.get("stockTableFactors"), list)
        or any(k not in FACTOR_KEYS for k in payload["stockTableFactors"])
    ):
        raise ValidationError("多因子行业或明细定义不完整")

    model = payload.get("model") or {}
    quality = payload.get("quality") or {}
    if "非 MSCI Barra 官方模型" not in (model.get("disclaimer") or ""):
        raise ValidationError("多因子声明或质量信息不完整")
    if not isinstance(quality.get("warnings"), list):
        raise ValidationError("多因子声明或质量信息不完整")

    stocks = payload.get("stocks")
    if (
        not isinstance(stocks, list)
        or len(stocks) > 500
        or any(
            not isinstance(item.get("code"), str)
            or not isinstance(item.get("name"), str)
            or not item.get("exposures")
            for item in stocks
        )
        or not isinstance(payload.get("heatmap"), list)
    ):
        raise ValidationError("多因子明细数据无效")
    return payload


def _is_date(value) -> bool:
    return isinstance(value, str) and _DATE_RE.fullmatch(value) is not None


def _is_finite_number(value) -> bool:
    import math

    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float)) and math.isfinite(float(value))


import re

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
