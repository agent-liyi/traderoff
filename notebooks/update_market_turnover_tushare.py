#!/usr/bin/env python3
"""Build comparable constituent free-float turnover histories from Tushare Pro."""

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
OUTPUT_PATH = DATA_DIR / "market_turnover_runtime.json"
LOOKBACK = 250
REQUEST_INTERVAL = 0.13
INDICES = [
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


def latest_open_date(pro):
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    requested = (now.date() if (now.hour, now.minute) >= (21, 0) else now.date() - timedelta(days=1)).strftime("%Y%m%d")
    frame = retry("trade_cal", lambda: pro.trade_cal(exchange="SSE", end_date=requested, is_open="1", fields="cal_date"))
    if frame.empty:
        raise RuntimeError("No open trading date returned by Tushare")
    return str(frame["cal_date"].max())


def trade_dates(pro, end_date):
    start = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=400)).strftime("%Y%m%d")
    frame = retry("trade_cal", lambda: pro.trade_cal(exchange="SSE", start_date=start, end_date=end_date, is_open="1", fields="cal_date"))
    dates = sorted(frame["cal_date"].astype(str).tolist())
    if len(dates) < LOOKBACK:
        raise RuntimeError(f"Need at least {LOOKBACK} open days, got {len(dates)}")
    return dates[-LOOKBACK:]


def cache_path(date):
    path = RAW_DIR / "equity_turnover"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{date}.csv.gz"


def fetch_daily_inputs(pro, dates):
    frames = []
    for position, date in enumerate(dates, 1):
        path = cache_path(date)
        frame = None
        if path.exists():
            try:
                frame = pd.read_csv(path, dtype={"ts_code": str, "trade_date": str})
            except (OSError, pd.errors.EmptyDataError, ValueError):
                path.unlink(missing_ok=True)
        if frame is None or frame.empty or not {"vol", "free_share"}.issubset(frame.columns):
            volume = retry("daily " + date, lambda date=date: pro.daily(trade_date=date, fields="ts_code,trade_date,vol"))
            basic = retry("daily_basic " + date, lambda date=date: pro.daily_basic(trade_date=date, fields="ts_code,trade_date,free_share"))
            frame = volume.merge(basic, on=["ts_code", "trade_date"], how="inner")
            if frame.empty:
                raise RuntimeError(f"No turnover inputs for {date}")
            frame.to_csv(path, index=False, compression="gzip")
        frames.append(frame[["ts_code", "trade_date", "vol", "free_share"]])
        if position % 50 == 0 or position == len(dates):
            print(f"  成分股换手率输入 {position}/{len(dates)}", flush=True)
    result = pd.concat(frames, ignore_index=True)
    result["trade_date"] = result["trade_date"].astype(str)
    result["vol"] = pd.to_numeric(result["vol"], errors="coerce")
    result["free_share"] = pd.to_numeric(result["free_share"], errors="coerce")
    result = result[result["ts_code"].str.endswith((".SH", ".SZ"), na=False)]
    return result.dropna(subset=["vol", "free_share"])


def month_windows(start_date, end_date):
    current = datetime.strptime(start_date, "%Y%m%d").replace(day=1)
    end = datetime.strptime(end_date, "%Y%m%d")
    while current <= end:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield current.strftime("%Y%m%d"), min(next_month - timedelta(days=1), end).strftime("%Y%m%d")
        current = next_month


def memberships(pro, dates, end_date):
    snapshots = {}
    first_window = (datetime.strptime(dates[0], "%Y%m%d") - timedelta(days=40)).strftime("%Y%m%d")
    for name, code in INDICES:
        chunks = []
        for start, end in month_windows(first_window, end_date):
            frame = retry(
                f"index_weight {code} {start}-{end}",
                lambda code=code, start=start, end=end: pro.index_weight(index_code=code, start_date=start, end_date=end, fields="con_code,trade_date"),
            )
            if not frame.empty:
                chunks.append(frame)
        if not chunks:
            raise RuntimeError(f"No membership snapshots returned for {name}")
        frame = pd.concat(chunks, ignore_index=True).drop_duplicates(subset=["con_code", "trade_date"])
        frame["trade_date"] = frame["trade_date"].astype(str)
        snapshots[code] = {date: set(group["con_code"].astype(str)) for date, group in frame.groupby("trade_date")}
        if not any(date <= dates[0] for date in snapshots[code]):
            raise RuntimeError(f"No {name} membership snapshot on or before {dates[0]}")
        print(f"  {name} 成分快照 {len(snapshots[code])} 个", flush=True)
    return snapshots


def members_on(snapshots, code, date):
    dates = [snapshot_date for snapshot_date in snapshots[code] if snapshot_date <= date]
    if not dates:
        raise RuntimeError(f"No membership snapshot for {code} on {date}")
    return snapshots[code][max(dates)]


def percentile(values):
    return values.rank(method="max", pct=True) * 100


def main():
    pro = ts.pro_api()
    end_date = latest_open_date(pro)
    dates = trade_dates(pro, end_date)
    print(f"Tushare-only turnover update: {dates[0]} - {dates[-1]} ({len(dates)} days)", flush=True)
    print("[1/3] 获取成分股成交量与自由流通股本", flush=True)
    daily = fetch_daily_inputs(pro, dates)
    print("[2/3] 获取月度指数成分快照", flush=True)
    snapshots = memberships(pro, dates, end_date)
    print("[3/3] 聚合自由流通换手率", flush=True)
    rows = []
    for date, day in daily.groupby("trade_date", sort=True):
        row = {"date": datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")}
        for _, code in INDICES:
            members = members_on(snapshots, code, date)
            selected = day[day["ts_code"].isin(members)]
            if len(selected) < max(20, len(members) * 0.8):
                raise RuntimeError(f"{code} only has {len(selected)}/{len(members)} valid turnover inputs on {date}")
            free_float_turnover = selected["vol"].sum() / selected["free_share"].sum()
            row[code] = float(free_float_turnover)
        rows.append(row)
    frame = pd.DataFrame(rows).sort_values("date")
    payload_indices = []
    for name, code in INDICES:
        values = frame[code]
        payload_indices.append({
            "name": name,
            "code": code,
            "current": round(float(values.iloc[-1]), 4),
            "weekAverage": round(float(values.tail(5).mean()), 4),
            "monthAverage": round(float(values.tail(20).mean()), 4),
            "percentile": round(float(percentile(values).iloc[-1]), 4),
            "sparkline": [{"date": row["date"], "value": round(float(row[code]), 4)} for _, row in frame.tail(5).iterrows()],
            "history": [{"date": row["date"], "value": round(float(row[code]), 4)} for _, row in frame.iterrows()],
        })
        print(f"  {name}: {payload_indices[-1]['current']:.2f}%", flush=True)
    payload = {
        "asOf": frame.iloc[-1]["date"],
        "generatedAt": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "definition": "成分股成交量合计除以自由流通股本合计；daily.vol 与 daily_basic.free_share 均按 Tushare 单位聚合，结果为百分比",
        "indices": payload_indices,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"完成: {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
