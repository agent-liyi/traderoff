#!/usr/bin/env python3
"""Build A-share size-bucket turnover data from Tushare Pro daily data."""

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
RAW_DIR = DATA_DIR / "tushare_raw"
OUTPUT_PATH = DATA_DIR / "market_volume_runtime.json"
START_DATE = "20231001"
LOOKBACK = 250
REQUEST_INTERVAL = 0.13
BUCKETS = [
    ("沪深300", "000300.SH"),
    ("中证500", "000905.SH"),
    ("中证1000", "000852.SH"),
    ("中证2000", "932000.CSI"),
    ("3800以外", "OTHER"),
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


def latest_open_date(pro):
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    requested = (now.date() if (now.hour, now.minute) >= (21, 0) else now.date() - timedelta(days=1)).strftime("%Y%m%d")
    calendar = retry("trade_cal", lambda: pro.trade_cal(exchange="SSE", end_date=requested, is_open="1", fields="cal_date"))
    if calendar.empty:
        raise RuntimeError("No open trading date returned by Tushare")
    return str(calendar["cal_date"].max())


def trading_dates(pro, end_date):
    calendar = retry(
        "trade_cal",
        lambda: pro.trade_cal(exchange="SSE", start_date=START_DATE, end_date=end_date, is_open="1", fields="cal_date"),
    )
    dates = sorted(calendar["cal_date"].astype(str).tolist())
    if len(dates) < LOOKBACK:
        raise RuntimeError(f"Need at least {LOOKBACK} trading days, got {len(dates)}")
    return dates


def daily_cache_path(date):
    path = RAW_DIR / "equity_daily"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{date}.csv.gz"


def fetch_daily_amounts(pro, dates):
    frames = []
    for index, date in enumerate(dates, 1):
        path = daily_cache_path(date)
        frame = None
        if path.exists():
            try:
                frame = pd.read_csv(path, dtype={"ts_code": str, "trade_date": str})
            except (OSError, pd.errors.EmptyDataError, ValueError):
                path.unlink(missing_ok=True)
        if frame is None or frame.empty or "amount" not in frame.columns:
            frame = retry(
                f"daily {date}",
                lambda date=date: pro.daily(trade_date=date, fields="ts_code,trade_date,amount"),
            )
            if frame.empty:
                raise RuntimeError(f"No daily amount data for {date}")
            frame.to_csv(path, index=False, compression="gzip")
        if frame.empty or "amount" not in frame.columns:
            raise RuntimeError(f"No daily amount data for {date}")
        frames.append(frame[["ts_code", "trade_date", "amount"]])
        if index % 50 == 0 or index == len(dates):
            print(f"  股票日线 {index}/{len(dates)}", flush=True)
    data = pd.concat(frames, ignore_index=True)
    data["trade_date"] = data["trade_date"].astype(str)
    data["amount"] = pd.to_numeric(data["amount"], errors="coerce")
    data = data[data["ts_code"].str.endswith((".SH", ".SZ"), na=False)].dropna(subset=["amount"])
    if data.empty:
        raise RuntimeError("No Shanghai or Shenzhen stock daily amount data available")
    return data


def month_windows(start_date, end_date):
    current = datetime.strptime(start_date, "%Y%m%d").replace(day=1)
    end = datetime.strptime(end_date, "%Y%m%d")
    while current <= end:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield current.strftime("%Y%m%d"), min(next_month - timedelta(days=1), end).strftime("%Y%m%d")
        current = next_month


def fetch_memberships(pro, end_date):
    snapshots = {}
    for name, code in BUCKETS[:-1]:
        frames = []
        for start_date, window_end in month_windows("20230901", end_date):
            frame = retry(
                f"index_weight {code} {start_date}-{window_end}",
                lambda code=code, start_date=start_date, window_end=window_end: pro.index_weight(
                    index_code=code,
                    start_date=start_date,
                    end_date=window_end,
                    fields="index_code,con_code,trade_date,weight",
                ),
            )
            if not frame.empty:
                frames.append(frame)
        if not frames:
            raise RuntimeError(f"No index membership snapshots returned for {name}")
        frame = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["con_code", "trade_date"])
        frame["trade_date"] = frame["trade_date"].astype(str)
        snapshots[code] = {
            date: set(day["con_code"].dropna().astype(str))
            for date, day in frame.groupby("trade_date")
        }
        snapshot_dates = sorted(snapshots[code])
        prior_dates = [date for date in snapshot_dates if date <= START_DATE]
        if not prior_dates:
            raise RuntimeError(f"No {name} membership snapshot on or before {START_DATE}")
        print(
            f"  {name} 成分快照 {len(snapshot_dates)} 个 ({snapshot_dates[0]} - {snapshot_dates[-1]}; "
            f"{max(prior_dates)} 覆盖起点)",
            flush=True,
        )
    return snapshots


def membership_for_date(snapshots, trade_date):
    memberships = {}
    for _, code in BUCKETS[:-1]:
        dates = [date for date in snapshots[code] if date <= trade_date]
        if not dates:
            raise RuntimeError(f"No {code} membership snapshot on or before {trade_date}")
        memberships[code] = snapshots[code][max(dates)]
    return memberships


def inclusive_percentile(values):
    return values.rank(method="max", pct=True) * 100


def build_payload(pro):
    end_date = latest_open_date(pro)
    dates = trading_dates(pro, end_date)
    print(f"Tushare-only update: {dates[0]} - {dates[-1]} ({len(dates)} days)", flush=True)
    print("[1/3] 获取沪深股票日成交额", flush=True)
    daily = fetch_daily_amounts(pro, dates)
    print("[2/3] 获取指数月度成分快照", flush=True)
    snapshots = fetch_memberships(pro, end_date)

    print("[3/3] 归类、校验并计算分位值", flush=True)
    history = []
    for date, day in daily.groupby("trade_date", sort=True):
        memberships = membership_for_date(snapshots, date)
        assigned = pd.Series("OTHER", index=day.index, dtype="object")
        used = set()
        for _, code in BUCKETS[:-1]:
            members = memberships[code] - used
            assigned.loc[day["ts_code"].isin(members)] = code
            used.update(members)
        amounts = day.assign(bucket=assigned).groupby("bucket")["amount"].sum()
        raw_amounts = {code: float(amounts.get(code, 0.0)) for _, code in BUCKETS}
        total = float(day["amount"].sum())
        if abs(sum(raw_amounts.values()) - total) > max(1e-6, total * 1e-12):
            raise RuntimeError(f"Bucket amount reconciliation failed for {date}")
        history.append({"date": datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d"), "total": total, "amounts": raw_amounts})

    frame = pd.DataFrame(
        [{"date": row["date"], **row["amounts"], "total": row["total"]} for row in history]
    ).sort_values("date")
    for _, code in BUCKETS:
        frame[f"{code}_share"] = frame[code] / frame["total"] * 100
        frame[f"{code}_amount_percentile"] = inclusive_percentile(frame[code])
        frame[f"{code}_share_percentile"] = inclusive_percentile(frame[f"{code}_share"])

    latest = frame.iloc[-1]
    summary = [
        {
            "name": name,
            "code": code,
            "amount": round(float(latest[code]) / 100000, 4),
            "amountPercentile": round(float(latest[f"{code}_amount_percentile"]), 4),
            "share": round(float(latest[f"{code}_share"]), 4),
            "sharePercentile": round(float(latest[f"{code}_share_percentile"]), 4),
        }
        for name, code in BUCKETS
    ]
    trend = [
        {
            "date": row["date"],
            "total": round(float(row["total"]) / 100000, 4),
            "amounts": {code: round(float(row[code]) / 100000, 4) for _, code in BUCKETS},
            "shares": {code: round(float(row[f"{code}_share"]), 4) for _, code in BUCKETS},
        }
        for _, row in frame.tail(LOOKBACK).iterrows()
    ]
    return {
        "asOf": latest["date"],
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "startDate": frame.iloc[0]["date"],
        "percentileMethod": "inclusive rank: count of values less than or equal to the current value divided by all available trading days",
        "buckets": summary,
        "history": trend,
    }


def main():
    payload = build_payload(ts.pro_api())
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"完成: {OUTPUT_PATH} ({len(payload['history'])}个交易日)", flush=True)


if __name__ == "__main__":
    main()
