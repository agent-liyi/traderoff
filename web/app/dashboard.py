"""Dashboard aggregation logic, ported 1:1 from the Node server.js.

Includes the INDICATORS metadata, zone mapping, range selection, summarization,
and the anonymous-visitor synthetic-series masking.
"""

from __future__ import annotations

import math
from typing import Any

from . import market_data

# ---------------------------------------------------------------------------
# INDICATORS metadata (identical to Node)
# ---------------------------------------------------------------------------
INDICATORS = {
    "qvix": {
        "rawColumn": "raw_qvix", "factor": 1, "precision": 2, "unit": "%",
        "name": "QVIX 波动率", "short": "50ETF QVIX", "color": "#5AAEF3",
        "direction": "反向指标", "source": "Tushare · 50ETF期权链",
        "description": "按照 QVIX 方差互换口径综合近月、次月和不同行权价的 50ETF 期权，直接显示年化隐含波动率。",
    },
    "strength": {
        "rawColumn": "raw_strength", "factor": 1, "precision": 2, "unit": "%",
        "name": "股价强度", "short": "250日新高占比", "color": "#333333",
        "direction": "正向指标", "source": "Tushare · A股日线",
        "description": "直接显示全市场收盘价创 250 日新高的股票数量占当日股票总数的比例。",
    },
    "futures": {
        "rawColumn": "raw_futures", "factor": 1, "precision": 2, "unit": "%",
        "name": "期货升贴水", "short": "IF 次月", "color": "#E65A56",
        "direction": "正向指标", "source": "Tushare · IF期货与沪深300",
        "description": "直接显示 IF 次月合约相对沪深 300 的年化升贴水率，经 10 个交易日移动平均。",
    },
    "volume": {
        "rawColumn": "raw_volume", "factor": 100, "precision": 2, "unit": "%",
        "name": "成交量偏离", "short": "沪深全市场", "color": "#6D61E4",
        "direction": "正向指标", "source": "Tushare · 沪深A股日线汇总",
        "description": "直接显示沪深两市 A 股总成交量相对 20 日移动平均成交量的偏离比例。",
    },
    "safety": {
        "rawColumn": "raw_safety", "factor": 100, "precision": 2, "unit": "%",
        "name": "避险需求", "short": "股债收益差", "color": "#30CB13",
        "direction": "正向指标", "source": "Tushare · 沪深300与中债综合指数",
        "description": "直接显示沪深 300 的 20 日收益率减去中债综合指数 20 日收益率。",
    },
}


def zone(score: float) -> str:
    if score < 25:
        return "极度恐惧"
    if score < 40:
        return "恐惧"
    if score < 60:
        return "中性"
    if score < 75:
        return "贪婪"
    return "极度贪婪"


RANGE_SIZES = {"6m": 126, "1y": 250, "3y": 750, "all": 1250}


def range_rows(all_rows: list[dict], range_: str) -> list[dict]:
    size = RANGE_SIZES.get(range_) or 250
    return all_rows[-min(size, len(all_rows)):]


def summarize(values: list[float]) -> dict:
    valid = [v for v in values if math.isfinite(float(v))]
    if not valid:
        return {"min": 0, "max": 0, "average": 0}
    return {
        "min": min(valid),
        "max": max(valid),
        "average": sum(valid) / len(valid),
    }


def _indicator_value(row: dict, meta: dict) -> float:
    return row[meta["rawColumn"]] * meta["factor"]


def dashboard(range_: str = "1y", user: Any = None) -> dict:
    all_rows = market_data.load_rows()
    selected = range_rows(all_rows, range_)
    current = all_rows[-1]
    previous = all_rows[-2]

    indicators = []
    for key, meta in INDICATORS.items():
        value = _indicator_value(current, meta)
        selected_values = [_indicator_value(r, meta) for r in selected]
        indicators.append({
            "key": key, **meta, "value": value, "change": value - _indicator_value(previous, meta),
            **summarize(selected_values),
        })

    anonymous = user is None
    indicator_series = []
    for index, row in enumerate(selected):
        point = {"date": row["date"], "index": row["our_index"], "shanghai": row["shanghai_index"]}
        if not anonymous:
            point.update({
                "qvix": row["raw_qvix"],
                "strength": row["raw_strength"],
                "futures": row["raw_futures"],
                "volume": row["raw_volume"] * 100,
                "safety": row["raw_safety"] * 100,
            })
        else:
            point.update({
                "qvix": 18 + math.sin(index / 8),
                "strength": 1 + math.sin(index / 10),
                "futures": -8 + math.sin(index / 9),
                "volume": math.sin(index / 7) * 5,
                "safety": math.sin(index / 11) * 4,
            })
        indicator_series.append(point)

    return {
        "asOf": current["date"],
        "index": {
            "score": current["our_index"],
            "change": current["our_index"] - previous["our_index"],
            "zone": zone(current["our_index"]),
        },
        "indicators": (indicators if not anonymous
                       else [{"key": k, **meta, "value": 0, "change": 0,
                              "average": 0, "min": 0, "max": 0}
                             for k, meta in INDICATORS.items()]),
        "series": indicator_series,
    }
