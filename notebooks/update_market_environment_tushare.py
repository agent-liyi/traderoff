#!/usr/bin/env python3
"""Fetch major index performance from Tushare for the market environment view."""

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
OUTPUT_PATH = DATA_DIR / "market_environment_runtime.json"
REQUEST_INTERVAL = 0.15

A_SHARE = [
    ("A股", "上证50", "000016.SH"),
    ("A股", "沪深300", "000300.SH"),
    ("A股", "中证500", "000905.SH"),
    ("A股", "中证1000", "000852.SH"),
    ("A股", "中证2000", "932000.CSI"),
    ("A股", "创业板指", "399006.SZ"),
    ("A股", "科创50", "000688.SH"),
    ("A股", "中证红利指数", "000922.CSI"),
]
GLOBAL = [
    ("港股", "恒生指数", "HSI"),
    ("港股", "恒生科技", "HKTECH"),
    ("美股", "纳斯达克指数", "IXIC"),
    ("美股", "标普500", "SPX"),
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


def summarize(frame, group, name, code):
    frame = frame.copy()
    frame["trade_date"] = frame["trade_date"].astype(str)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["close"]).sort_values("trade_date").drop_duplicates("trade_date")
    if len(frame) < 251:
        raise ValueError(f"{name} only returned {len(frame)} valid observations")

    latest = frame.iloc[-1]
    latest_year = str(latest["trade_date"])[:4]
    prior_year = frame[frame["trade_date"] < f"{latest_year}0101"]
    if prior_year.empty:
        raise ValueError(f"{name} has no prior-year close")

    closes = frame["close"].reset_index(drop=True)
    spark = frame.tail(5)
    history = frame.tail(250)
    return {
        "group": group,
        "name": name,
        "code": code,
        "date": datetime.strptime(str(latest["trade_date"]), "%Y%m%d").strftime("%Y-%m-%d"),
        "close": round(float(latest["close"]), 4),
        "week": round(period_return(closes, 5), 4),
        "month": round(period_return(closes, 21), 4),
        "ytd": round((float(latest["close"]) / float(prior_year.iloc[-1]["close"]) - 1) * 100, 4),
        "year": round(period_return(closes, 250), 4),
        "sparkline": [
            {"date": datetime.strptime(str(row.trade_date), "%Y%m%d").strftime("%Y-%m-%d"), "close": round(float(row.close), 4)}
            for row in spark.itertuples()
        ],
        "history": [
            {"date": datetime.strptime(str(row.trade_date), "%Y%m%d").strftime("%Y-%m-%d"), "close": round(float(row.close), 4)}
            for row in history.itertuples()
        ],
    }


def main():
    pro = ts.pro_api()
    end = available_end_date()
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=500)).strftime("%Y%m%d")
    rows = []

    for group, name, code in A_SHARE:
        frame = retry(name, lambda code=code: pro.index_daily(ts_code=code, start_date=start, end_date=end, fields="ts_code,trade_date,close"))
        rows.append(summarize(frame, group, name, code))
        print(f"  {name}: {rows[-1]['date']}", flush=True)

    for group, name, code in GLOBAL:
        frame = retry(name, lambda code=code: pro.index_global(ts_code=code, start_date=start, end_date=end, fields="ts_code,trade_date,close"))
        rows.append(summarize(frame, group, name, code))
        print(f"  {name}: {rows[-1]['date']}", flush=True)

    payload = {
        "asOf": max(row["date"] for row in rows),
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "indices": rows,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"完成: {OUTPUT_PATH} ({len(rows)}项)", flush=True)


if __name__ == "__main__":
    main()
