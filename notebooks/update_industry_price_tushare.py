#!/usr/bin/env python3
"""Fetch Shenwan Level 1 industry price indices from Tushare Pro."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import tushare as ts

DATA_DIR = Path(os.getenv("FEAR_GREED_DATA_DIR", "/workspace/data"))
OUTPUT_PATH = DATA_DIR / "industry_price_runtime.json"
REQUEST_INTERVAL = 0.15
MARKET_INDICES = [
    ("沪深300", "000300.SH"),
    ("中证500", "000905.SH"),
    ("中证1000", "000852.SH"),
    ("中证2000", "932000.CSI"),
    ("中证红利", "000922.CSI"),
    ("创业板指", "399006.SZ"),
    ("科创50", "000688.SH"),
]


def retry(name, request, attempts=4):
    for attempt in range(attempts):
        try:
            result = request()
            time.sleep(REQUEST_INTERVAL)
            return result
        except Exception as exc:
            if attempt == attempts - 1:
                raise RuntimeError(f"Tushare {name} failed: {exc}") from exc
            time.sleep(2**attempt)


def available_end_date():
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    date = now.date() if (now.hour, now.minute) >= (21, 0) else now.date() - timedelta(days=1)
    return date.strftime("%Y%m%d")


def period_return(closes, periods):
    if len(closes) <= periods:
        raise ValueError(f"need more than {periods} observations")
    return (float(closes.iloc[-1]) / float(closes.iloc[-periods - 1]) - 1) * 100


def summarize(frame, name, code):
    frame = frame.copy()
    frame["trade_date"] = frame["trade_date"].astype(str)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    frame = frame.dropna(subset=["close"]).sort_values("trade_date").drop_duplicates("trade_date")
    if len(frame) < 251:
        raise ValueError(f"{name} only returned {len(frame)} valid observations")

    latest = frame.iloc[-1]
    latest_year = str(latest["trade_date"])[:4]
    prior_year = frame[frame["trade_date"] < f"{latest_year}0101"]
    if prior_year.empty:
        raise ValueError(f"{name} has no prior-year close")

    closes = frame["close"].reset_index(drop=True)
    latest_amount = float(latest["amount"]) if pd.notna(latest["amount"]) else 0.0
    return {
        "name": name,
        "code": code,
        "date": datetime.strptime(str(latest["trade_date"]), "%Y%m%d").strftime("%Y-%m-%d"),
        "close": round(float(latest["close"]), 4),
        "week": round(period_return(closes, 5), 4),
        "month": round(period_return(closes, 21), 4),
        "ytd": round((float(latest["close"]) / float(prior_year.iloc[-1]["close"]) - 1) * 100, 4),
        "year": round(period_return(closes, 250), 4),
        "amount": round(latest_amount / 100000, 2),
        "sparkline": [
            {"date": datetime.strptime(str(row.trade_date), "%Y%m%d").strftime("%Y-%m-%d"), "close": round(float(row.close), 4)}
            for row in frame.tail(5).itertuples()
        ],
        "history": [
            {"date": datetime.strptime(str(row.trade_date), "%Y%m%d").strftime("%Y-%m-%d"), "close": round(float(row.close), 4)}
            for row in frame.tail(250).itertuples()
        ],
    }


def main():
    pro = ts.pro_api()
    classifications = retry(
        "申万一级行业分类",
        lambda: pro.index_classify(
            level="L1",
            src="SW2021",
            fields="index_code,industry_name,is_pub",
        ),
    )
    classifications = classifications[classifications["is_pub"].astype(str) == "1"].copy()
    if len(classifications) != 31:
        raise RuntimeError(f"Expected 31 published Shenwan Level 1 indices, received {len(classifications)}")

    end = available_end_date()
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=500)).strftime("%Y%m%d")
    rows = []
    for index, row in enumerate(classifications.itertuples(index=False), 1):
        frame = retry(
            row.industry_name,
            lambda code=row.index_code: pro.index_daily(
                ts_code=code,
                start_date=start,
                end_date=end,
                fields="ts_code,trade_date,close,amount",
            ),
        )
        rows.append(summarize(frame, row.industry_name, row.index_code))
        print(f"  [{index}/31] {rows[-1]['name']}: {rows[-1]['date']}", flush=True)

    market_indices = []
    for name, code in MARKET_INDICES:
        frame = retry(
            name,
            lambda code=code: pro.index_daily(
                ts_code=code,
                start_date=start,
                end_date=end,
                fields="ts_code,trade_date,close,amount",
            ),
        )
        market_indices.append(summarize(frame, name, code))
        print(f"  {name} 市场对照: {market_indices[-1]['date']}", flush=True)

    payload = {
        "asOf": max(row["date"] for row in [*rows, *market_indices]),
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "indices": rows,
        "marketIndices": market_indices,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"完成: {OUTPUT_PATH} ({len(rows)}项)", flush=True)


if __name__ == "__main__":
    main()
